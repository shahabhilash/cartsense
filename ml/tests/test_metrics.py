"""Metric values checked against hand-computed examples."""

import math

import numpy as np
import pytest

from cartsense_ml.eval.metrics import (
    all_metrics,
    catalogue_coverage,
    hit_matrix,
    hit_rate_at_k,
    map_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)

# user 0: hits at ranks 1 and 3, 3 relevant items
# user 1: no hits, 1 relevant item
RECS = np.array([[10, 11, 12, 13], [20, 21, 22, 23]])
RELEVANT = [{10, 12, 99}, {50}]


def test_hit_matrix():
    hits = hit_matrix(RECS, RELEVANT, 3)
    assert hits.tolist() == [[True, False, True], [False, False, False]]


def test_precision_and_recall():
    assert precision_at_k(RECS, RELEVANT, 3) == pytest.approx((2 / 3 + 0) / 2)
    assert recall_at_k(RECS, RELEVANT, 3) == pytest.approx((2 / 3 + 0) / 2)
    assert precision_at_k(RECS, RELEVANT, 1) == pytest.approx(0.5)


def test_hit_rate():
    assert hit_rate_at_k(RECS, RELEVANT, 3) == pytest.approx(0.5)


def test_ndcg():
    dcg = 1 / math.log2(2) + 1 / math.log2(4)
    idcg = 1 / math.log2(2) + 1 / math.log2(3) + 1 / math.log2(4)
    assert ndcg_at_k(RECS, RELEVANT, 3) == pytest.approx((dcg / idcg + 0) / 2)


def test_ndcg_ideal_uses_min_of_relevant_and_k():
    # one relevant item ranked first is a perfect list even at k=4
    assert ndcg_at_k(np.array([[1, 2, 3, 4]]), [{1}], 4) == pytest.approx(1.0)


def test_map():
    # AP@3 user 0 = (P@1 + P@3) / min(3, 3) = (1 + 2/3) / 3
    expected = ((1 + 2 / 3) / 3 + 0) / 2
    assert map_at_k(RECS, RELEVANT, 3) == pytest.approx(expected)


def test_map_normalises_by_k_when_many_relevant():
    recs = np.array([[1, 2]])
    assert map_at_k(recs, [{1, 2, 3, 4, 5}], 2) == pytest.approx(1.0)


def test_coverage():
    assert catalogue_coverage(RECS, 2, n_recommendable=8) == pytest.approx(4 / 8)


def test_perfect_and_empty_lists():
    recs = np.array([[1, 2], [3, 4]])
    perfect = [{1, 2}, {3, 4}]
    m = all_metrics(recs, perfect, [2], n_recommendable=4)
    assert all(m[name] == pytest.approx(1.0) for name in m)
    miss = all_metrics(recs, [{9}, {8}], [2], n_recommendable=4)
    assert miss["ndcg@2"] == miss["recall@2"] == miss["map@2"] == 0.0


def test_input_validation():
    with pytest.raises(ValueError):
        hit_matrix(RECS, RELEVANT, 5)
    with pytest.raises(ValueError):
        hit_matrix(RECS, [{1}], 2)
    with pytest.raises(ValueError):
        hit_matrix(RECS, [{1}, set()], 2)


def test_all_metrics_matches_individual_functions():
    rng = np.random.default_rng(1)
    recs = np.stack([rng.permutation(50)[:20] for _ in range(30)])
    relevant = [set(rng.choice(50, size=rng.integers(1, 8), replace=False).tolist()) for _ in range(30)]
    m = all_metrics(recs, relevant, [5, 20], n_recommendable=50)
    for k in (5, 20):
        assert m[f"precision@{k}"] == pytest.approx(precision_at_k(recs, relevant, k))
        assert m[f"recall@{k}"] == pytest.approx(recall_at_k(recs, relevant, k))
        assert m[f"ndcg@{k}"] == pytest.approx(ndcg_at_k(recs, relevant, k))
        assert m[f"map@{k}"] == pytest.approx(map_at_k(recs, relevant, k))
        assert m[f"hit_rate@{k}"] == pytest.approx(hit_rate_at_k(recs, relevant, k))
