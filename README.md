# CartSense

**An explainable recommendation engine for online stores, with a working storefront built on top of it.**

**The problem.** Large marketplaces have teams building personalised
recommendations; small and mid-sized online stores usually show the same
bestsellers to everyone. They also face three practical gaps: most of their
visitors never sign in, recommendations are black boxes that shoppers don't
trust, and there is no simple way to prove that recommendations actually help.

**What CartSense does.** It learns from a store's catalogue and purchase
history, personalises for signed-in **and anonymous** visitors, explains every
suggestion ("Why this?"), retrains on the store's own live behaviour, and
measures its impact with a built-in **A/B test** against a popularity
baseline. It is demonstrated as a video game store (React + FastAPI) on
**814,533 real Amazon reviews**, and exposes a REST API that other stores can
call with an API key.

![CI](https://github.com/shahabhilash/cartsense/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.10%20%7C%203.12-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Highlights

- **Two-stage hybrid recommender.** ALS, item-kNN, TF-IDF and popularity
  each retrieve candidates; an **XGBoost LambdaMART** ranker re-orders them
  with 24 features.
- **+39% NDCG@10** over the best single model on a held-out future time
  period (0.0182 vs 0.0131). Results are reported as measured, including
  that NCF did **not** beat ALS.
- **Leakage-free evaluation.** Global time-based split, a catalogue that only
  contains products released before each cutoff, and ranker labels taken from
  inside the training history.
- **Explainable.** Each recommendation carries structured reasons, e.g.
  *"Similar to 'Metroid Fusion' (shared: samus, metroid prime)"* or
  *"People who reviewed X also reviewed this"*.
- **Personalises without a login.** Guests are recognised by their browsing
  session: after viewing a single product they get related recommendations,
  and that history carries over if they sign up.
- **Learns from live behaviour.** One command (`scripts/retrain.py`) pulls
  real store events (views, clicks, bag additions, wishlists; synthetic events
  are always excluded), retrains the hybrid on dataset + store activity, and
  activates the new model version. Store accounts then get model-based
  recommendations that reflect what they did in the store.
- **Proves its impact.** A built-in A/B test splits visitors (stable hashing
  per visitor) between the model and a popularity control, and reports
  click-through and add-to-bag rate per group with a two-proportion z-test.
- **Production-style serving.** Batch-precomputed recommendations, a
  lightweight API with no ML runtime, impression and click logging, and CTR
  per model version on an analytics dashboard.
- **A store people can actually use.** Live search suggestions, recommendation
  rails with labelled "Why this?" reasons, wishlist, a bag with a demo
  checkout, recently viewed items, an account page with review history, and an
  insights dashboard. It is responsive down to phone width.
- **Reusable REST API.** Versioned (`/api/v1`) and validated, with an
  API-key endpoint for external stores.

## Results

Offline evaluation on the **test period (2021-07 → 2023-09)**: 25,013 users
ranked against the full catalogue of 23,238 products available at the cutoff.

| Model | NDCG@10 | Recall@10 | MAP@10 | Coverage@10 |
|---|---:|---:|---:|---:|
| **Hybrid (candidates + XGBoost ranker)** | **0.0182** | **0.0287** | **0.0101** | 0.0874 |
| ALS + popularity prior | 0.0131 | 0.0211 | 0.0066 | 0.0751 |
| TF-IDF content + popularity prior | 0.0123 | 0.0219 | 0.0056 | 0.1252 |
| Platform-aware popularity | 0.0124 | 0.0186 | 0.0069 | 0.0085 |
| Recent popularity | 0.0114 | 0.0207 | 0.0049 | 0.0008 |
| NCF (NeuMF) + popularity prior | 0.0111 | 0.0175 | 0.0055 | 0.0499 |
| Random | 0.0002 | 0.0003 | 0.0001 | 1.0000 |

All hyperparameters were chosen on the validation period; the test period was
run once. Absolute values are low because every model ranks the full
catalogue rather than one positive against sampled negatives. Full tables,
the tuning record and the analysis are in
[docs/evaluation.md](docs/evaluation.md).

## Architecture

```mermaid
flowchart LR
    A[Amazon Reviews 2023<br/>Video Games 5-core] --> B[Data pipeline<br/>Parquet · cleaning · time split]
    B --> C[Base models<br/>popularity · TF-IDF · item-kNN · ALS · NCF]
    C --> D[Hybrid ranker<br/>XGBoost LambdaMART]
    D --> E[Export<br/>recs + reasons · similar items]
    B --> F[Evaluation<br/>MLflow]
    E --> G[(PostgreSQL)]
    G <--> H[FastAPI /api/v1]
    H <--> I[React store<br/>Vite]
    J[External store] -- API key --> H
```

Recommendation strategies, in order: **precomputed** hybrid output for
shoppers the model was trained on → **session similarity** for new accounts
and guests (products similar to what they viewed, clicked or saved) →
**popularity** for visitors with no signal. When the A/B test is on, the
control group always gets popularity. Store events feed back into the next
retrain. Details and design tradeoffs: [docs/architecture.md](docs/architecture.md).

## Tech stack

| Layer | Tools |
|---|---|
| Machine learning | Python, pandas, PyArrow, scikit-learn (TF-IDF), implicit (ALS), PyTorch (NCF), XGBoost (LambdaMART), MLflow |
| Backend | FastAPI, SQLAlchemy 2, Pydantic, PostgreSQL / SQLite, JWT, bcrypt |
| Frontend | React 18, TypeScript, Vite, React Router, Tailwind CSS, Recharts |
| Quality and ops | pytest, Vitest, Testing Library, GitHub Actions, Docker, docker-compose |

## Project structure

```
cartsense/
├── ml/                     # Python package cartsense_ml
│   ├── cartsense_ml/
│   │   ├── data/           # download, Parquet conversion, cleaning, stats, time split, dataset encoding
│   │   ├── models/         # popularity, content, collaborative, ncf, hybrid, registry
│   │   ├── eval/           # ranking metrics, evaluation harness
│   │   ├── experiments/    # config-driven runner + comparison tables
│   │   ├── explain.py      # "Why this?" reasons
│   │   └── export.py       # production training + export for the API
│   ├── configs/            # YAML experiment configs (data, baselines, tuning, final models)
│   └── tests/
├── services/api/           # FastAPI app, routers, data loader, tests
├── apps/web/               # React (Vite) storefront and dashboard
├── docs/                   # architecture, data pipeline, evaluation, deployment
├── reports/                # generated dataset stats and evaluation results
└── docker-compose.yml
```

## API overview

Interactive documentation is served at `/docs`. Main endpoints (prefix `/api/v1`):

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/products?q=&platform=&sort=&page=` | Browse and search the catalogue |
| GET | `/products/{id}` · `/products/{id}/similar` | Product details and similar products |
| POST | `/auth/register` · `/auth/login` · `/auth/demo` | Accounts and demo personas (JWT) |
| GET | `/recommendations?k=&surface=` | Recommendations with reasons and impression ids; guests send `X-Session-Id` |
| POST | `/events` | Log views, clicks, searches, add-to-cart |
| GET/POST/DELETE | `/me/wishlist` | Wishlist |
| GET | `/analytics/overview` | Store activity, CTR per model version, A/B test results, offline metrics |
| GET | `/partner/recommendations/{user_id}` | For external stores, authenticated with `X-API-Key` |

Errors use one format: `{"error": {"code": 404, "message": "..."}}`.

## Data and attribution

CartSense uses the Amazon Reviews 2023 dataset from the McAuley Lab, UC San Diego:

> Yupeng Hou, Jiacheng Li, Zhankui He, An Yan, Xiusi Chen, Julian McAuley.
> *Bridging Language and Items for Retrieval and Recommendation.*
> arXiv:2403.03952, 2024.

- **Use:** the dataset is used for non-commercial, educational purposes.
- **Not redistributed:** this repository does not contain the dataset. It is
  downloaded from the official source, and raw and processed files are
  git-ignored. Committed reports contain only aggregate statistics.
- **Images:** product images are hosted by Amazon and are **not shown** unless
  `CARTSENSE_SHOW_PRODUCT_IMAGES=true`.
- **Users and brands:** user IDs are anonymised by the dataset authors.
  Product names and brands belong to their respective owners.
- **No synthetic data:** clicks, views and wishlists do not exist in the
  dataset. The store records real ones only (`is_synthetic = false`).
  Synthetic data is never used for training or metrics.

## Known limitations and next steps

- **No real store has used it yet.** The A/B test and the feedback retrain
  work end to end, but the numbers they produce so far come from test
  traffic, so there is no measured real-world sales lift to report.
- **Retraining is run on demand** (`scripts/retrain.py`), not on a schedule,
  and takes about 30–35 minutes on a laptop CPU.
- **Model versions** are tracked in MLflow runs and in the database, but not
  registered in the MLflow Model Registry.
- **Database:** the tests run on SQLite. PostgreSQL is supported through
  `DATABASE_URL` but has not been tested in CI. The schema is created on
  startup and new columns are added automatically; there is no full
  migration tool yet.
- **Docker:** the Docker setup has not been run end to end yet.
- **Retrieval is the bottleneck:** only about 18% of the products users went
  on to review are among their candidates. Better retrieval would help more
  than a better ranker.
- **Speed:** full-catalogue top-k selection takes 15–84 s per offline
  evaluation run and could be made faster.

## License

Code: [MIT](LICENSE). The dataset is subject to its own terms and is not
included.
