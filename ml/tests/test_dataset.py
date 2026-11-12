from datetime import date

import numpy as np
import pandas as pd
import pytest

from cartsense_ml.data.dataset import build_dataset

DAY = 86_400_000
T0 = int(pd.Timestamp("2020-01-01").value // 1_000_000)


@pytest.fixture
def products():
    return pd.DataFrame(
        {
            "item_id": ["C", "A", "B", "D", "E"],
            "title": ["c", "a", "b", "d", "e"],
            "date_first_available": [
                date(2019, 6, 1),  # C: listed before cutoff, never reviewed -> available
                date(2018, 1, 1),
                None,  # B: no date but reviewed -> available
                date(2021, 1, 1),  # D: released after cutoff -> not available
                None,  # E: no date, never reviewed -> not available
            ],
        }
    )


@pytest.fixture
def history():
    return pd.DataFrame(
        {
            "user_id": ["U2", "U1", "U1"],
            "item_id": ["A", "A", "B"],
            "rating": [5.0, 4.0, 3.0],
            "timestamp": [T0, T0 + DAY, T0 + 2 * DAY],
        }
    )


def test_indices_are_sorted_and_cover_catalogue(history, products):
    ds = build_dataset(history, products)
    assert ds.item_ids.tolist() == ["A", "B", "C", "D", "E"]
    assert ds.user_ids.tolist() == ["U1", "U2"]
    assert ds.products["item_id"].tolist() == ds.item_ids.tolist()
    assert ds.n_users == 2 and ds.n_items == 5


def test_matrix_is_binary_user_item(history, products):
    m = build_dataset(history, products).matrix.toarray()
    assert m.tolist() == [[1, 1, 0, 0, 0], [1, 0, 0, 0, 0]]


def test_availability_uses_history_and_release_date(history, products):
    ds = build_dataset(history, products, cutoff_ms=T0 + 2 * DAY)
    assert dict(zip(ds.item_ids, ds.available)) == {
        "A": True,
        "B": True,
        "C": True,
        "D": False,
        "E": False,
    }


def test_encoding_unknown_ids(history, products):
    ds = build_dataset(history, products)
    assert ds.encode_users(["U2", "nobody"]).tolist() == [1, -1]
    assert ds.encode_items(["E", "ZZZ"]).tolist() == [4, -1]


def test_rejects_history_after_cutoff(history, products):
    with pytest.raises(ValueError):
        build_dataset(history, products, cutoff_ms=T0)


def test_rejects_unknown_items(history, products):
    bad = pd.concat([history, pd.DataFrame([{"user_id": "U3", "item_id": "X", "rating": 1.0, "timestamp": T0}])])
    with pytest.raises(ValueError):
        build_dataset(bad, products)


def test_history_encoding_dtypes(history, products):
    h = build_dataset(history, products).history
    assert h["user_idx"].dtype == np.int64 and h["item_idx"].dtype == np.int64
    assert h["rating"].dtype == np.float32
