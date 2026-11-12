# Offline evaluation (Phase 2 onwards)

The complete, generated comparison tables are
[`reports/results_val.md`](../reports/results_val.md) and
[`reports/results_test.md`](../reports/results_test.md); per-model JSON files
are in `reports/results/<stage>/`, and every run is also logged to MLflow.
Numbers quoted on this page are copied from those files.

## Protocol

| Stage | Model is fitted on | Evaluated on | Cutoff |
|---|---|---|---|
| `val` | train | val | 2019-12-10 |
| `test` | train + val | test | 2021-07-09 |

Hyperparameters are chosen on `val`. `test` is run once per model, after its
configuration is fixed.

* **Ground truth:** every product a user reviewed in the evaluation window
  (implicit feedback, binary relevance).
* **Ranking:** the full catalogue available at the cutoff; no negative sampling.
  Products the user already reviewed before the cutoff are excluded.
* **Catalogue at the cutoff:** a product can be recommended only if it has a
  review before the cutoff or a "Date First Available" on or before it.
  Products released later still count as relevant, so no model can reach
  perfect recall. The **oracle recall** in each table is that ceiling:
  0.7958 (val) and 0.6842 (test) at K = 10.
* **Segments:** warm users have history before the cutoff, cold users do not.
  Both are reported, because the two need different strategies.
* **Metrics:** Precision, Recall, NDCG, MAP and HitRate at K = 10 and 20, plus
  catalogue coverage (share of recommendable products appearing in anyone's
  top K). Definitions are in `ml/cartsense_ml/eval/metrics.py`, and the unit
  tests check them against hand-computed examples.

Run it with:

```bash
python -m cartsense_ml.experiments.run --config ml/configs/baselines.yaml --stage val
python -m cartsense_ml.experiments.run --config ml/configs/baselines.yaml --stage test
mlflow ui --backend-store-uri sqlite:///mlruns.db      # browse runs at http://127.0.0.1:5000
```

## Baselines (Phase 2)

| Model | What it does |
|---|---|
| `random` | Uniform random ranking (seeded); the floor |
| `most_popular` | Count of reviews per product |
| `recent_popular` | Reviews weighted by `0.5 ** (age / 180 days)` from the cutoff |
| `category_popular` | `recent_popular` re-weighted by the user's share of history on each platform (PC, Switch, ...); cold users fall back to `recent_popular` |

NDCG@10, all users:

| Model | val | test |
|---|---:|---:|
| category_popular | 0.0157 | 0.0124 |
| recent_popular | 0.0177 | 0.0114 |
| most_popular | 0.0110 | 0.0044 |
| random | 0.0002 | 0.0002 |

### Observations

* **Recency matters most.** Weighting by recency beats raw counts on both
  stages: NDCG@10 rises from 0.0110 to 0.0177 on val and from 0.0044 to 0.0114
  on test. All-time counts favour games that were popular years earlier.
* **Platform personalisation is mixed.** On warm users, `category_popular` is
  below `recent_popular` on val (NDCG@10 0.0136 vs 0.0160) but above it on
  test (0.0118 vs 0.0107), and its recall@10 is slightly lower on both. Its
  clear win is catalogue coverage: 0.0103 vs 0.0010 at K = 10 on val, about
  ten times more distinct products shown. Platform is too coarse a signal to
  rank well on its own; it will be used as a feature for the hybrid ranker
  rather than as a model.
* **The half-life (180 days) was not tuned.** Selecting it on val is a cheap
  improvement, left for Phase 7.
* **Absolute values are low,** as expected for full-catalogue ranking over
  about 21–23k products with a sparse 5-core dataset (median 6 interactions
  per user). The useful comparison is relative to these baselines and to the
  oracle ceiling, not to papers that rank 1 positive against 99 sampled
  negatives.
* **Recommendation time** for about 25–30k users is under 1.5 minutes per
  model on a laptop CPU (15–84 s in these runs; `random` is the slowest). It is
  dominated by full-catalogue top-k selection and will be profiled in
  Phase 7. Serving does not depend on it: recommendations are
  precomputed in batch.

## Content-based and collaborative filtering (Phase 3)

| Model | What it does |
|---|---|
| `content_tfidf` | TF-IDF over title, brand, categories, features and description; the user profile is the recency-weighted mean of history item vectors; score = cosine similarity |
| `item_knn` | Item-item cosine similarity on the binary interaction matrix, shrinkage 100, top-50 neighbours per item |
| `als` | Implicit-feedback matrix factorisation (`implicit` library), 128 factors, regularisation 1.0, alpha 40 |
| `*_pop` | The same model plus recent popularity (scaled to [0, 1]) with weight 1.0 |

All personalised models serve users without history with recent popularity,
so their cold-user metrics equal `recent_popular`'s.

### How the settings were chosen

All tuning used **validation only**. The full search (33 configurations) is in
[`reports/tuning_p3_val.md`](../reports/tuning_p3_val.md).

1. Model parameters with a negligible popularity prior: kNN neighbours ×
   shrinkage, ALS factors × regularisation × alpha, content history
   half-life. Higher shrinkage (100 > 10) and higher ALS alpha (40 > 10)
   helped. Going further (shrinkage 300, alpha 100) did not change NDCG@10
   meaningfully.
2. Popularity-prior weight in {0.05, 0.2, 0.5, 1, 2, 4} on the best setting
   of each model. Every model peaked at weight 1 (ALS: 0.0196 at 1, 0.0190 at
   2, 0.0183 at 4), so the optimum is inside the grid, not at its edge. For
   item-kNN, weights 0.5 and 1 are effectively tied (0.01800 vs 0.01804); the
   selection rule (highest val NDCG@10) picks 1, although 0.5 gives more than
   twice the coverage (0.0483 vs 0.0201).

The test stage was run once, with the chosen settings only.

### Results, NDCG@10 (all users)

| Model | val | test |
|---|---:|---:|
| als_pop | 0.0196 | 0.0131 |
| content_tfidf_pop | 0.0186 | 0.0123 |
| item_knn_pop | 0.0180 | 0.0116 |
| recent_popular (Phase 2) | 0.0177 | 0.0114 |
| category_popular (Phase 2) | 0.0157 | 0.0124 |
| als | 0.0130 | 0.0092 |
| item_knn | 0.0124 | 0.0080 |
| content_tfidf | 0.0104 | 0.0075 |

### Observations

* **On their own, CF and content models lose to popularity.** Without the
  prior, ALS, item-kNN and TF-IDF all score below `recent_popular` on both
  stages. With a global time split, much of what users review next is
  simply what is new and popular at that moment, and a model trained only
  on co-occurrence or text has no notion of "now".
* **Personal signal plus popularity is the best combination.** `als_pop` is
  the best model on both stages: +11% NDCG@10 over `recent_popular` on val
  (0.0196 vs 0.0177) and +15% on test (0.0131 vs 0.0114). On test the margin
  over the best Phase 2 model, `category_popular` (0.0124), is smaller (+6%),
  and on MAP@10 `category_popular` is slightly ahead (0.0069 vs 0.0066). The
  gains are real but modest, and they do not dominate every metric.
* **Content has the best test recall.** `content_tfidf_pop` has the highest
  test Recall@10 (0.0219, vs 0.0211 for `als_pop`) and shows a far wider
  part of the catalogue (coverage@10 0.1252 vs 0.0751). Unlike CF, it can
  score products that have no reviews yet.
* **Content similarity finds substitutes, not complements.** In a manual check,
  a user who bought one HD AV cable was recommended two more near-identical
  cables. The text match is correct, but it is a poor recommendation. This is
  a known weakness of pure content models. The Phase 4 ranker gets
  "is the candidate the same kind of product as something already owned?" as
  a feature so it can learn to down-weight these.
* **Val-to-test drop.** Every model scores lower on test than on val, partly
  because the test window has a lower oracle ceiling (0.6842 vs 0.7958
  recall@10): more of what people reviewed was released after the cutoff.

### Explanations

`cartsense_ml/explain.py` turns each recommendation into structured
reasons, taken from the signal the model actually used. Real example from
the validation dataset, for a user whose history includes
*Assassin's Creed: Brotherhood - PC*. Item-kNN recommends
*Assassin's Creed: Revelations* with the reasons:

* `also_reviewed_with`: People who reviewed "Assassin's Creed: Brotherhood - PC" also reviewed this
* `popular_on_platform`: Popular on Legacy Systems, 75% of what you have reviewed

Users without history receive a popularity reason ("Trending: #N in the store").

### Reproducibility note

The final Phase 3 runs record git revision `faec0f1-dirty`. The only
uncommitted change at the time was an edit to `README.md` (dataset
attribution); the model code is exactly commit `faec0f1`. The tuning runs in
`reports/results/tuning_p3/` were produced on the same code before it was
committed, and are marked dirty for the same reason.
