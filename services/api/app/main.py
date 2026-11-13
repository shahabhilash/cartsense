"""FastAPI application: routers under /api/v1, CORS and uniform error bodies."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.config import get_settings, redact_database_url
from app.db import init_db
from app.routers import catalog, recs, users

log = logging.getLogger("uvicorn.error")
STARTUP_ATTEMPTS = 5
STARTUP_DELAY_SECONDS = 3


async def connect_with_retry() -> None:
    """Create tables, retrying while a freshly provisioned database starts up.
    If it still fails, log what to check (without the password) and stop."""
    url = redact_database_url(get_settings().database_url)
    for attempt in range(1, STARTUP_ATTEMPTS + 1):
        try:
            init_db()
            log.info("Connected to database %s", url)
            return
        except OperationalError as exc:
            reason = str(exc.orig).strip().splitlines()[0] if exc.orig else str(exc)
            log.warning("Database connection attempt %d/%d failed: %s", attempt, STARTUP_ATTEMPTS, reason)
            if attempt < STARTUP_ATTEMPTS:
                await asyncio.sleep(STARTUP_DELAY_SECONDS)
    log.error(
        "Could not connect to %s. Check CARTSENSE_DATABASE_URL: copy it again from the database page; "
        "use the External URL if the API and database are in different regions; make sure the "
        "database status is Available.",
        url,
    )
    raise RuntimeError("database unavailable at startup")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_with_retry()
    yield


app = FastAPI(title="CartSense API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (catalog, users, recs):
    app.include_router(module.router, prefix="/api/v1")


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": exc.status_code, "message": exc.detail}})


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    details = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"error": {"code": 422, "message": "invalid request", "details": details}})


@app.get("/health")
def health():
    return {"status": "ok"}
