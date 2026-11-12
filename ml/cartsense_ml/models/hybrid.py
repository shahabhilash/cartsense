"""Two-stage hybrid recommender: candidate generation + XGBoost re-ranking.

Stage 1, candidates
    Several base models ("generators", e.g. ALS, item-kNN, content, NCF,
    popularity) each retrieve their top ``n_candidates`` items for a user. The
    union, typically 100-250 items, is the candidate set.

Stage 2, ranking
    Every (user, candidate) pair gets a feature vector: each generator's score
    and rank, which generators retrieved it, item statistics, user statistics
    and user-item affinities (platform and brand share, text similarity to the
    user's history). An XGBoost LambdaMART model (``rank:ndcg``) orders the
    candidates of each user.

Training without leakage
    The ranker needs labels from a period *after* the data its generators were
    trained on, exactly as at serving time:

        history = [ ............ H' ............ | label window L ]
                                                 ^ cut = quantile(1 - label_fraction)

    1. fit the generators on H' only,
    2. build candidates + features for users active in L, label = 1 if the
       candidate was reviewed in L,
    3. train XGBoost on those groups (early stopping on a held-out 10% of users),
    4. refit the generators on the full history for inference.

    The evaluation window (val or test) is never seen in any step.

Users without history get recent popularity, like every other model.
"""

from __future__ import annotations

import logging
import time
from collections import Counter
from typing import Any

import numpy as np
import pandas as pd

from cartsense_ml.data.dataset import InteractionDataset, build_dataset
from cartsense_ml.data.stats import platform_of
from cartsense_ml.models.base import Recommender
from cartsense_ml.models.content import ContentTfidf
from cartsense_ml.models.popularity import DAY_MS, normalized_recent_popularity

log = logging.getLogger(__name__)

NON_CANDIDATE_SCORE = -1e6

DEFAULT_GENERATORS = [
    {"label": "als", "name": "als",
     "params": {"factors": 128, "regularization": 1.0, "alpha": 40, "popularity_weight": 1.0}},
    {"label": "knn", "name": "item_knn", "params": {"neighbors": 50, "shrink": 100, "popularity_weight": 1.0}},
    {"label": "content", "name": "content_tfidf", "params": {"half_life_days": 730, "popularity_weight": 1.0}},
    {"label": "pop", "name": "recent_popular", "params": {"half_life_days": 180}},
]

DEFAULT_XGB = {
    "n_estimators": 500,
    "learning_rate": 0.05,
    "max_depth": 6,
    "min_child_weight": 1.0,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_lambda": 1.0,
}


def union_candidates(lists: list[np.ndarray]) -> np.ndarray:
    """Row-wise union of candidate lists. Returns sorted item indices per row
    with duplicates replaced by -1 (fixed width = sum of list widths)."""
    cand = np.concatenate(lists, axis=1)
    cand = np.sort(cand, axis=1)
    dup = np.zeros_like(cand, dtype=bool)
    dup[:, 1:] = cand[:, 1:] == cand[:, :-1]
    cand[dup] = -1
    return cand


def _rank_within_rows(values: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """1-based descending rank of each entry among the valid entries of its row."""
    v = np.where(valid, values, -np.inf)
    order = np.argsort(-v, axis=1, kind="stable")
    ranks = np.empty_like(order)
    np.put_along_axis(ranks, order, np.arange(1, v.shape[1] + 1)[None, :].repeat(v.shape[0], 0), axis=1)
    return ranks.astype(np.float32)


class HybridRanker(Recommender):
    name = "hybrid"

    def __init__(
        self,
        generators: list[dict[str, Any]] | None = None,
        n_candidates: int = 50,
        label_fraction: float = 0.11,
        max_train_users: int | None = 30_000,
        xgb: dict[str, Any] | None = None,
        early_stopping_rounds: int = 30,
        valid_user_fraction: float = 0.1,
        seed: int = 42,
    ):
        super().__init__(seed=seed)
        self.generator_specs = generators or DEFAULT_GENERATORS
        labels = [g["label"] for g in self.generator_specs]
        if len(set(labels)) != len(labels):
            raise ValueError("generator labels must be unique")
        self.n_candidates = n_candidates
        self.label_fraction = label_fraction
        self.max_train_users = max_train_users
        self.xgb_params = {**DEFAULT_XGB, **(xgb or {})}
        self.early_stopping_rounds = early_stopping_rounds
        self.valid_user_fraction = valid_user_fraction
        self._diagnostics: dict[str, Any] = {}

    def params(self) -> dict[str, Any]:
        return {
            **super().params(),
            "generators": [f"{g['label']}={g['name']}" for g in self.generator_specs],
            "n_candidates": self.n_candidates,
            "label_fraction": self.label_fraction,
            "max_train_users": self.max_train_users,
            **{f"xgb_{k}": v for k, v in self.xgb_params.items()},
        }

    def diagnostics(self) -> dict[str, Any]:
        return self._diagnostics

    # ------------------------------------------------------------------ #
    # Training
    # ------------------------------------------------------------------ #
    def _build_generators(self, ds: InteractionDataset) -> dict[str, Recommender]:
        from cartsense_ml.models.registry import build_model  # avoid an import cycle

        gens = {}
        for spec in self.generator_specs:
            start = time.perf_counter()
            gens[spec["label"]] = build_model(spec["name"], spec.get("params"), seed=self.seed).fit(ds)
            log.info("hybrid: fitted generator %s in %.1fs", spec["label"], time.perf_counter() - start)
        return gens

    def _split_history(self, ds: InteractionDataset) -> tuple[InteractionDataset, pd.DataFrame]:
        h = ds.history
        cut = int(h["timestamp"].quantile(1 - self.label_fraction, interpolation="lower"))
        decoded = pd.DataFrame(
            {
                "user_id": ds.user_ids[h["user_idx"].to_numpy()],
                "item_id": ds.item_ids[h["item_idx"].to_numpy()],
                "rating": h["rating"].to_numpy(),
                "timestamp": h["timestamp"].to_numpy(),
            }
        )
        early = decoded[decoded["timestamp"] <= cut]
        label_window = decoded[decoded["timestamp"] > cut]
        return build_dataset(early, ds.products, cutoff_ms=cut), label_window

    def _fit(self, ds: InteractionDataset) -> None:
        import xgboost as xgb

        rng = np.random.default_rng(self.seed)
        sub_ds, label_window = self._split_history(ds)
        self._diagnostics = {"label_cut_ms": sub_ds.cutoff_ms, "label_window_rows": len(label_window)}

        sub_gens = self._build_generators(sub_ds)

        # Users active in the label window who also have history before the cut
        lw = label_window.assign(user_idx=sub_ds.encode_users(label_window["user_id"]),
                                 item_idx=sub_ds.encode_items(label_window["item_id"]))
        lw = lw[lw["user_idx"] >= 0]
        users = np.sort(lw["user_idx"].unique())
        if self.max_train_users and users.size > self.max_train_users:
            users = np.sort(rng.choice(users, size=self.max_train_users, replace=False))
        lw = lw[lw["user_idx"].isin(users)]

        start = time.perf_counter()
        feats, cand, valid = self._features(sub_ds, sub_gens, users)
        rows = np.repeat(np.arange(users.size), cand.shape[1]).reshape(cand.shape)
        positive_codes = set(zip(np.searchsorted(users, lw["user_idx"].to_numpy()), lw["item_idx"].to_numpy()))
        labels = np.zeros(cand.shape, dtype=np.float32)
        flat_rows, flat_cand = rows[valid], cand[valid]
        labels[valid] = np.fromiter(
            ((r, c) in positive_codes for r, c in zip(flat_rows.tolist(), flat_cand.tolist())), dtype=bool
        )
        log.info("hybrid: features for %d users in %.1fs", users.size, time.perf_counter() - start)

        n_pos_total = lw.groupby("user_idx").size().reindex(users).to_numpy()
        found = labels.sum(axis=1)
        self._diagnostics.update(
            {
                "train_users": int(users.size),
                "candidates_per_user": float(valid.sum(axis=1).mean()),
                "candidate_recall_label_window": float((found / n_pos_total).mean()),
                "users_with_positive_candidate": int((found > 0).sum()),
            }
        )

        # Only groups with at least one positive carry gradient for LambdaMART
        keep_users = np.flatnonzero(found > 0)
        rng.shuffle(keep_users)
        n_valid = max(1, int(len(keep_users) * self.valid_user_fraction))
        valid_users, train_users = np.sort(keep_users[:n_valid]), np.sort(keep_users[n_valid:])

        def matrices(sel):
            m = valid[sel]
            return feats[sel][m], labels[sel][m], np.repeat(np.arange(len(sel)), m.sum(axis=1))

        x_tr, y_tr, q_tr = matrices(train_users)
        x_va, y_va, q_va = matrices(valid_users)
        self.ranker = xgb.XGBRanker(
            objective="rank:ndcg",
            eval_metric="ndcg@10",
            tree_method="hist",
            random_state=self.seed,
            early_stopping_rounds=self.early_stopping_rounds,
            **self.xgb_params,
        )
        start = time.perf_counter()
        self.ranker.fit(x_tr, y_tr, qid=q_tr, eval_set=[(x_va, y_va)], eval_qid=[q_va], verbose=False)
        log.info("hybrid: ranker trained in %.1fs (best iteration %s)",
                 time.perf_counter() - start, self.ranker.best_iteration)

        importance = self.ranker.get_booster().get_score(importance_type="gain")
        named = {self.feature_names[int(k[1:])]: round(v, 3) for k, v in importance.items()}
        self._diagnostics.update(
            {
                "ranker_train_rows": int(len(y_tr)),
                "ranker_positive_rate": float(y_tr.mean()),
                "ranker_best_iteration": int(self.ranker.best_iteration),
                "ranker_best_valid_ndcg@10": float(self.ranker.best_score),
                "feature_gain": dict(sorted(named.items(), key=lambda kv: -kv[1])),
            }
        )

        # Generators for inference see the whole history
        self.gens = self._build_generators(ds)
        self.pop = normalized_recent_popularity(ds)

    # ------------------------------------------------------------------ #
    # Features
    # ------------------------------------------------------------------ #
    def _features(
        self, ds: InteractionDataset, gens: dict[str, Recommender], users: np.ndarray, batch_size: int = 1024
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Candidates and features for warm ``users``.
        Returns (features [n, C, F], candidates [n, C] with -1 padding, valid mask [n, C])."""
        static = _ItemUserStats(ds)
        content = next((g for g in gens.values() if isinstance(g, ContentTfidf)), None)
        feats_out, cand_out = [], []
        for s in range(0, users.size, batch_size):
            batch = users[s : s + batch_size]
            full = {label: g.score(batch) for label, g in gens.items()}
            tops = {label: gens[label].top_k_from_scores(batch, full[label], self.n_candidates)
                    for label in gens}
            cand = union_candidates(list(tops.values()))
            valid = cand >= 0
            safe = np.where(valid, cand, 0)
            row_codes = np.arange(len(batch))[:, None] * ds.n_items + safe

            columns, names = [], []
            for label in gens:
                score = np.take_along_axis(np.asarray(full[label], dtype=np.float32), safe, axis=1)
                retrieved = np.isin(row_codes, np.arange(len(batch))[:, None] * ds.n_items + tops[label])
                columns += [score, _rank_within_rows(score, valid), retrieved.astype(np.float32)]
                names += [f"{label}_score", f"{label}_rank", f"{label}_retrieved"]
            n_sources = sum(columns[i] for i in range(2, len(columns), 3))
            columns.append(n_sources)
            names.append("n_sources")

            item_cols, item_names = static.item_features(safe)
            user_cols, user_names = static.user_features(batch, safe.shape[1])
            pair_cols, pair_names = static.pair_features(batch, safe)
            columns += item_cols + user_cols + pair_cols
            names += item_names + user_names + pair_names
            if content is not None:
                columns.append(_max_history_similarity(content, ds, batch, safe))
                names.append("max_text_sim_to_history")

            feats = np.stack(columns, axis=-1).astype(np.float32)
            feats[~valid] = np.nan
            feats_out.append(feats)
            cand_out.append(cand)
        self.feature_names = names
        cand = np.concatenate(cand_out)
        return np.concatenate(feats_out), cand, cand >= 0

    # ------------------------------------------------------------------ #
    # Inference
    # ------------------------------------------------------------------ #
    def score(self, user_idx: np.ndarray) -> np.ndarray:
        scores = np.tile(1e-3 * self.pop + NON_CANDIDATE_SCORE, (len(user_idx), 1)).astype(np.float32)
        warm = np.flatnonzero(user_idx >= 0)
        if warm.size:
            feats, cand, valid = self._features(self.ds, self.gens, user_idx[warm])
            pred = np.full(cand.shape, -np.inf, dtype=np.float32)
            pred[valid] = self.ranker.predict(feats[valid])
            rows = np.repeat(warm, cand.shape[1]).reshape(cand.shape)
            scores[rows[valid], cand[valid]] = pred[valid]
        cold = np.flatnonzero(user_idx < 0)
        if cold.size:
            scores[cold] = self.pop
        return scores


class _ItemUserStats:
    """History-derived statistics. Nothing here uses product metadata that was
    collected after the cutoff (average ratings and review counts in the
    metadata file are 2023 snapshots, so they are deliberately not used)."""

    def __init__(self, ds: InteractionDataset):
        h = ds.history
        n_items, n_users = ds.n_items, ds.n_users
        items, users = h["item_idx"].to_numpy(), h["user_idx"].to_numpy()
        ts, rating = h["timestamp"].to_numpy(), h["rating"].to_numpy()

        count = np.bincount(items, minlength=n_items).astype(np.float32)
        self.item_log_count = np.log1p(count)
        self.item_recent_pop = normalized_recent_popularity(ds)
        rating_sum = np.bincount(items, weights=rating, minlength=n_items)
        self.item_mean_rating = np.where(count > 0, rating_sum / np.maximum(count, 1), np.nan).astype(np.float32)
        first_ts = np.full(n_items, np.nan)
        np.fmin.at(first_ts, items, ts.astype(np.float64))
        self.item_days_since_first_review = ((ds.cutoff_ms - first_ts) / DAY_MS).astype(np.float32)
        if "date_first_available" in ds.products:
            released = pd.to_datetime(ds.products["date_first_available"])
            cutoff = pd.Timestamp(ds.cutoff_ms, unit="ms")
            self.item_days_since_release = (cutoff - released).dt.days.to_numpy(dtype=np.float64).astype(np.float32)
        else:
            self.item_days_since_release = np.full(n_items, np.nan, dtype=np.float32)

        u_count = np.bincount(users, minlength=n_users).astype(np.float32)
        self.user_log_count = np.log1p(u_count)
        last_ts = np.zeros(n_users)
        np.maximum.at(last_ts, users, ts.astype(np.float64))
        self.user_days_since_last = ((ds.cutoff_ms - last_ts) / DAY_MS).astype(np.float32)
        u_rating = np.bincount(users, weights=rating, minlength=n_users)
        self.user_mean_rating = (u_rating / np.maximum(u_count, 1)).astype(np.float32)

        # Platform and brand codes, and per-user shares
        categories = ds.products["categories"] if "categories" in ds.products else [None] * n_items
        platforms = [platform_of(c) or "" for c in categories]
        self.item_platform = pd.factorize(pd.Series(platforms))[0]
        brands = ds.products["brand"].fillna("") if "brand" in ds.products else pd.Series([""] * n_items)
        self.item_brand = pd.factorize(brands)[0]
        self._user_platform = self._shares(users, self.item_platform[items], n_users)
        self._user_brand = self._shares(users, self.item_brand[items], n_users)
        self._user_count = u_count

    @staticmethod
    def _shares(users: np.ndarray, codes: np.ndarray, n_users: int) -> dict[int, Counter]:
        out: dict[int, Counter] = {}
        for u, c in zip(users.tolist(), codes.tolist()):
            out.setdefault(u, Counter())[c] += 1
        return out

    def item_features(self, cand: np.ndarray) -> tuple[list[np.ndarray], list[str]]:
        return (
            [self.item_log_count[cand], self.item_recent_pop[cand], self.item_mean_rating[cand],
             self.item_days_since_first_review[cand], self.item_days_since_release[cand]],
            ["item_log_count", "item_recent_pop", "item_mean_rating",
             "item_days_since_first_review", "item_days_since_release"],
        )

    def user_features(self, batch: np.ndarray, width: int) -> tuple[list[np.ndarray], list[str]]:
        def wide(v):
            return np.repeat(v[batch][:, None], width, axis=1)

        return (
            [wide(self.user_log_count), wide(self.user_days_since_last), wide(self.user_mean_rating)],
            ["user_log_count", "user_days_since_last", "user_mean_rating"],
        )

    def pair_features(self, batch: np.ndarray, cand: np.ndarray) -> tuple[list[np.ndarray], list[str]]:
        platform_share = np.zeros(cand.shape, dtype=np.float32)
        brand_share = np.zeros(cand.shape, dtype=np.float32)
        for r, u in enumerate(batch.tolist()):
            total = self._user_count[u]
            if total == 0:
                continue
            p_counts, b_counts = self._user_platform.get(u, {}), self._user_brand.get(u, {})
            platform_share[r] = [p_counts.get(c, 0) / total for c in self.item_platform[cand[r]].tolist()]
            brand_share[r] = [b_counts.get(c, 0) / total for c in self.item_brand[cand[r]].tolist()]
        return [platform_share, brand_share], ["user_platform_share", "user_brand_share"]


def _max_history_similarity(
    content: ContentTfidf, ds: InteractionDataset, batch: np.ndarray, cand: np.ndarray
) -> np.ndarray:
    """Highest text similarity between each candidate and any item in the user's
    history. High values flag near-duplicates of something the user already has."""
    out = np.zeros(cand.shape, dtype=np.float32)
    vectors = content.item_vectors
    for r, u in enumerate(batch.tolist()):
        hist = ds.matrix[u].indices
        if hist.size == 0:
            continue
        sims = (vectors[cand[r]] @ vectors[hist].T).toarray()
        out[r] = sims.max(axis=1)
    return out
