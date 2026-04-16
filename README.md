# CodeZen Backend

FastAPI + Celery backend for queued code execution with Docker sandboxing.

## Visual architecture guides

- Open `project_guide.html` in a browser for a full beginner-friendly explanation of components.
- Open `file_dependency.html` in a browser for an in-depth breakdown of how files flow and depend on each other.
- Open `real_world_restaurant.html` in a browser for a deep real-life restaurant analogy with an interactive dependency graph built using Cytoscape.js (no Mermaid).

## Supported languages

- python
- js (or javascript)
- java
- c
- cpp

## Run with Docker Compose

1. Build sandbox image and start all services:

```bash
./run.sh
```

or on Windows PowerShell:

```powershell
./run.ps1
```

2. API will be available at `http://localhost:8000`.

## API endpoints

### POST /submit

Queue execution and return task id.

Example body:

```json
{
  "language": "python",
  "code": "print(input())",
  "stdin": "hello",
  "timeout_seconds": 5
}
```

### GET /result/{task_id}

Get task status and result.

### POST /execute

Queue and wait for completion for up to `wait_timeout` seconds.

Example body:

```json
{
  "language": "cpp",
  "code": "#include <iostream>\nint main(){std::string s; std::getline(std::cin,s); std::cout<<s;}",
  "stdin": "hello cpp",
  "timeout_seconds": 5,
  "wait_timeout": 20
}
```
