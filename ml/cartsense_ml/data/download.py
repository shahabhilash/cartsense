"""Streaming download of the Amazon Reviews 2023 source files.

Files are written in fixed-size chunks to a ``.part`` file and renamed only
once the transfer is complete, so an interrupted run never leaves a truncated
file that later steps would mistake for a finished download.
"""

from __future__ import annotations

import logging
from pathlib import Path

import requests

log = logging.getLogger(__name__)

CHUNK_BYTES = 1 << 20  # 1 MiB


def _use_os_trust_store() -> None:
    """Verify TLS against the operating system's certificate store.

    Networks that inspect TLS traffic install their root certificate in the OS
    store, which the certifi bundle used by ``requests`` does not include.
    """
    try:
        import truststore

        truststore.inject_into_ssl()
    except ImportError:  # optional: fall back to certifi
        pass


def download_file(
    url: str,
    dest: Path,
    *,
    force: bool = False,
    session: requests.Session | None = None,
    timeout: float = 60.0,
) -> Path:
    """Download ``url`` to ``dest`` and return the destination path.

    An existing file is kept unless ``force`` is set. When the server reports a
    Content-Length, the number of bytes received must match it.
    """
    dest = Path(dest)
    if dest.exists() and not force:
        log.info("already downloaded: %s", dest)
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    if session is None:
        _use_os_trust_store()
        session = requests.Session()

    log.info("downloading %s -> %s", url, dest)
    with session.get(url, stream=True, timeout=timeout) as resp:
        resp.raise_for_status()
        expected = int(resp.headers.get("Content-Length", 0)) or None
        received = 0
        with open(tmp, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=CHUNK_BYTES):
                if chunk:
                    fh.write(chunk)
                    received += len(chunk)

    if expected is not None and received != expected:
        tmp.unlink(missing_ok=True)
        raise IOError(f"incomplete download of {url}: got {received} of {expected} bytes")

    tmp.replace(dest)
    log.info("saved %s (%.1f MB)", dest, received / 1e6)
    return dest
