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

## Progress Tracking

**IMPORTANT**: Before starting any implementation work, ALWAYS read the following files:

1. **`report/PROGRESS.md`** - Current implementation status
   - Shows what's completed and what's TODO
   - Contains known issues and next action items
   - Updated frequently during implementation

2. **`report/DIARY.md`** - Development session log
   - Records what was done in each session
   - Contains learnings and insights
   - Helps understand the project history

### Workflow for Each Session

1. **Start of Session:**
   - Read `report/PROGRESS.md` to understand current status
   - Read `report/DIARY.md` to see recent work and context
   - Check "Next Action Items" in PROGRESS.md

2. **During Implementation:**
   - Update `report/PROGRESS.md` as you complete tasks
   - Mark items as completed (✅) or in-progress (🔄)
   - Add new TODOs or issues as discovered

3. **End of Session:**
   - Add a new entry to `report/DIARY.md` documenting:
     - Session goals
     - What was implemented
     - Deliverables
     - Learnings and insights
     - Next session plans
   - Update `report/PROGRESS.md` final status

### Progress File Guidelines

- **PROGRESS.md**: Edit freely to reflect current state
- **DIARY.md**: Append only (don't edit past entries)
- Both files are critical for maintaining context across sessions
