"""Neural Collaborative Filtering (NeuMF, He et al. 2017) in PyTorch.

Architecture
    GMF branch:  p_u * q_i                       (element-wise product, dim d)
    MLP branch:  MLP([p'_u ; q'_i])              (layers e.g. 64 -> 32 -> 16)
    Output:      w . [GMF ; MLP] + b             (a logit)

    The two branches use separate embeddings, as in the paper.

Training
    Implicit feedback: each observed (user, item) pair is a positive; for each
    positive, ``negatives`` items are sampled uniformly from the products the
    user has not interacted with. Loss is binary cross-entropy on the logit.
    Sampling and initialisation are seeded.

Scoring the full catalogue
    Scoring all ~25k items for every user through an MLP is the expensive part.
    The first MLP layer is linear in the concatenated embeddings,
    ``W [p ; q] = W_u p + W_i q``, so the user and item halves are projected
    once and only added per pair. The remaining layers run on
    (users x items x hidden) blocks of a bounded size.

Users without history get recent popularity; a popularity prior with weight
``popularity_weight`` is added for everyone, as in the other models.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import numpy as np

from cartsense_ml.data.dataset import InteractionDataset
from cartsense_ml.models.base import Recommender
from cartsense_ml.models.popularity import normalized_recent_popularity

log = logging.getLogger(__name__)


def _build_network(n_users: int, n_items: int, dim: int, layers: list[int]):
    import torch
    from torch import nn

    class NeuMF(nn.Module):
        def __init__(self):
            super().__init__()
            self.user_gmf = nn.Embedding(n_users, dim)
            self.item_gmf = nn.Embedding(n_items, dim)
            self.user_mlp = nn.Embedding(n_users, layers[0] // 2)
            self.item_mlp = nn.Embedding(n_items, layers[0] // 2)
            mlp = []
            for d_in, d_out in zip(layers[:-1], layers[1:]):
                mlp += [nn.Linear(d_in, d_out), nn.ReLU()]
            self.mlp = nn.Sequential(*mlp)
            self.out = nn.Linear(dim + layers[-1], 1)
            for emb in (self.user_gmf, self.item_gmf, self.user_mlp, self.item_mlp):
                nn.init.normal_(emb.weight, std=0.01)

        def forward(self, users, items):
            gmf = self.user_gmf(users) * self.item_gmf(items)
            mlp = self.mlp(torch.cat([self.user_mlp(users), self.item_mlp(items)], dim=-1))
            return self.out(torch.cat([gmf, mlp], dim=-1)).squeeze(-1)

    return NeuMF()


class NCF(Recommender):
    name = "ncf"

    def __init__(
        self,
        dim: int = 32,
        layers: list[int] | None = None,
        negatives: int = 4,
        epochs: int = 10,
        batch_size: int = 4096,
        lr: float = 1e-3,
        weight_decay: float = 0.0,
        popularity_weight: float = 1e-3,
        num_threads: int | None = None,
        seed: int = 42,
    ):
        super().__init__(seed=seed)
        self.dim = dim
        self.layers = list(layers or [64, 32, 16])
        if self.layers[0] % 2:
            raise ValueError("the first MLP layer width must be even (user and item halves)")
        self.negatives = negatives
        self.epochs = epochs
        self.batch_size = batch_size
        self.lr = lr
        self.weight_decay = weight_decay
        self.popularity_weight = popularity_weight
        self.num_threads = num_threads
        self.epoch_losses: list[float] = []

    def params(self) -> dict[str, Any]:
        return {
            **super().params(),
            "dim": self.dim,
            "layers": self.layers,
            "negatives": self.negatives,
            "epochs": self.epochs,
            "batch_size": self.batch_size,
            "lr": self.lr,
            "weight_decay": self.weight_decay,
            "popularity_weight": self.popularity_weight,
        }

    def diagnostics(self) -> dict[str, Any]:
        return {"epoch_losses": [round(x, 5) for x in self.epoch_losses]}

    # ------------------------------------------------------------------ #
    def _sample_negatives(self, users: np.ndarray, rng: np.random.Generator) -> np.ndarray:
        """Uniform negatives, re-drawn where they hit an item the user has seen."""
        matrix = self.ds.matrix
        items = rng.integers(0, self.ds.n_items, size=users.size)
        for _ in range(10):  # a handful of rounds removes virtually all collisions
            hit = np.asarray(matrix[users, items]).ravel() > 0
            if not hit.any():
                break
            items[hit] = rng.integers(0, self.ds.n_items, size=int(hit.sum()))
        return items

    def _fit(self, ds: InteractionDataset) -> None:
        import torch

        if self.num_threads:
            torch.set_num_threads(self.num_threads)
        torch.manual_seed(self.seed)
        rng = np.random.default_rng(self.seed)

        self.net = _build_network(ds.n_users, ds.n_items, self.dim, self.layers)
        optimizer = torch.optim.Adam(self.net.parameters(), lr=self.lr, weight_decay=self.weight_decay)
        loss_fn = torch.nn.BCEWithLogitsLoss()

        coo = ds.matrix.tocoo()
        pos_users, pos_items = coo.row.astype(np.int64), coo.col.astype(np.int64)
        self.epoch_losses = []
        self.net.train()
        for epoch in range(self.epochs):
            start = time.perf_counter()
            neg_users = np.repeat(pos_users, self.negatives)
            neg_items = self._sample_negatives(neg_users, rng)
            users = np.concatenate([pos_users, neg_users])
            items = np.concatenate([pos_items, neg_items])
            labels = np.concatenate([np.ones(pos_users.size), np.zeros(neg_users.size)]).astype(np.float32)
            order = rng.permutation(users.size)
            users_t = torch.from_numpy(users[order])
            items_t = torch.from_numpy(items[order])
            labels_t = torch.from_numpy(labels[order])

            total = 0.0
            for s in range(0, users_t.numel(), self.batch_size):
                optimizer.zero_grad()
                logits = self.net(users_t[s : s + self.batch_size], items_t[s : s + self.batch_size])
                loss = loss_fn(logits, labels_t[s : s + self.batch_size])
                loss.backward()
                optimizer.step()
                total += loss.item() * logits.numel()
            self.epoch_losses.append(total / users_t.numel())
            log.info("ncf epoch %d/%d loss=%.4f (%.1fs)", epoch + 1, self.epochs,
                     self.epoch_losses[-1], time.perf_counter() - start)

        self.net.eval()
        self._prepare_scoring()
        self.pop = normalized_recent_popularity(ds)

    def _prepare_scoring(self) -> None:
        """Pre-project embeddings for fast full-catalogue scoring."""
        import torch

        with torch.no_grad():
            first = self.net.mlp[0]
            half = self.layers[0] // 2
            w_user, w_item = first.weight[:, :half], first.weight[:, half:]
            self._u_proj = (self.net.user_mlp.weight @ w_user.T).contiguous()  # users x h1
            self._i_proj = (self.net.item_mlp.weight @ w_item.T + first.bias).contiguous()  # items x h1
            self._u_gmf = self.net.user_gmf.weight.detach()
            self._i_gmf = self.net.item_gmf.weight.detach()
            out_w = self.net.out.weight.squeeze(0)
            self._w_gmf, self._w_mlp = out_w[: self.dim], out_w[self.dim :]
            self._b_out = self.net.out.bias

    def _logits(self, user_idx: np.ndarray, block_elems: int = 8_000_000) -> np.ndarray:
        """Logits for warm users against every item, shape (n_users, n_items)."""
        import torch

        n_items = self.ds.n_items
        h1 = self.layers[0]
        rows_per_block = max(1, block_elems // (n_items * h1))
        out = np.empty((len(user_idx), n_items), dtype=np.float32)
        rest = self.net.mlp[1:]  # everything after the first Linear
        with torch.no_grad():
            gmf_item = self._i_gmf * self._w_gmf  # fold the output weights into the items
            for s in range(0, len(user_idx), rows_per_block):
                u = torch.from_numpy(user_idx[s : s + rows_per_block])
                gmf = self._u_gmf[u] @ gmf_item.T  # (b, items)
                hidden = self._u_proj[u][:, None, :] + self._i_proj[None, :, :]  # (b, items, h1)
                mlp = rest(hidden) @ self._w_mlp  # (b, items)
                out[s : s + len(u)] = (gmf + mlp + self._b_out).numpy()
        return out

    def score(self, user_idx: np.ndarray) -> np.ndarray:
        scores = np.tile(self.popularity_weight * self.pop, (len(user_idx), 1))
        warm = np.flatnonzero(user_idx >= 0)
        if warm.size:
            logits = self._logits(user_idx[warm])
            # sigmoid keeps the model term in [0, 1], on the same scale as the prior
            scores[warm] += 1.0 / (1.0 + np.exp(-logits))
        cold = np.flatnonzero(user_idx < 0)
        if cold.size:
            scores[cold] = self.pop
        return scores

    def score_pairs(self, user_idx: np.ndarray, item_idx: np.ndarray) -> np.ndarray:
        """Probabilities for explicit (user, item) pairs; users must be warm."""
        import torch

        with torch.no_grad():
            logits = self.net(torch.from_numpy(np.asarray(user_idx, np.int64)),
                              torch.from_numpy(np.asarray(item_idx, np.int64)))
        return (1.0 / (1.0 + np.exp(-logits.numpy()))).astype(np.float32)
