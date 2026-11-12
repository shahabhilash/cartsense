# CartSense

An online video game store with a built-in recommendation engine. The store is
built on real product metadata and real review interactions from the
[Amazon Reviews 2023](https://amazon-reviews-2023.github.io/) dataset
(Video Games, 5-core); the recommender powers "Recommended for you",
"Similar products" and "Why this?" explanations.

> Work in progress. Phases 1–3 (data pipeline, evaluation, baselines, content-based and collaborative filtering) are complete; see the roadmap below.

## Repository layout

| Path | Contents |
|---|---|
| `ml/` | Data processing, training, evaluation and inference (Python package `cartsense_ml`) |
| `docs/` | Design notes and results |
| `reports/` | Generated dataset and evaluation reports (never edited by hand) |

## Quick start (data pipeline)

```bash
python -m venv .venv
.venv/Scripts/activate            # Windows; use .venv/bin/activate elsewhere
pip install -e "ml[dev]"
python -m cartsense_ml.data.pipeline --config ml/configs/data.yaml
python -m cartsense_ml.experiments.run --config ml/configs/baselines.yaml --stage val
cd ml && pytest
```

Raw and processed data are written to `data/` (git-ignored). See
[docs/data-pipeline.md](docs/data-pipeline.md) for the design and the dataset
findings, and [docs/evaluation.md](docs/evaluation.md) for the evaluation
protocol and results.

## Data and attribution

CartSense uses the Amazon Reviews 2023 dataset, collected and released by the
McAuley Lab at UC San Diego:

> Yupeng Hou, Jiacheng Li, Zhankui He, An Yan, Xiusi Chen, Julian McAuley.
> *Bridging Language and Items for Retrieval and Recommendation.*
> arXiv:2403.03952, 2024.

The dataset is used here for non-commercial, educational purposes. This
repository does **not** redistribute it: raw and processed files are
git-ignored and are downloaded from the official source by
`cartsense_ml.data.pipeline`. Committed reports contain only aggregate
statistics (counts, distributions, metric values). They contain no user
identifiers, review text or product images. User IDs in the dataset are
already anonymised by its authors. Product names and brands belong to their
respective owners.

## Roadmap

- [x] P1 Data download, preprocessing, time-based split
- [x] P2 Evaluation harness and popularity baselines
- [x] P3 Content-based and collaborative filtering models
- [ ] P4 Neural collaborative filtering and hybrid re-ranker
- [ ] P5 Backend API and database
- [ ] P6 Storefront
- [ ] P7 Evaluation and optimisation
- [ ] P8 Docker, deployment, final README
