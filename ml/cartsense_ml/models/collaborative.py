"""Collaborative filtering: item-kNN and implicit ALS.

Both models learn only from who-reviewed-what, so they cannot score products
that have no interactions before the cutoff. A small popularity prior (see
``normalized_recent_popularity``) orders those items and serves users without
history.

ItemKNN
    Cosine similarity between item columns of the binary user-item matrix,
    with shrinkage: ``sim(i, j) = |U_i & U_j| / (sqrt(|U_i| * |U_j|) + shrink)``.
    Shrinkage pulls similarities supported by only a few co-occurrences
    towards zero. Only the ``neighbors`` strongest similarities per item are
    kept. Score(u, j) = sum over the user's history items i of sim(i, j).

ALS (implicit library)
    Matrix factorisation for implicit feedback (Hu, Koren & Volinsky 2008).
    Every observed pair gets confidence ``1 + alpha`` and every unobserved pair
    confidence 1 with preference 0. Score(u, j) = user_factors[u] . item_factors[j].
"""

from __future__ import annotations

from typing import Any

import numpy as np
import scipy.sparse as sp

from cartsense_ml.data.dataset import InteractionDataset
from cartsense_ml.models.base import Recommender
from cartsense_ml.models.popularity import normalized_recent_popularity


def top_n_per_row(matrix: sp.csr_matrix, n: int) -> sp.csr_matrix:
    """Keep the n largest values in each row of a CSR matrix."""
    matrix = matrix.tocsr()
    indptr, indices, data = matrix.indptr, matrix.indices, matrix.data
    keep_rows, keep_cols, keep_vals = [], [], []
    for row in range(matrix.shape[0]):
        start, end = indptr[row], indptr[row + 1]
        if start == end:
            continue
        vals = data[start:end]
        cols = indices[start:end]
        if end - start > n:
            top = np.argpartition(-vals, n - 1)[:n]
            vals, cols = vals[top], cols[top]
        keep_rows.append(np.full(len(vals), row, dtype=np.int64))
        keep_cols.append(cols)
        keep_vals.append(vals)
    if not keep_rows:
        return sp.csr_matrix(matrix.shape, dtype=matrix.dtype)
    return sp.csr_matrix(
        (np.concatenate(keep_vals), (np.concatenate(keep_rows), np.concatenate(keep_cols))),
        shape=matrix.shape,
    )


class ItemKNN(Recommender):
    name = "item_knn"

    def __init__(self, neighbors: int = 100, shrink: float = 10.0, popularity_weight: float = 1e-3, seed: int = 42):
        super().__init__(seed=seed)
        self.neighbors = neighbors
        self.shrink = shrink
        self.popularity_weight = popularity_weight

    def params(self) -> dict[str, Any]:
        return {
            **super().params(),
            "neighbors": self.neighbors,
            "shrink": self.shrink,
            "popularity_weight": self.popularity_weight,
        }

    def _fit(self, ds: InteractionDataset) -> None:
        x = ds.matrix.astype(np.float32)  # users x items, binary
        co = (x.T @ x).tocsr()  # items x items co-occurrence counts
        co.setdiag(0)
        co.eliminate_zeros()
        counts = np.asarray(x.sum(axis=0)).ravel()
        norms = np.sqrt(counts)

        coo = co.tocoo()
        denom = norms[coo.row] * norms[coo.col] + self.shrink
        sim = sp.csr_matrix((coo.data / denom, (coo.row, coo.col)), shape=co.shape, dtype=np.float32)
        # Row i holds the neighbours of item i; scores use sim[i, j] for history item i
        self.similarity = top_n_per_row(sim, self.neighbors).astype(np.float32)
        self.pop = normalized_recent_popularity(ds)

    def score(self, user_idx: np.ndarray) -> np.ndarray:
        scores = np.tile(self.popularity_weight * self.pop, (len(user_idx), 1))
        warm = np.flatnonzero(user_idx >= 0)
        if warm.size:
            scores[warm] += (self.ds.matrix[user_idx[warm]] @ self.similarity).toarray()
        cold = np.flatnonzero(user_idx < 0)
        if cold.size:
            scores[cold] = self.pop
        return scores

    def contributions(self, user_idx: int, item_idx: int) -> list[tuple[int, float]]:
        """History items of the user ranked by how much they contributed to item_idx's score."""
        history = self.ds.matrix[user_idx].indices
        sims = np.asarray(self.similarity[history, item_idx].toarray()).ravel()
        order = np.argsort(-sims)
        return [(int(history[o]), float(sims[o])) for o in order if sims[o] > 0]


class ALS(Recommender):
    name = "als"

    def __init__(
        self,
        factors: int = 64,
        regularization: float = 0.05,
        alpha: float = 10.0,
        iterations: int = 20,
        popularity_weight: float = 1e-3,
        num_threads: int = 0,
        seed: int = 42,
    ):
        super().__init__(seed=seed)
        self.factors = factors
        self.regularization = regularization
        self.alpha = alpha
        self.iterations = iterations
        self.popularity_weight = popularity_weight
        self.num_threads = num_threads

    def params(self) -> dict[str, Any]:
        return {
            **super().params(),
            "factors": self.factors,
            "regularization": self.regularization,
            "alpha": self.alpha,
            "iterations": self.iterations,
            "popularity_weight": self.popularity_weight,
        }

    def _fit(self, ds: InteractionDataset) -> None:
        from implicit.cpu.als import AlternatingLeastSquares
        from threadpoolctl import threadpool_limits

        # implicit parallelises over users itself; a multi-threaded BLAS underneath
        # oversubscribes the CPU and slows training down (implicit checks this
        # when the model is constructed, so both steps run inside the limit)
        with threadpool_limits(limits=1, user_api="blas"):
            model = AlternatingLeastSquares(
                factors=self.factors,
                regularization=self.regularization,
                alpha=self.alpha,
                iterations=self.iterations,
                random_state=self.seed,
                num_threads=self.num_threads,
            )
            model.fit(ds.matrix.astype(np.float32), show_progress=False)
        self.user_factors = np.asarray(model.user_factors, dtype=np.float32)
        self.item_factors = np.asarray(model.item_factors, dtype=np.float32)
        # Items never seen in the history only ever received regularisation;
        # zero them so their scores come from the popularity prior alone.
        unseen = np.asarray(ds.matrix.sum(axis=0)).ravel() == 0
        self.item_factors[unseen] = 0.0
        self.pop = normalized_recent_popularity(ds)

    def score(self, user_idx: np.ndarray) -> np.ndarray:
        scores = np.tile(self.popularity_weight * self.pop, (len(user_idx), 1))
        warm = np.flatnonzero(user_idx >= 0)
        if warm.size:
            scores[warm] += self.user_factors[user_idx[warm]] @ self.item_factors.T
        cold = np.flatnonzero(user_idx < 0)
        if cold.size:
            scores[cold] = self.pop
        return scores

    def contributions(self, user_idx: int, item_idx: int) -> list[tuple[int, float]]:
        """History items most similar to item_idx in the latent space (cosine)."""
        history = self.ds.matrix[user_idx].indices
        if history.size == 0:
            return []
        f = self.item_factors
        target = f[item_idx]
        norms = np.linalg.norm(f[history], axis=1) * (np.linalg.norm(target) + 1e-12) + 1e-12
        sims = (f[history] @ target) / norms
        order = np.argsort(-sims)
        return [(int(history[o]), float(sims[o])) for o in order if sims[o] > 0]
