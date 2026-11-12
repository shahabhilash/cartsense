# CartSense

An online video game store with a built-in recommendation engine. The store is
built on real product metadata and real review interactions from the
[Amazon Reviews 2023](https://amazon-reviews-2023.github.io/) dataset
(Video Games, 5-core); the recommender powers "Recommended for you",
"Similar products" and "Why this?" explanations.

> Work in progress. Phase 1 (data pipeline) is complete; see the roadmap below.

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
cd ml && pytest
```

Raw and processed data are written to `data/` (git-ignored). See
[docs/data-pipeline.md](docs/data-pipeline.md) for the design and the dataset
findings.

## Roadmap

- [x] P1 Data download, preprocessing, time-based split
- [ ] P2 Evaluation harness and popularity baselines
- [ ] P3 Content-based and collaborative filtering models
- [ ] P4 Neural collaborative filtering and hybrid re-ranker
- [ ] P5 Backend API and database
- [ ] P6 Storefront
- [ ] P7 Evaluation and optimisation
- [ ] P8 Docker, deployment, final README
