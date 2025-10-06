# Code Style and Conventions

## Python Version
- **Python 3.11+** is required

## Type Hints
- The codebase uses **modern Python type hints** extensively
- SQLAlchemy models use `Mapped[T]` and `mapped_column()` syntax (SQLAlchemy 2.0 style)
- Type annotations are present in most function signatures

## Naming Conventions

### Files and Directories
- Snake_case for Python files: `training_tasks.py`, `ppo_service.py`
- Package names: lowercase without underscores when possible: `app`, `core`, `models`

### Classes
- PascalCase for class names: `TrainingJob`, `SecurityEnvironment`, `WebSocketManager`
- Enum classes also use PascalCase: `TrainingJobStatus`

### Functions and Variables
- Snake_case for functions and variables: `create_app()`, `total_steps`, `database_url`
- Private functions/methods: prefix with underscore `_internal_method()`

### Constants
- UPPER_CASE for constants: `API_PREFIX` (though in Settings class, lowercase is used)

## Code Organization

### FastAPI Application Structure
```
app/
├── main.py              # Application factory, lifespan management
├── api/                 # API routes
│   ├── deps.py          # Dependency injection
│   └── v1/
│       ├── api.py       # Router aggregation
│       └── endpoints/   # Individual endpoint modules
├── core/                # Business logic services
│   ├── config.py        # Settings with Pydantic BaseSettings
│   ├── environment/     # Environment management
│   ├── training/        # Training services (ppo_service, a3c_service)
│   ├── websocket/       # WebSocket management
│   └── files/           # File operations
├── models/              # SQLAlchemy ORM models
├── schemas/             # Pydantic request/response schemas
├── db/                  # Database session and base classes
├── tasks/               # Celery task definitions
└── utils/               # Utilities (security, logging, monitoring)

rl/
├── environments/        # Gymnasium environment implementations
├── algorithms/          # RL algorithms (PPO, A3C)
├── callbacks/           # Training callbacks
└── utils/               # RL-specific utilities
```

### Import Order (implicit from existing code)
1. Standard library imports
2. Third-party imports (FastAPI, SQLAlchemy, etc.)
3. Local application imports

## SQLAlchemy Models (SQLAlchemy 2.0 Style)

```python
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

class MyModel(Base):
    # Use Mapped[] type hints
    column_name: Mapped[str] = mapped_column(String(50))
    optional_column: Mapped[Optional[datetime]] = mapped_column(default=None)
    
    # Relationships
    related: Mapped[list['RelatedModel']] = relationship(back_populates='my_model')
```

## Pydantic Schemas

```python
from pydantic import BaseModel, Field

class MySchema(BaseModel):
    field_name: str = Field(..., description="Field description")
    optional_field: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)  # For ORM mode
```

## Async/Await
- FastAPI endpoints use `async def` where appropriate
- Database operations use async SQLAlchemy with `async_session`
- WebSocket handlers are async

## Configuration
- Settings managed via `pydantic_settings.BaseSettings`
- Environment variables can override defaults
- Singleton settings instance: `settings = Settings()`

## Docstrings
- Docstrings are **not extensively present** in the current codebase
- Consider adding them for complex functions and classes
- No specific docstring format (Google/NumPy/Sphinx) is enforced yet

## Error Handling
- FastAPI HTTPException for API errors
- Proper status codes (404, 400, 500, etc.)

## Progress Tracking
- **IMPORTANT**: Always read `report/PROGRESS.md` and `report/DIARY.md` before starting work
- Update `PROGRESS.md` as tasks complete
- Append session notes to `DIARY.md` at end of session
- This workflow is documented in `CLAUDE.md`
