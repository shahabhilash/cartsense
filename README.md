# CartSense

An online video game store with a built-in, explainable recommendation
engine. The store runs on real product metadata and real review interactions
from the [Amazon Reviews 2023](https://amazon-reviews-2023.github.io/)
dataset (Video Games, 5-core). The recommender powers "Recommended for you",
"Similar products" and a "Why this?" explanation on every recommendation.

**Headline result (held-out test period, NDCG@10):** two-stage hybrid
(candidate generation + XGBoost LambdaMART) **0.0182**, vs 0.0131 for the
best single model (ALS), a **+39%** improvement. NCF did not beat ALS.
Every number comes from the evaluation scripts; see
[docs/evaluation.md](docs/evaluation.md).

## What is inside

| Path | Contents |
|---|---|
| `ml/` | Python package `cartsense_ml`: streaming data pipeline, time-based split, metrics, popularity / TF-IDF / item-kNN / ALS / NCF models, hybrid ranker, explanations, MLflow-tracked experiments, production export |
| `services/api/` | FastAPI + SQLAlchemy REST API (`/api/v1`): catalogue, search, auth, demo personas, wishlist, events, recommendations with impression logging, analytics, partner API with API keys |
| `apps/web/` | Next.js + TypeScript + Tailwind + Recharts store: home, browse/search, product pages, wishlist, sign-in, analytics dashboard |
| `docs/` | [Architecture](docs/architecture.md), [data pipeline](docs/data-pipeline.md), [evaluation and results](docs/evaluation.md), [deployment](docs/deployment.md) |
| `reports/` | Generated dataset and evaluation reports (never edited by hand) |

## ML in one paragraph

814,533 real reviews from 94,762 users on 25,611 products, split by global
time cutoffs (train to 2019-12, val to 2021-07, test to 2023-09). Products
released after a cutoff cannot be recommended at that cutoff. Models are
tuned on val and run once on test. The hybrid retrieves about 200
candidates per user from ALS, item-kNN, TF-IDF and popularity, then
re-ranks them with 24 history-only features. Its training labels come from a
window inside the training history, so no evaluation data leaks in.
New users get recommendations from their first product views (similar-item
lookup); guests get recent popularity.

## Quick start

See [docs/deployment.md](docs/deployment.md) for the full guide (local,
Docker, Render + Vercel).

```bash
python -m venv .venv && .venv/Scripts/activate
pip install -e "ml[dev]" -e "services/api[dev]"
python -m cartsense_ml.data.pipeline
python -m cartsense_ml.export --out artifacts/export
cd services/api && python -m app.load_data --export-dir ../../artifacts/export --results-dir ../../reports/results/test
uvicorn app.main:app --port 8000
# in another terminal
cd apps/web && npm install && npm run dev
```

Tests: `cd ml && pytest` · `cd services/api && pytest` · `cd apps/web && npm test`

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
statistics. Product images are hosted by Amazon and are not shown unless
`CARTSENSE_SHOW_PRODUCT_IMAGES=true`. User IDs in the dataset are anonymised
by its authors. Product names and brands belong to their respective owners.

## Status and limitations

- [x] P1–P4 data pipeline, baselines, content-based + CF, NCF + hybrid
- [x] P5 API and database (SQLite locally and in tests; PostgreSQL via `docker-compose.yml`)
- [x] P6 storefront
- [ ] P7 optimisation: not done as a separate phase. Open items: faster
      full-catalogue top-k, tuning the popularity half-life, deeper candidate
      lists, an automated retrain from store events
- [x] P8 Dockerfiles, compose file, deployment guide. The Docker setup is
      written but was not run in the development environment (Docker was
      not installed there)
- Database schema is created with `create_all`; there are no migrations yet.
