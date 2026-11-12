"""NCF and hybrid ranker tests on a small synthetic dataset with a clear signal.

Two user groups each prefer their own half of the catalogue over time, so a
model that learns anything personal should rank the user's own half first.
"""

from datetime import date

import numpy as np
import pandas as pd
import pytest
import torch

from cartsense_ml.data.dataset import build_dataset
from cartsense_ml.models.hybrid import HybridRanker, _rank_within_rows, union_candidates
from cartsense_ml.models.ncf import NCF

DAY = 86_400_000
T0 = 1_500_000_000_000
N_ITEMS = 40


def _products():
    return pd.DataFrame(
        {
            "item_id": [f"I{i:02d}" for i in range(N_ITEMS)],
            "title": [("space shooter " if i < N_ITEMS // 2 else "farm simulator ") + str(i) for i in range(N_ITEMS)],
            "brand": ["Acme" if i < N_ITEMS // 2 else "Barn" for i in range(N_ITEMS)],
            "categories": [["Video Games", "PC" if i < N_ITEMS // 2 else "Nintendo Switch"] for i in range(N_ITEMS)],
            "features": [[]] * N_ITEMS,
            "description": [None] * N_ITEMS,
            "date_first_available": [date(2010, 1, 1)] * N_ITEMS,
        }
    )


@pytest.fixture(scope="module")
def ds():
    rng = np.random.default_rng(0)
    rows = []
    for u in range(120):
        group = u % 2
        items = rng.choice(np.arange(N_ITEMS // 2) + group * (N_ITEMS // 2), size=8, replace=False)
        for j, i in enumerate(items):
            rows.append((f"U{u:03d}", f"I{i:02d}", 5.0, T0 + int(rng.integers(0, 400)) * DAY))
    history = pd.DataFrame(rows, columns=["user_id", "item_id", "rating", "timestamp"])
    return build_dataset(history, _products())


def _own_half_share(model, ds, k=5):
    users = np.arange(0, 40)
    recs = model.recommend(users, k=k)
    groups = np.array([int(u[1:]) % 2 for u in ds.user_ids[users]])
    item_group = (recs >= N_ITEMS // 2).astype(int)  # item index order matches I00..I39
    return float((item_group == groups[:, None]).mean())


def test_union_candidates_dedupes_rows():
    a = np.array([[3, 1], [5, 6]])
    b = np.array([[1, 2], [6, 5]])
    out = union_candidates([a, b])
    assert [sorted(x for x in row if x >= 0) for row in out.tolist()] == [[1, 2, 3], [5, 6]]
    assert (out == -1).sum() == 3


def test_rank_within_rows_ignores_invalid():
    values = np.array([[0.1, 0.9, 0.5]], dtype=np.float32)
    valid = np.array([[True, False, True]])
    ranks = _rank_within_rows(values, valid)
    assert ranks[0, 2] == 1 and ranks[0, 0] == 2


def test_ncf_learns_group_preference_and_is_reproducible(ds):
    a = NCF(dim=8, layers=[16, 8], epochs=8, batch_size=256, lr=5e-3, num_threads=1, seed=3).fit(ds)
    b = NCF(dim=8, layers=[16, 8], epochs=8, batch_size=256, lr=5e-3, num_threads=1, seed=3).fit(ds)
    assert a.epoch_losses[-1] < a.epoch_losses[0]
    assert _own_half_share(a, ds) > 0.8
    assert np.allclose(a.score(np.arange(5)), b.score(np.arange(5)))


def test_ncf_fast_scoring_matches_network(ds):
    model = NCF(dim=8, layers=[16, 8], epochs=1, batch_size=256, num_threads=1).fit(ds)
    users = np.array([0, 7, 11])
    fast = model._logits(users)
    with torch.no_grad():
        ref = np.stack(
            [model.net(torch.full((ds.n_items,), int(u)), torch.arange(ds.n_items)).numpy() for u in users]
        )
    assert np.allclose(fast, ref, atol=1e-5)
    probs = model.score_pairs(np.array([0, 0]), np.array([1, 2]))
    assert np.allclose(probs, 1 / (1 + np.exp(-fast[0, [1, 2]])), atol=1e-5)


def test_ncf_rejects_odd_first_layer():
    with pytest.raises(ValueError):
        NCF(layers=[15, 8])


SMALL_GENERATORS = [
    {"label": "knn", "name": "item_knn", "params": {"neighbors": 20, "shrink": 5, "popularity_weight": 0.1}},
    {"label": "content", "name": "content_tfidf", "params": {"min_df": 1, "popularity_weight": 0.1}},
    {"label": "pop", "name": "recent_popular", "params": {"half_life_days": 90}},
]


@pytest.fixture(scope="module")
def hybrid(ds):
    return HybridRanker(
        generators=SMALL_GENERATORS,
        n_candidates=10,
        label_fraction=0.25,
        xgb={"n_estimators": 30, "max_depth": 3},
        early_stopping_rounds=10,
        valid_user_fraction=0.2,
        seed=1,
    ).fit(ds)


def test_hybrid_trains_with_label_window_before_cutoff(hybrid, ds):
    d = hybrid.diagnostics()
    # The ranker's labels come from the last 25% of the history, never after it
    assert d["label_cut_ms"] < ds.cutoff_ms
    assert d["train_users"] > 0 and d["ranker_train_rows"] > 0
    assert 0 < d["candidate_recall_label_window"] <= 1
    assert set(d["feature_gain"]) <= set(hybrid.feature_names)
    assert "max_text_sim_to_history" in hybrid.feature_names


def test_hybrid_recommends_from_candidates_only(hybrid, ds):
    users = np.arange(10)
    recs = hybrid.recommend(users, k=5)
    scores = hybrid.score(users)
    chosen = np.take_along_axis(scores, recs, axis=1)
    assert (chosen > -1e5).all()  # every recommended item was a scored candidate
    seen = ds.matrix[users].toarray() > 0
    assert not np.take_along_axis(seen, recs, axis=1).any()


def test_hybrid_personalises_and_handles_cold_users(hybrid, ds):
    assert _own_half_share(hybrid, ds) > 0.8
    pop_only = hybrid.score(np.array([-1]))[0]
    assert np.allclose(pop_only, hybrid.pop)


def test_hybrid_rejects_duplicate_generator_labels():
    with pytest.raises(ValueError):
        HybridRanker(generators=[SMALL_GENERATORS[0], SMALL_GENERATORS[0]])
