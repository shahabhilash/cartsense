from datetime import date

import numpy as np
import pandas as pd
import pytest

from cartsense_ml.data.dataset import build_dataset
from cartsense_ml.eval.harness import build_target, evaluate, oracle_recall
from cartsense_ml.models.base import NotFittedError, Recommender, top_k


class FixedScores(Recommender):
    """Scores items by a fixed vector; used to test the shared machinery."""

    name = "fixed"

    def __init__(self, item_scores):
        super().__init__()
        self.item_scores = np.asarray(item_scores, dtype=np.float32)

    def _fit(self, ds):
        pass

    def score(self, user_idx):
        return np.tile(self.item_scores, (len(user_idx), 1))


@pytest.fixture
def ds():
    products = pd.DataFrame(
        {
            "item_id": ["A", "B", "C", "D", "E"],
            "date_first_available": [None, None, None, None, date(2030, 1, 1)],
        }
    )
    history = pd.DataFrame(
        {
            "user_id": ["U1", "U1", "U2", "U3"],
            "item_id": ["A", "B", "C", "D"],
            "rating": [5.0] * 4,
            "timestamp": [1, 2, 3, 4],
        }
    )
    # E is released after the cutoff: never recommendable
    return build_dataset(history, products)


def test_top_k_orders_and_breaks_ties_by_index():
    scores = np.array([[0.1, 0.9, 0.5, 0.9], [1.0, 1.0, 1.0, 0.0]], dtype=np.float32)
    assert top_k(scores, 2).tolist() == [[1, 3], [0, 1]]
    assert top_k(scores, 4).tolist() == [[1, 3, 2, 0], [0, 1, 2, 3]]


def test_recommend_excludes_seen_and_unavailable(ds):
    # E has the highest score but is unavailable; U1 has seen A and B
    model = FixedScores([5, 4, 3, 2, 9]).fit(ds)
    recs = model.recommend(ds.encode_users(["U1", "U2", "new"]), k=2, batch_size=2)
    assert recs.tolist() == [[2, 3], [0, 1], [0, 1]]


def test_recommend_requires_fit():
    with pytest.raises(NotFittedError):
        FixedScores([1]).recommend(np.array([0]), k=1)


def test_build_target_groups_and_drops_history_pairs(ds):
    target = pd.DataFrame({"user_id": ["U1", "U1", "U4", "U2"], "item_id": ["A", "C", "E", "D"]})
    t = build_target(ds, target)
    assert t.user_ids.tolist() == ["U1", "U2", "U4"]
    # (U1, A) was already in history, so only C remains for U1
    assert t.relevant == [{2}, {3}, {4}]
    assert t.warm.tolist() == [True, True, False]


def test_oracle_recall_counts_only_available_items(ds):
    # user 0: one of two items available; user 1: only E (unavailable)
    assert oracle_recall(ds, [{0, 4}, {4}], k=10) == pytest.approx((0.5 + 0.0) / 2)


def test_evaluate_reports_slices(ds):
    target = build_target(ds, pd.DataFrame({"user_id": ["U1", "U4"], "item_id": ["C", "A"]}))
    model = FixedScores([5, 4, 3, 2, 9]).fit(ds)
    res = evaluate(model, ds, target, k_values=[1, 2])
    assert res["n_users"] == 2 and res["n_warm_users"] == 1 and res["n_cold_users"] == 1
    assert res["n_recommendable_items"] == 4
    # U1 gets [C, D] -> hit at rank 1; U4 gets [A, B] -> hit at rank 1
    assert res["overall"]["precision@1"] == pytest.approx(1.0)
    assert res["warm_users"]["recall@2"] == pytest.approx(1.0)
    assert res["cold_users"]["hit_rate@1"] == pytest.approx(1.0)
    assert res["oracle_recall"]["recall@1"] == pytest.approx(1.0)
