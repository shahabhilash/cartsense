"""Top-K ranking metrics with binary relevance.

All functions take

* ``recs``: int array of shape (n_users, K) holding recommended item indices,
  best first (K may be larger than the cutoff ``k``);
* ``relevant``: a list with one set of relevant item indices per user.

and return the mean over users. Users with no relevant items must be removed
before calling; they would make recall and AP undefined.

Definitions (rel = relevant set of one user, hit_i = 1 if the item at rank i
is relevant, ranks start at 1):

    Precision@k = sum_{i<=k} hit_i / k
    Recall@k    = sum_{i<=k} hit_i / |rel|
    NDCG@k      = DCG@k / IDCG@k, DCG@k = sum_{i<=k} hit_i / log2(i + 1),
                  IDCG@k = DCG of a perfect list with min(|rel|, k) hits
    AP@k        = sum_{i<=k} hit_i * Precision@i / min(|rel|, k)
    HitRate@k   = 1 if any hit in the top k

MAP@k is the mean of AP@k. Catalogue coverage is the share of recommendable
items that appear in at least one user's top-k list.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def hit_matrix(recs: np.ndarray, relevant: Sequence[set[int]], k: int) -> np.ndarray:
    """Boolean (n_users, k) matrix: is the item at each rank relevant?"""
    recs = np.asarray(recs)
    if recs.ndim != 2:
        raise ValueError("recs must be a 2-D array of shape (n_users, K)")
    if len(relevant) != recs.shape[0]:
        raise ValueError("recs and relevant must have one row per user")
    if k < 1 or k > recs.shape[1]:
        raise ValueError(f"k must be between 1 and {recs.shape[1]}, got {k}")
    if any(len(r) == 0 for r in relevant):
        raise ValueError("every user must have at least one relevant item")

    top = recs[:, :k]
    # Encode (user, item) pairs as single integers so membership is one vectorised isin
    n_items = int(max(top.max(initial=0), max((max(r) for r in relevant), default=0))) + 1
    rows = np.repeat(np.arange(len(relevant)), [len(r) for r in relevant])
    items = np.fromiter((i for r in relevant for i in r), dtype=np.int64, count=len(rows))
    rel_codes = rows.astype(np.int64) * n_items + items
    rec_codes = np.arange(top.shape[0], dtype=np.int64)[:, None] * n_items + top
    return np.isin(rec_codes, rel_codes)


def _n_relevant(relevant: Sequence[set[int]]) -> np.ndarray:
    return np.fromiter((len(r) for r in relevant), dtype=np.float64, count=len(relevant))


def precision_at_k(recs, relevant, k: int) -> float:
    return float(hit_matrix(recs, relevant, k).sum(axis=1).mean() / k)


def recall_at_k(recs, relevant, k: int) -> float:
    hits = hit_matrix(recs, relevant, k).sum(axis=1)
    return float((hits / _n_relevant(relevant)).mean())


def hit_rate_at_k(recs, relevant, k: int) -> float:
    return float(hit_matrix(recs, relevant, k).any(axis=1).mean())


def ndcg_at_k(recs, relevant, k: int) -> float:
    hits = hit_matrix(recs, relevant, k)
    discounts = 1.0 / np.log2(np.arange(2, k + 2))
    dcg = (hits * discounts).sum(axis=1)
    ideal_hits = np.minimum(_n_relevant(relevant), k).astype(int)
    idcg = np.cumsum(discounts)[ideal_hits - 1]
    return float((dcg / idcg).mean())


def map_at_k(recs, relevant, k: int) -> float:
    hits = hit_matrix(recs, relevant, k)
    precision_at_i = np.cumsum(hits, axis=1) / np.arange(1, k + 1)
    ap = (precision_at_i * hits).sum(axis=1) / np.minimum(_n_relevant(relevant), k)
    return float(ap.mean())


def catalogue_coverage(recs: np.ndarray, k: int, n_recommendable: int) -> float:
    if n_recommendable <= 0:
        raise ValueError("n_recommendable must be positive")
    return float(np.unique(np.asarray(recs)[:, :k]).size / n_recommendable)


def all_metrics(
    recs: np.ndarray, relevant: Sequence[set[int]], k_values: Sequence[int], n_recommendable: int
) -> dict[str, float]:
    """Every metric at every cutoff, keyed like ``ndcg@10``."""
    # The hit matrix is computed once at the largest cutoff and sliced for smaller ones
    k_max = max(k_values)
    hits_full = hit_matrix(recs, relevant, k_max)
    n_rel = _n_relevant(relevant)
    out: dict[str, float] = {}
    for k in k_values:
        hits = hits_full[:, :k]
        n_hits = hits.sum(axis=1)
        discounts = 1.0 / np.log2(np.arange(2, k + 2))
        idcg = np.cumsum(discounts)[np.minimum(n_rel, k).astype(int) - 1]
        precision_at_i = np.cumsum(hits, axis=1) / np.arange(1, k + 1)
        out[f"precision@{k}"] = float(n_hits.mean() / k)
        out[f"recall@{k}"] = float((n_hits / n_rel).mean())
        out[f"ndcg@{k}"] = float(((hits * discounts).sum(axis=1) / idcg).mean())
        out[f"map@{k}"] = float(((precision_at_i * hits).sum(axis=1) / np.minimum(n_rel, k)).mean())
        out[f"hit_rate@{k}"] = float(hits.any(axis=1).mean())
        out[f"coverage@{k}"] = catalogue_coverage(recs, k, n_recommendable)
    return out
