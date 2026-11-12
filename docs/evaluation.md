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
