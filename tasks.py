from __future__ import annotations

from celery_app import celery_app
from executor import execute_code


@celery_app.task(name="code_execution.run")
def run_code_task(payload: dict) -> dict:
    return execute_code(
        language=payload["language"],
        code=payload["code"],
        stdin=payload.get("stdin", ""),
        timeout_seconds=int(payload.get("timeout_seconds", 5)),
    )
