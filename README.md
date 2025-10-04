# Security Robot RL Backend

This directory contains the FastAPI-based backend outlined in `report/backend_api_specification.md`. It is organized to support REST endpoints, WebSocket streaming, background jobs, and reinforcement learning services.

## Getting Started

Like the frontend, this backend directory is meant to be moved into its own repository. Dependency metadata is already present via `pyproject.toml` and `requirements.txt` so the service can be bootstrapped after relocation.

> **Note:** The backend now relies on [uv](https://docs.astral.sh/uv/) for environment
> management. uv creates and maintains the virtual environment, installs
> dependencies, and can run commands using the project's metadata.

```bash
# create the virtual environment managed by uv
uv venv

# activate the environment if you prefer to work inside it directly
source .venv/bin/activate

# install dependencies declared in pyproject.toml / requirements.txt
uv pip install -r requirements.txt

# launch the development server (either from the activated shell or with `uv run`)
uvicorn app.main:app --reload
```

You can also skip manual activation and let uv manage command execution:

```bash
uv run uvicorn app.main:app --reload
```

## Repository Layout

- `app/` keeps the FastAPI application, including routers, domain services, database models, schemas, and task definitions.
- `rl/` stores the reinforcement learning environments, algorithms, callbacks, and helpers.
- `tests/` follows the prompt-driven layout with placeholders for unit (`unit/api`, `unit/services`, `unit/ml`, `unit/core`, `unit/utils`), integration, fixtures, utilities, and Playwright E2E suites.
- `scripts/` and `docker/` hold operational utilities and container definitions.

Placeholder modules are provided so that implementation can proceed incrementally in line with the prompts under `report/prompt/`.
