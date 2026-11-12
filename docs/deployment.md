# Running and deploying CartSense

## 1. Produce the ML export (once per retrain)

```bash
python -m venv .venv && .venv/Scripts/activate        # Windows; .venv/bin/activate elsewhere
pip install -e "ml[dev]"
python -m cartsense_ml.data.pipeline                  # download + preprocess (about 1 minute)
python -m cartsense_ml.export --out artifacts/export --demo-users 2000   # about 15-20 minutes on CPU
```

## 2. Local development (no Docker needed)

```bash
# API (SQLite by default)
cd services/api
pip install -e ".[dev]"
python -m app.load_data --export-dir ../../artifacts/export --results-dir ../../reports/results/test
uvicorn app.main:app --reload --port 8000            # docs at http://localhost:8000/docs

# Store (React + Vite)
cd apps/web
npm install
npm run dev                                          # http://localhost:3000
```

## 3. Local stack with Docker (PostgreSQL)

```bash
cp .env.example .env              # set CARTSENSE_JWT_SECRET and POSTGRES_PASSWORD
docker compose up --build -d
docker compose exec api python -m app.load_data --export-dir /data/export
```

The results directory is not mounted in the container, so the dashboard's
offline table stays empty this way. To fill it, run the loader from the host
against the container's database instead (step 4.3 with the local URL).

## 4. Free-tier deployment (Render + Vercel)

1. **Database:** on Render, create a PostgreSQL instance. Copy its
   *External Database URL*.
2. **API:** create a Render *Web Service* from this repository.
   * Root directory `services/api`, runtime Docker (uses the `Dockerfile`).
   * Environment variables:
     * `CARTSENSE_DATABASE_URL`: the database URL, with the scheme changed to `postgresql+psycopg://`
     * `CARTSENSE_JWT_SECRET`: a long random string
     * `CARTSENSE_CORS_ORIGINS`: your Vercel URL, e.g. `https://cartsense.vercel.app`
3. **Load data:** from your machine, point the loader at the hosted database:
   ```bash
   cd services/api
   CARTSENSE_DATABASE_URL="postgresql+psycopg://...external-url..." \
     python -m app.load_data --export-dir ../../artifacts/export --results-dir ../../reports/results/test
   ```
   With 2,000 demo users, the export is roughly 25k products, about 250k
   similar-item rows and 40k recommendation rows. That fits within free-tier
   storage limits; reduce `--demo-users` if it doesn't.
4. **Store:** on Vercel (or Netlify), import the repository with root
   directory `apps/web`, framework preset **Vite**, and set `VITE_API_URL`
   to the Render API URL. The store is a static single-page app.
   `vercel.json` sends every path to `index.html`, so React Router handles
   deep links. Alternatively, build the `apps/web/Dockerfile`, which serves
   the static files with nginx.
5. **Partner API key** (optional):
   `python -m app.load_data --create-api-key "my-store"`. The key is
   printed once.

## Retraining with store feedback

Events written by the store are real behaviour (`is_synthetic = false`). The
next retrain exports them from the `events` table and appends them to the
interactions before `cartsense_ml.export` runs. Synthetic events, if ever
generated for demos, must keep `is_synthetic = true` and are excluded from
training and from every dashboard number.
