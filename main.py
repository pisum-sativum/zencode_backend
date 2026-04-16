from __future__ import annotations

import logging
import os
import uuid

from celery.exceptions import TimeoutError as CeleryTimeoutError
from celery.result import AsyncResult
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from celery_app import celery_app
from executor import execute_code
from schemas import ExecuteRequest, SubmitResponse, TaskResultResponse
from tasks import run_code_task

logger = logging.getLogger(__name__)


def _parse_cors_origins() -> list[str]:
    configured = os.getenv("CORS_ORIGINS", "")
    origins = [origin.strip() for origin in configured.split(",") if origin.strip()]
    if origins:
        return origins
    return [
        "https://zencode-eta.vercel.app",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


def _enqueue_task(payload: dict):
    try:
        return run_code_task.delay(payload)
    except Exception as exc:
        logger.exception("Failed to enqueue task")
        raise HTTPException(
            status_code=503,
            detail="Execution queue unavailable. Ensure Redis and Celery worker are running.",
        ) from exc


def _execute_sync(request: ExecuteRequest) -> TaskResultResponse:
    try:
        result = execute_code(
            language=request.language,
            code=request.code,
            stdin=request.stdin,
            timeout_seconds=request.timeout_seconds,
        )
        return TaskResultResponse(
            task_id=f"sync-{uuid.uuid4()}",
            status="completed",
            result=result,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Synchronous execution failed")
        raise HTTPException(status_code=500, detail=f"Execution failed: {exc}") from exc


app = FastAPI(title="CodeZen Runner API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_cors_origins(),
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "CodeZen FastAPI runner is up."}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/submit", response_model=SubmitResponse)
def submit_execution(request: ExecuteRequest) -> SubmitResponse:
    task = _enqueue_task(request.model_dump())
    if task.id is None:
        raise HTTPException(status_code=500, detail="Failed to create execution task.")
    return SubmitResponse(task_id=task.id, status="queued")


@app.get("/result/{task_id}", response_model=TaskResultResponse)
def get_result(task_id: str) -> TaskResultResponse:
    task = AsyncResult(task_id, app=celery_app)
    if task.successful():
        return TaskResultResponse(task_id=task_id, status="completed", result=task.result)
    if task.failed():
        return TaskResultResponse(task_id=task_id, status="failed", error=str(task.result))
    return TaskResultResponse(task_id=task_id, status=task.status.lower())


@app.post("/execute", response_model=TaskResultResponse)
def execute_and_wait(request: ExecuteRequest) -> TaskResultResponse:
    try:
        task = _enqueue_task(request.model_dump())
    except HTTPException as exc:
        if exc.status_code == 503:
            logger.warning("Queue unavailable, falling back to synchronous execution")
            return _execute_sync(request)
        raise

    if task.id is None:
        raise HTTPException(status_code=500, detail="Failed to create execution task.")

    try:
        result = task.get(timeout=request.wait_timeout)
        return TaskResultResponse(task_id=task.id, status="completed", result=result)
    except CeleryTimeoutError:
        return TaskResultResponse(task_id=task.id, status="queued")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Execution failed: {exc}") from exc