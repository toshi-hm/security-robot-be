# Codebase Structure

## Root Directory Layout

```
security-robot-be/
├── app/                    # Main FastAPI application
├── rl/                     # Reinforcement learning components
├── tests/                  # Test suite (unit, integration, E2E)
├── scripts/                # Operational scripts
├── docker/                 # Docker-related files
├── instructions/           # Design documents and implementation guides
├── report/                 # Progress tracking files
├── .venv/                  # Virtual environment (created by uv)
├── requirements.txt        # Python dependencies
├── pyproject.toml          # Project metadata
├── alembic.ini             # Database migration config
├── CLAUDE.md               # Claude Code guidance
└── README.md               # Project README
```

## app/ - FastAPI Application

```
app/
├── main.py                 # Application factory, lifespan context manager
├── api/
│   ├── deps.py             # Dependency injection utilities
│   └── v1/
│       ├── api.py          # Aggregates all v1 routers
│       └── endpoints/
│           ├── training.py  # Training control endpoints
│           ├── environment.py # Environment management endpoints
│           ├── jobs.py      # Job management endpoints (placeholder)
│           ├── files.py     # File upload/download endpoints (placeholder)
│           ├── websocket.py # WebSocket endpoint
│           └── health.py    # Health check endpoint
├── core/
│   ├── config.py           # Settings (Pydantic BaseSettings)
│   ├── environment/
│   │   ├── service.py      # Environment control service
│   │   └── schemas.py      # Environment-specific schemas
│   ├── training/
│   │   ├── ppo_service.py  # PPO training service (placeholder)
│   │   ├── a3c_service.py  # A3C training service (placeholder)
│   │   ├── job_manager.py  # Training job lifecycle management
│   │   └── schemas.py      # Training-specific schemas
│   ├── websocket/
│   │   ├── manager.py      # WebSocketManager singleton
│   │   └── handlers.py     # WebSocket message handlers
│   └── files/
│       ├── service.py      # File operations service
│       └── storage.py      # File storage backend
├── models/
│   ├── base.py             # SQLAlchemy Base with common columns (id, created_at, updated_at)
│   ├── training.py         # TrainingJob, TrainingMetric models
│   ├── environment.py      # Environment state models (placeholder)
│   └── files.py            # File metadata models (placeholder)
├── schemas/
│   ├── common.py           # Common Pydantic schemas
│   ├── training.py         # Training request/response schemas
│   ├── environment.py      # Environment schemas
│   ├── jobs.py             # Job schemas
│   └── websocket.py        # WebSocket message schemas
├── db/
│   ├── base_class.py       # SQLAlchemy base class utilities
│   ├── database.py         # Database engine setup
│   └── session.py          # Async session management
├── tasks/
│   ├── celery_app.py       # Celery configuration
│   ├── training_tasks.py   # Training-related Celery tasks
│   └── file_tasks.py       # File processing tasks
└── utils/
    ├── security.py         # Security utilities
    ├── logging.py          # Logging configuration
    └── monitoring.py       # Monitoring and metrics
```

## rl/ - Reinforcement Learning

```
rl/
├── environments/
│   ├── security_env.py     # SecurityEnvironment (Gymnasium)
│   └── enhanced_env.py     # Enhanced security environment
├── algorithms/
│   ├── ppo/                # Proximal Policy Optimization
│   │   ├── trainer.py
│   │   ├── network.py
│   │   └── agent.py
│   └── a3c/                # Asynchronous Advantage Actor-Critic
│       ├── trainer.py
│       ├── network.py
│       └── worker.py
├── callbacks/
│   ├── websocket_callback.py  # Streams metrics via WebSocket
│   └── logging_callback.py    # Training logging
└── utils/
    ├── visualization.py    # Training visualization
    └── evaluation.py       # Model evaluation
```

## tests/ - Test Suite

```
tests/
├── unit/
│   ├── api/                # API endpoint tests
│   ├── services/           # Service layer tests
│   ├── ml/                 # ML component tests
│   ├── core/               # Core logic tests
│   └── utils/              # Utility tests
├── integration/            # Integration tests
├── fixtures/               # Test fixtures
├── utils/                  # Test utilities
└── e2e/                    # End-to-end tests (Playwright)
```

## Key Files

### app/main.py
- Application factory: `create_app()` function
- Lifespan context manager for startup/shutdown
- Database initialization
- WebSocket manager lifecycle
- CORS middleware configuration
- API router mounting

### app/core/config.py
- `Settings` class with environment variables
- `api_prefix`: API route prefix (default: `/api/v1`)
- `allowed_origins`: CORS configuration
- `database_url`: Database connection string
- `redis_url`: Redis connection for Celery

### Key Database Models
- `TrainingJob`: Training session metadata
- `TrainingMetric`: Time-series training metrics
- `TrainingJobStatus`: Enum (queued, running, completed, failed)

## Implementation Status

- ✅ Basic FastAPI app structure
- ✅ Database models (basic)
- ✅ API endpoints (basic)
- ✅ WebSocket manager (basic)
- 🔄 Celery tasks (skeleton)
- 🔄 RL training services (placeholder)
- ⏳ Tests (minimal)

See `report/PROGRESS.md` for detailed implementation status.
