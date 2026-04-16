from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

SUPPORTED_LANGUAGES = {"python", "javascript", "java", "c", "cpp"}
LANGUAGE_ALIASES = {"js": "javascript"}


class ExecuteRequest(BaseModel):
    language: str = Field(description="Language: python, js/javascript, java, c, cpp")
    code: str = Field(min_length=1, description="Source code to execute")
    stdin: str = Field(default="", description="Input passed to stdin")
    timeout_seconds: int = Field(default=5, ge=1, le=30)
    wait_timeout: int = Field(default=20, ge=1, le=120)

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        normalized = value.strip().lower()
        normalized = LANGUAGE_ALIASES.get(normalized, normalized)
        if normalized not in SUPPORTED_LANGUAGES:
            supported = ", ".join(sorted(SUPPORTED_LANGUAGES | set(LANGUAGE_ALIASES)))
            raise ValueError(f"Unsupported language '{value}'. Supported values: {supported}.")
        return normalized


class ExecutionResult(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool
    duration_ms: int


class SubmitResponse(BaseModel):
    task_id: str
    status: str


class TaskResultResponse(BaseModel):
    task_id: str
    status: str
    result: ExecutionResult | None = None
    error: str | None = None
