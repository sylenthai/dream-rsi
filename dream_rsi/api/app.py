from __future__ import annotations
import os
from typing import Any
from fastapi import FastAPI, HTTPException, Header, Request, Response
from pydantic import BaseModel, Field
from ..service.experiments import ExperimentService
from ..service.queue import InMemoryJobQueue, RedisJobQueue
from ..storage import RunStore, PostgresRunStore
from ..observability import METRICS
from .. import __version__

class ExperimentRequest(BaseModel):
    task: str = Field(min_length=1, max_length=256)
    config: dict[str, Any] = Field(default_factory=dict)

class ExperimentResponse(BaseModel):
    id: str
    task: str
    status: str
    attempts: int
    created_at: str
    result: dict[str, Any] | None = None
    error: str | None = None

def create_app(service: ExperimentService | None = None) -> FastAPI:
    if service is None:
        dsn=os.getenv("DREAM_RSI_POSTGRES_DSN")
        store=PostgresRunStore(dsn) if dsn else RunStore(os.getenv("DREAM_RSI_DB", "runs/dream_rsi.sqlite3"))
        redis_url=os.getenv("DREAM_RSI_REDIS_URL")
        q=RedisJobQueue(redis_url) if redis_url else InMemoryJobQueue()
        service=ExperimentService(store, q)
    svc = service
    app = FastAPI(title="Dream-RSI API", version=__version__)
    api_key = os.getenv("DREAM_RSI_API_KEY")
    production = os.getenv("DREAM_RSI_ENV", "development").lower() == "production"

    def auth(x_api_key: str | None = None, authorization: str | None = None) -> None:
        token = x_api_key
        if not token and authorization and authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
        if not api_key:
            if production: raise HTTPException(503, "API authentication is not configured")
            return
        if token != api_key: raise HTTPException(401, "invalid API key")

    @app.get("/metrics")
    def metrics(x_api_key: str | None = Header(default=None), authorization: str | None = Header(default=None)):
        public_metrics = os.getenv("DREAM_RSI_PUBLIC_METRICS", "false").lower() in {"1", "true", "yes"}
        if production and not public_metrics:
            auth(x_api_key, authorization)
        return Response(METRICS.prometheus(), media_type="text/plain; version=0.0.4")

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "version": __version__}

    @app.get("/readyz")
    def readyz():
        checks: dict[str, str] = {}
        try:
            healthcheck = getattr(svc.store, "healthcheck", None)
            if healthcheck:
                healthcheck()
            checks["store"] = "ok"
        except Exception as exc:
            checks["store"] = f"error: {type(exc).__name__}"
        queue_healthcheck = getattr(svc.queue, "healthcheck", None)
        if queue_healthcheck:
            try:
                queue_healthcheck()
                checks["queue"] = "ok"
            except Exception as exc:
                checks["queue"] = f"error: {type(exc).__name__}"
        else:
            checks["queue"] = "ok"
        ready = all(value == "ok" for value in checks.values())
        if not ready:
            raise HTTPException(503, detail={"status": "not_ready", "checks": checks})
        return {"status": "ready", "version": __version__, "checks": checks}

    @app.post("/v1/experiments", response_model=ExperimentResponse, status_code=202)
    def submit(req: ExperimentRequest, x_api_key: str | None = Header(default=None), authorization: str | None = Header(default=None), idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
        auth(x_api_key, authorization)
        r=svc.submit(req.task, req.config, idempotency_key)
        return ExperimentResponse(id=r.id, task=r.task, status=r.status, attempts=r.attempts, created_at=r.created_at, result=r.result, error=r.error)

    @app.post("/v1/experiments/{run_id}/cancel", response_model=ExperimentResponse)
    def cancel(run_id: str, x_api_key: str | None = Header(default=None), authorization: str | None = Header(default=None)):
        auth(x_api_key, authorization)
        r = svc.get(run_id)
        if r is None: raise HTTPException(404, "experiment not found")
        if r.status in {"succeeded", "failed", "dead_letter", "cancelled"}: return ExperimentResponse(id=r.id, task=r.task, status=r.status, attempts=r.attempts, created_at=r.created_at, result=r.result, error=r.error)
        r.status = "cancelled"
        if getattr(svc, "store", None): svc.store.update_run(run_id, "cancelled", attempts=r.attempts)
        return ExperimentResponse(id=r.id, task=r.task, status=r.status, attempts=r.attempts, created_at=r.created_at, result=r.result, error=r.error)

    @app.get("/v1/experiments/{run_id}", response_model=ExperimentResponse)
    def status(run_id: str, x_api_key: str | None = Header(default=None), authorization: str | None = Header(default=None)):
        auth(x_api_key, authorization); r=svc.get(run_id)
        if r is None: raise HTTPException(404, "experiment not found")
        return ExperimentResponse(id=r.id, task=r.task, status=r.status, attempts=r.attempts, created_at=r.created_at, result=r.result, error=r.error)
    return app

app=create_app()
