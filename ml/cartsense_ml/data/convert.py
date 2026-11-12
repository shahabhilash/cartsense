"""Convert raw gzip CSV / JSONL files to Parquet without loading them whole.

* Ratings are read with pyarrow's streaming CSV reader, one block at a time.
* Metadata records are parsed line by line, normalised into flat columns and
  written in batches of ``chunk_size`` rows. Only products that appear in the
  ratings file are kept, which shrinks the metadata from the whole category
  down to the 5-core catalogue.
"""

from __future__ import annotations

import gzip
import json
import logging
import math
from collections.abc import Iterable, Iterator
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

log = logging.getLogger(__name__)

RATINGS_SCHEMA = pa.schema(
    [
        ("user_id", pa.string()),
        ("parent_asin", pa.string()),
        ("rating", pa.float32()),
        ("timestamp", pa.int64()),
    ]
)

PRODUCT_SCHEMA = pa.schema(
    [
        ("item_id", pa.string()),
        ("title", pa.string()),
        ("main_category", pa.string()),
        ("brand", pa.string()),
        ("categories", pa.list_(pa.string())),
        ("features", pa.list_(pa.string())),
        ("description", pa.string()),
        ("price", pa.float64()),
        ("average_rating", pa.float32()),
        ("rating_number", pa.int64()),
        ("image_url", pa.string()),
        ("date_first_available", pa.date32()),
        ("details_json", pa.string()),
    ]
)


# --------------------------------------------------------------------------- #
# Ratings
# --------------------------------------------------------------------------- #
def ratings_to_parquet(src: Path, dest: Path, block_bytes: int = 8 << 20) -> int:
    """Stream the gzip ratings CSV into Parquet. Returns the number of rows."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    reader = pacsv.open_csv(
        src,
        read_options=pacsv.ReadOptions(block_size=block_bytes),
        convert_options=pacsv.ConvertOptions(
            column_types={f.name: f.type for f in RATINGS_SCHEMA},
            include_columns=RATINGS_SCHEMA.names,
        ),
    )
    rows = 0
    with pq.ParquetWriter(dest, RATINGS_SCHEMA) as writer:
        for batch in reader:
            table = pa.Table.from_batches([batch]).select(RATINGS_SCHEMA.names).cast(RATINGS_SCHEMA)
            writer.write_table(table)
            rows += table.num_rows
    log.info("ratings: wrote %d rows to %s", rows, dest)
    return rows


def unique_item_ids(ratings_parquet: Path) -> set[str]:
    """Distinct product ids in the ratings file (reads only that column)."""
    pf = pq.ParquetFile(ratings_parquet)
    ids: set[str] = set()
    for batch in pf.iter_batches(columns=["parent_asin"]):
        ids.update(batch.column(0).to_pylist())
    return ids


# --------------------------------------------------------------------------- #
# Metadata
# --------------------------------------------------------------------------- #
def iter_jsonl_chunks(path: Path, chunk_size: int) -> Iterator[list[dict[str, Any]]]:
    """Yield lists of at most ``chunk_size`` parsed records from a gzip JSONL file.
    Malformed lines are skipped and logged."""
    chunk: list[dict[str, Any]] = []
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                chunk.append(json.loads(line))
            except json.JSONDecodeError:
                log.warning("skipping malformed JSON on line %d of %s", lineno, path)
                continue
            if len(chunk) >= chunk_size:
                yield chunk
                chunk = []
    if chunk:
        yield chunk


def _clean_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clean_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [s for s in (_clean_str(v) for v in value) if s]


def parse_price(value: Any) -> float | None:
    """Prices appear as numbers, numeric strings ("$19.99", "1,299.00") or
    placeholders such as "—". Anything that is not a positive number is None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        price = float(value)
    else:
        text = str(value).replace("$", "").replace(",", "").strip()
        try:
            price = float(text)
        except ValueError:
            return None
    if math.isnan(price) or price <= 0:
        return None
    return price


def pick_image_url(images: Any) -> str | None:
    """Prefer the MAIN image; within an image prefer ``large`` over ``hi_res``."""
    if not isinstance(images, list) or not images:
        return None
    ordered = sorted(
        (img for img in images if isinstance(img, dict)),
        key=lambda img: img.get("variant") != "MAIN",
    )
    for img in ordered:
        for key in ("large", "hi_res", "thumb"):
            url = _clean_str(img.get(key))
            if url:
                return url
    return None


def parse_first_available(details: Any) -> date | None:
    if not isinstance(details, dict):
        return None
    raw = _clean_str(details.get("Date First Available"))
    if not raw:
        return None
    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def normalize_meta(record: dict[str, Any]) -> dict[str, Any] | None:
    """Flatten one raw metadata record into the PRODUCT_SCHEMA columns.
    Returns None for records without a product id."""
    item_id = _clean_str(record.get("parent_asin"))
    if not item_id:
        return None

    description = "\n".join(_clean_str_list(record.get("description"))) or None
    details = record.get("details") if isinstance(record.get("details"), dict) else {}
    rating_number = record.get("rating_number")
    average_rating = record.get("average_rating")

    return {
        "item_id": item_id,
        "title": _clean_str(record.get("title")),
        "main_category": _clean_str(record.get("main_category")),
        "brand": _clean_str(record.get("store")),
        "categories": _clean_str_list(record.get("categories")),
        "features": _clean_str_list(record.get("features")),
        "description": description,
        "price": parse_price(record.get("price")),
        "average_rating": float(average_rating) if isinstance(average_rating, (int, float)) else None,
        "rating_number": int(rating_number) if isinstance(rating_number, (int, float)) else None,
        "image_url": pick_image_url(record.get("images")),
        "date_first_available": parse_first_available(details),
        "details_json": json.dumps(details, ensure_ascii=False, sort_keys=True) if details else None,
    }


def _rows_to_table(rows: Iterable[dict[str, Any]]) -> pa.Table:
    return pa.Table.from_pylist(list(rows), schema=PRODUCT_SCHEMA)


def metadata_to_parquet(
    src: Path,
    dest: Path,
    chunk_size: int,
    keep_ids: set[str] | None = None,
) -> dict[str, int]:
    """Stream metadata JSONL into Parquet, keeping only ``keep_ids`` if given.
    Returns counts of records seen and written."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    seen = written = 0
    with pq.ParquetWriter(dest, PRODUCT_SCHEMA) as writer:
        for chunk in iter_jsonl_chunks(src, chunk_size):
            seen += len(chunk)
            rows = []
            for record in chunk:
                row = normalize_meta(record)
                if row is None:
                    continue
                if keep_ids is not None and row["item_id"] not in keep_ids:
                    continue
                rows.append(row)
            if rows:
                writer.write_table(_rows_to_table(rows))
                written += len(rows)
            log.info("metadata: %d records read, %d kept", seen, written)
    return {"records_seen": seen, "records_written": written}
