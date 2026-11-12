from datetime import date

import numpy as np
import pandas as pd
import pytest

from cartsense_ml.data.dataset import build_dataset
from cartsense_ml.models.popularity import (
    DAY_MS,
    CategoryPopular,
    MostPopular,
    RandomRecommender,
    RecentPopular,
)

T = 1_000 * DAY_MS  # cutoff


@pytest.fixture
def ds():
    products = pd.DataFrame(
        {
            "item_id": ["A", "B", "C", "D"],
            "categories": [
                ["Video Games", "PC"],
                ["Video Games", "PC"],
                ["Video Games", "Nintendo Switch"],
                ["Video Games"],
            ],
            "date_first_available": [None] * 4,
        }
    )
    rows = [
        # A: 3 old interactions; B: 2 recent; C: 1 recent; D: 1 old
        ("U1", "A", T - 900 * DAY_MS),
        ("U2", "A", T - 900 * DAY_MS),
        ("U3", "A", T - 900 * DAY_MS),
        ("U4", "B", T - 1 * DAY_MS),
        ("U5", "B", T),
        ("U5", "C", T),
        ("U6", "D", T - 900 * DAY_MS),
        ("U7", "C", T - 2 * DAY_MS),
    ]
    history = pd.DataFrame(rows, columns=["user_id", "item_id", "timestamp"]).assign(rating=5.0)
    return build_dataset(history, products, cutoff_ms=T)


def test_most_popular_ranks_by_count(ds):
    model = MostPopular().fit(ds)
    assert model.item_scores.tolist() == [3, 2, 2, 1]
    assert model.recommend(np.array([-1]), k=4).tolist() == [[0, 1, 2, 3]]


def test_recent_popular_prefers_recent_items(ds):
    model = RecentPopular(half_life_days=30).fit(ds)
    assert model.recommend(np.array([-1]), k=2).tolist() == [[1, 2]]
    # an interaction at the cutoff has weight exactly 1
    assert model.item_scores[1] == pytest.approx(1 + 0.5 ** (1 / 30), rel=1e-5)


def test_recent_popular_rejects_bad_half_life():
    with pytest.raises(ValueError):
        RecentPopular(half_life_days=0)


def test_category_popular_follows_user_platform(ds):
    model = CategoryPopular(half_life_days=30).fit(ds)
    u7 = ds.encode_users(["U7"])  # a Switch player who has seen C
    u1 = ds.encode_users(["U1"])  # a PC player who has seen A
    assert model.top_platforms(int(u7[0])) == [("Nintendo Switch", 1.0)]
    # U1 should get the other PC game (B) first
    assert model.recommend(u1, k=1).tolist() == [[1]]
    # A cold user gets plain recent popularity
    cold = model.recommend(np.array([-1]), k=2)
    assert cold.tolist() == RecentPopular(half_life_days=30).fit(ds).recommend(np.array([-1]), k=2).tolist()


def test_category_popular_unknown_platform_bucket(ds):
    model = CategoryPopular().fit(ds)
    assert "<unknown>" in model.platform_names.tolist()
    assert model.top_platforms(-1) == []


def test_random_is_reproducible_with_seed(ds):
    a = RandomRecommender(seed=7).fit(ds).recommend(np.array([-1, -1]), k=3)
    b = RandomRecommender(seed=7).fit(ds).recommend(np.array([-1, -1]), k=3)
    assert a.tolist() == b.tolist()


def test_random_seeds_differ_on_larger_catalogue():
    n = 200
    products = pd.DataFrame(
        {"item_id": [f"I{i:03d}" for i in range(n)], "categories": [[]] * n, "date_first_available": [date(2000, 1, 1)] * n}
    )
    history = pd.DataFrame({"user_id": ["U"], "item_id": ["I000"], "rating": [5.0], "timestamp": [1_600_000_000_000]})
    big = build_dataset(history, products)
    a = RandomRecommender(seed=7).fit(big).recommend(np.array([-1]), k=10)
    c = RandomRecommender(seed=8).fit(big).recommend(np.array([-1]), k=10)
    assert a.tolist() != c.tolist()
