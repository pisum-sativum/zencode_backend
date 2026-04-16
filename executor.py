from __future__ import annotations

import io
import os
import tarfile
import time
from typing import Any

import docker
from docker.errors import APIError, DockerException
from requests.exceptions import ReadTimeout

MAX_OUTPUT_CHARS = 20_000
DEFAULT_SANDBOX_IMAGE = "codezen-sandbox:latest"
SANDBOX_IMAGE = os.getenv("SANDBOX_IMAGE", DEFAULT_SANDBOX_IMAGE)

LANGUAGE_ALIASES = {"js": "javascript"}
LANGUAGE_CONFIG: dict[str, dict[str, str]] = {
    "python": {
        "image": SANDBOX_IMAGE,
        "source_file": "main.py",
        "command": "python3 main.py < stdin.txt",
    },
    "javascript": {
        "image": SANDBOX_IMAGE,
        "source_file": "main.js",
        "command": "node main.js < stdin.txt",
    },
    "java": {
        "image": SANDBOX_IMAGE,
        "source_file": "Main.java",
        "command": "javac Main.java && java Main < stdin.txt",
    },
    "c": {
        "image": SANDBOX_IMAGE,
        "source_file": "main.c",
        "command": "gcc main.c -O2 -std=c11 -o main && ./main < stdin.txt",
    },
    "cpp": {
        "image": SANDBOX_IMAGE,
        "source_file": "main.cpp",
        "command": "g++ main.cpp -O2 -std=c++17 -o main && ./main < stdin.txt",
    },
}


def normalize_language(language: str) -> str:
    normalized = language.strip().lower()
    return LANGUAGE_ALIASES.get(normalized, normalized)


def _truncate_output(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + "\n\n[output truncated]"


def _build_archive(source_file: str, code: str, stdin: str) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for file_name, content in ((source_file, code), ("stdin.txt", stdin)):
            encoded = content.encode("utf-8")
            tar_info = tarfile.TarInfo(name=file_name)
            tar_info.size = len(encoded)
            tar_info.mtime = int(time.time())
            archive.addfile(tar_info, io.BytesIO(encoded))
    buffer.seek(0)
    return buffer.read()


def _collect_logs(container: docker.models.containers.Container) -> tuple[str, str]:
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    try:
        log_stream = container.logs(stream=True, stdout=True, stderr=True, demux=True)
        for stdout_chunk, stderr_chunk in log_stream:
            if stdout_chunk:
                stdout_parts.append(stdout_chunk.decode("utf-8", errors="replace"))
            if stderr_chunk:
                stderr_parts.append(stderr_chunk.decode("utf-8", errors="replace"))
    except TypeError:
        stdout_fallback = container.logs(stdout=True, stderr=False)
        stderr_fallback = container.logs(stdout=False, stderr=True)
        return (
            stdout_fallback.decode("utf-8", errors="replace"),
            stderr_fallback.decode("utf-8", errors="replace"),
        )
    return "".join(stdout_parts), "".join(stderr_parts)


def execute_code(
    language: str,
    code: str,
    stdin: str,
    timeout_seconds: int = 5,
) -> dict[str, Any]:
    normalized_language = normalize_language(language)
    if normalized_language not in LANGUAGE_CONFIG:
        supported = ", ".join(sorted(LANGUAGE_CONFIG))
        raise ValueError(f"Unsupported language '{language}'. Supported values: {supported}.")

    config = LANGUAGE_CONFIG[normalized_language]
    sandbox_image = config["image"]

    start_time = time.perf_counter()
    client: docker.DockerClient | None = None
    container: docker.models.containers.Container | None = None

    timed_out = False
    status_code = 1
    stdout = ""
    stderr = ""

    try:
        client = docker.from_env()
        container = client.containers.create(
            image=sandbox_image,
            command=["sh", "-lc", config["command"]],
            detach=True,
            network_disabled=True,
            working_dir="/sandbox",
            mem_limit="256m",
            nano_cpus=500_000_000,
            pids_limit=64,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
            user="nobody",
        )

        archive = _build_archive(config["source_file"], code, stdin)
        copied = container.put_archive("/sandbox", archive)
        if not copied:
            raise RuntimeError("Failed to copy files into sandbox container.")

        container.start()

        try:
            wait_result = container.wait(timeout=timeout_seconds)
            status_code = int(wait_result.get("StatusCode", 1))
        except ReadTimeout:
            timed_out = True
            status_code = 124
            container.kill()

        stdout, stderr = _collect_logs(container)
    except (APIError, DockerException, RuntimeError) as exc:
        stderr = f"Docker sandbox error: {exc}"
        status_code = 1
    finally:
        if container is not None:
            try:
                container.remove(force=True)
            except Exception:
                pass
        if client is not None:
            client.close()

    if timed_out:
        timeout_message = f"Execution timed out after {timeout_seconds} seconds."
        stderr = f"{stderr}\n{timeout_message}".strip()

    duration_ms = int((time.perf_counter() - start_time) * 1000)
    return {
        "stdout": _truncate_output(stdout),
        "stderr": _truncate_output(stderr),
        "exit_code": status_code,
        "timed_out": timed_out,
        "duration_ms": duration_ms,
    }
