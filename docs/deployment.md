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
     * `CARTSENSE_DATABASE_URL`: the database URL, pasted as Render shows it.
       Use the *Internal* URL only if the API and database are in the same
       region; otherwise use the *External* URL. The API converts
       `postgres://` to the driver it needs, retries while the database
       starts, and logs the reason (without the password) if it cannot connect.
     * `CARTSENSE_JWT_SECRET`: a long random string
     * `CARTSENSE_CORS_ORIGINS`: your Vercel URL, e.g. `https://cartsense.vercel.app`
3. **Load data:** from your machine, point the loader at the hosted database:
   ```bash
   cd services/api
   CARTSENSE_DATABASE_URL="...External Database URL, as shown by Render..." \
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

One command collects real store behaviour, retrains the hybrid on the dataset
plus that behaviour, and activates the new model version:

```powershell
$env:CARTSENSE_DATABASE_URL = "<the store database URL>"
.venv\Scripts\python scripts\retrain.py
Remove-Item Env:CARTSENSE_DATABASE_URL
```

What it does:

1. **Collect** (`cartsense_ml.feedback`): reads views, clicks, bag additions
   and wishlists from the `events` table. Synthetic events
   (`is_synthetic = true`) are never read. Each (shopper, product) pair
   becomes one interaction with the strongest signal as its rating
   (bag/wishlist 5, click 4, view 3). Demo shoppers are mapped back to their
   dataset id, store accounts become `site:<id>`, and guest sessions with at
   least two products become `session:<id>`.
2. **Retrain** (`cartsense_ml.export --site-interactions`): store activity is
   placed right after the dataset's last timestamp (in its original order),
   so recency weighting treats it as the newest behaviour without letting a
   few clicks outweigh the dataset. Recommendations are precomputed for demo
   shoppers and for every store account with activity.
3. **Load** (`app.load_data`): the new version becomes active. Earlier
   versions stay in the database, so the dashboard compares click-through per
   version.

The run takes about 30–35 minutes on a laptop CPU. The URL is passed to each
step through the environment only, so it never shows up in a command line or
log. Use `--skip-load` to retrain without touching the database.

## A/B testing

Set `CARTSENSE_AB_CONTROL_SHARE` on the API (e.g. `0.5`) to send that share of
visitors to a popularity control while the rest get the model. Assignment
hashes the visitor (account, or browser session for guests) with the
experiment name, so each visitor always sees the same variant. The dashboard's
A/B section shows visitors, impressions, click-through and add-to-bag rate per
variant, the click-through lift and two-proportion z-test p-values. Set it
back to `0` to stop the test; `CARTSENSE_AB_EXPERIMENT` names the experiment
(changing it reshuffles assignment).
