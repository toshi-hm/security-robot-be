# Security Robot RL Backend - Project Overview

## Purpose
This is a FastAPI-based backend for a security robot reinforcement learning system. The backend provides:
- REST API endpoints for training control, environment management, file operations, and job management
- WebSocket streaming for real-time training metrics
- Background job processing via Celery
- Reinforcement learning training services supporting PPO and A3C algorithms

The project is designed as a standalone backend service that can be moved to its own repository.

## Tech Stack

### Core Framework
- **FastAPI 0.115.6** - Async web framework
- **Uvicorn 0.34.0** - ASGI server with `standard` extras
- **Python 3.11+** - Required Python version

### Database
- **SQLAlchemy 2.0.36** (with asyncio support) - ORM
- **aiosqlite 0.20.0** - Async SQLite driver
- **SQLite** - Default database (via `sqlite+aiosqlite:///./security_robot.db`)
- **Alembic** - Database migrations (configured via alembic.ini)

### Data Validation & Settings
- **Pydantic 2.10.3** - Data validation and schemas
- **Pydantic-settings 2.7.0** - Settings management

### Background Tasks
- **Celery 5.5.0** - Distributed task queue
- **Redis 5.2.1** - Message broker for Celery

### Reinforcement Learning
- **Gymnasium 1.0.0** - RL environment interface (replaces OpenAI Gym)
- **Stable-Baselines3 2.4.0** - High-quality RL algorithm implementations
- **PyTorch 2.5.1** - Deep learning framework
- **NumPy 1.26.4** - Numerical computing (pinned for SB3 compatibility)

### Development Tools
- **pytest 8.3.0+** - Testing framework
- **httpx 0.27.0+** - Async HTTP client for testing

## Environment Management
This project uses **uv** (not pip/venv directly) for fast, reliable environment management.
