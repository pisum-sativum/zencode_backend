from __future__ import annotations

from celery.exceptions import TimeoutError as CeleryTimeoutError
from celery.result import AsyncResult
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from celery_app import celery_app
from schemas import ExecuteRequest, SubmitResponse, TaskResultResponse
from tasks import run_code_task

app = FastAPI(title="CodeZen Runner API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
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
    task = run_code_task.delay(request.model_dump())
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
    task = run_code_task.delay(request.model_dump())
    if task.id is None:
        raise HTTPException(status_code=500, detail="Failed to create execution task.")

    try:
        result = task.get(timeout=request.wait_timeout)
        return TaskResultResponse(task_id=task.id, status="completed", result=result)
    except CeleryTimeoutError:
        return TaskResultResponse(task_id=task.id, status="queued")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Execution failed: {exc}") from exc