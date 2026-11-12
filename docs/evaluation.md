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

## Neural collaborative filtering and the hybrid ranker (Phase 4)

| Model | What it does |
|---|---|
| `ncf_d32_e5_pop1` | NeuMF (GMF + MLP, PyTorch): 32-dim embeddings, MLP 64→32→16, 4 sampled negatives per positive, BCE loss, 5 epochs, plus the popularity prior (weight 1.0) |
| `hybrid_c100` | Each of ALS+pop, item-kNN+pop, content+pop and recent popularity retrieves its top 100. The union (about 200 per user) is re-ranked by XGBoost LambdaMART (`rank:ndcg`) on 24 features |

### How the hybrid is trained without leakage

The ranker needs labels from *after* the data its candidate models saw, just
as in production. Within the history of each stage:

1. The last 11% of the history (by time) becomes a label window. This is
   about the same size as the evaluation window.
2. The candidate models are fitted on the history before that window, and
   candidates and features are built for the users active in it.
   Label = 1 if the user reviewed the candidate in the window.
3. XGBoost is trained on those groups, with early stopping on 10% of the
   users held out.
4. The candidate models are refitted on the full history for inference.

The val or test window is never used in any of these steps.

**Features** (all computed from the history up to the cutoff):
* **Per candidate model:** its score, the candidate's rank by that score, and
  whether that model retrieved it; plus how many models retrieved it.
* **Item:** review count, recent popularity, mean rating, days since first
  review, days since release.
* **User:** activity, days since last review, mean rating.
* **User-item:** the user's share of history on the item's platform and on
  its brand, and the highest text similarity to anything already in the
  history (to catch near-duplicates).

The metadata's `average_rating` and `rating_number` are 2023 snapshots, so
they would leak the future and are not used.

### Tuning (val only)

See [`reports/tuning_p4_val.md`](../reports/tuning_p4_val.md).

* **NCF overfits quickly.** Training loss keeps falling (0.386 after epoch 1,
  0.030 after epoch 20), but val NDCG@10 peaks at 5 epochs (0.0179) and
  drops at 20 (0.0167). A wider model (64 dims) and L2 weight decay (1e-5)
  did not help (0.0173 and 0.0178). Without the popularity prior, NCF
  reaches only 0.0106.
* **Hybrid candidate depth:** 100 candidates per model beat 50 (0.0271 vs
  0.0261). The label-window candidate recall rose from 0.139 to 0.198. Deeper
  lists and NCF as a fifth candidate model were not evaluated, to keep
  run time down. They are listed as future work.

### Results (all users)

| Model | NDCG@10 val | NDCG@10 test | Recall@10 test | MAP@10 test | Coverage@10 test |
|---|---:|---:|---:|---:|---:|
| **hybrid_c100** | **0.0271** | **0.0182** | **0.0287** | **0.0101** | 0.0874 |
| als_pop | 0.0196 | 0.0131 | 0.0211 | 0.0066 | 0.0751 |
| content_tfidf_pop | 0.0186 | 0.0123 | 0.0219 | 0.0056 | 0.1252 |
| category_popular | 0.0157 | 0.0124 | 0.0186 | 0.0069 | 0.0085 |
| recent_popular | 0.0177 | 0.0114 | 0.0207 | 0.0049 | 0.0008 |
| ncf_d32_e5_pop1 | 0.0179 | 0.0111 | 0.0175 | 0.0055 | 0.0499 |

### Observations

* **The hybrid is the best model on every accuracy metric, on both stages.**
  On test, NDCG@10 is +39% over the best single model, `als_pop` (0.0182 vs
  0.0131), and +47% over the best Phase 2 baseline, `category_popular`
  (0.0124). Recall@10 is +36% (0.0287 vs 0.0211). For warm users the test
  NDCG@10 is 0.0186 vs 0.0127.
* **NCF does not beat ALS.** On test it is below `als_pop` (0.0111 vs 0.0131)
  and slightly below plain `recent_popular` (0.0114). With a median of 6
  interactions per user, the extra capacity of the MLP mostly overfits; the
  linear factorisation in ALS generalises better. This matches published
  re-evaluations of NCF against well-tuned matrix factorisation. NCF is
  therefore not used as a candidate model in the final hybrid.
* **What the ranker relies on:** the features with the highest gain in the
  test-stage ranker are item freshness (days since first review, days since
  release), content rank and score, review count, popularity rank, the
  number of models that retrieved the item, and the user's brand share. The
  ranker learns *when* to trust the personal signal and when "new and
  popular" matters more, which the fixed popularity weight of Phase 3 could
  not do.
* **Candidate recall is now the ceiling.** In the test-stage label window,
  only 18.0% of the items users went on to review were among their roughly
  200 candidates. Better retrieval would lift the hybrid more than a better
  ranker would.
* **Cold users** get recent popularity in every model, so their numbers are
  identical across models (test NDCG@10 0.0157).
* **Cost:** a hybrid fit (two rounds of candidate-model training, features
  for about 24k users, XGBoost) takes about 6 minutes on val and about
  13 minutes on test on a laptop CPU. This is an offline batch job; serving
  reads precomputed results.

### Reproducibility note

All Phase 4 results record code revision `b95f729` (clean tree). The val
files in `reports/results/val/` for `ncf_d32_e5_pop1` and `hybrid_c100` are
copies of the tuning-run files, which have the same configuration and code.
The test stage was run once, with `ml/configs/p4_models.yaml`.
