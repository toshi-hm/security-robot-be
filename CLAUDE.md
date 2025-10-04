# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a FastAPI-based backend for a security robot reinforcement learning system. The backend provides REST endpoints, WebSocket streaming, background jobs via Celery, and RL training services.

## Development Environment

This project uses **uv** for environment management (not pip/venv directly).

### Setup

```bash
# Create virtual environment
uv venv

# Activate environment (optional, uv can run commands without activation)
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt
```

### Running the Development Server

```bash
# With activated environment
uvicorn app.main:app --reload

# Or using uv directly
uv run uvicorn app.main:app --reload
```

### Running Tests

```bash
# Install development dependencies first
uv pip install pytest httpx

# Run tests
pytest
```

## Architecture

### Core Application Structure

- **`app/`** - FastAPI application
  - `main.py` - Application factory with lifespan management for database and WebSocket initialization
  - `api/v1/` - Versioned API routes
    - `endpoints/` - Route handlers: environment, training, jobs, files, websocket, health
  - `core/` - Domain services (environment, training, websocket, files)
  - `db/` - Database models and session management (async SQLAlchemy)
  - `schemas/` - Pydantic models for request/response validation
  - `models/` - SQLAlchemy ORM models
  - `tasks/` - Celery task definitions
  - `utils/` - Security, logging, monitoring utilities

- **`rl/`** - Reinforcement learning components
  - `environments/` - RL environment implementations (security_env.py, enhanced_env.py)
  - `algorithms/` - RL algorithms (PPO, A3C with trainer/network/worker modules)
  - `callbacks/` - Training callbacks (websocket, logging)
  - `utils/` - Visualization and evaluation utilities

- **`tests/`** - Test suite structure (placeholder modules for unit, integration, E2E)

### Key Services

**FastAPI Application (`app.main:app`)**
- Uses `lifespan` context manager to initialize database tables on startup and manage WebSocket manager lifecycle
- CORS middleware configured via `settings.allowed_origins`
- API routes mounted at `settings.api_prefix` (default: `/api/v1`)

**Celery (`app.tasks.celery_app`)**
- Background task processing using Redis as broker
- Task modules: `file_tasks`, `training_tasks`

**WebSocket Manager (`app.core.websocket.manager`)**
- Singleton instance manages real-time connections
- Started/stopped during application lifespan

**Database**
- Async SQLAlchemy with SQLite (default: `sqlite+aiosqlite:///./security_robot.db`)
- Tables auto-created on startup via `Base.metadata.create_all`

### Configuration

Settings managed via `app.core.config.Settings` (Pydantic BaseSettings):
- `api_prefix` - API route prefix
- `allowed_origins` - CORS allowed origins (comma-separated string or list)
- `database_url` - SQLAlchemy database URL
- `redis_url` - Redis connection for Celery

## Project Context

This backend is designed to be moved into its own repository. The codebase includes placeholder modules intended for incremental implementation. The RL system supports multiple algorithms (PPO, A3C) with custom environments and callbacks for training security-related agents.
