# Suggested Commands for Development

## Environment Setup

```bash
# Create virtual environment
uv venv

# Activate environment (optional - uv can run commands without activation)
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt

# Install development dependencies
uv pip install pytest httpx
```

## Running the Application

```bash
# Start development server (with hot reload)
uvicorn app.main:app --reload

# Or using uv directly (without activation)
uv run uvicorn app.main:app --reload

# Start on specific port
uvicorn app.main:app --reload --port 8000 --host 0.0.0.0
```

## Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/unit/api/test_training.py

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test pattern
pytest -k "test_training"
```

## Background Task Workers

```bash
# Start Celery worker (requires Redis running)
celery -A app.tasks.celery_app worker --loglevel=info

# Start Celery worker with specific queue
celery -A app.tasks.celery_app worker --loglevel=info -Q training,files
```

## Database Management

```bash
# Create new migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Show current migration
alembic current

# Show migration history
alembic history
```

## Linting & Formatting

Note: No linter/formatter configuration files (.flake8, .black, pyproject.toml[tool.black], etc.) were found in the project. Consider adding them for consistency.

```bash
# If you add these tools, suggested commands would be:
# black app/ tests/  # Format code
# flake8 app/ tests/  # Lint code
# mypy app/          # Type checking
```

## Docker (if using)

```bash
# Check if docker-compose.yml exists
ls docker-compose.yml

# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## Redis (for Celery)

```bash
# Start Redis (if installed locally)
redis-server

# Check Redis connection
redis-cli ping
```

## Common Git Commands

```bash
# Check status
git status

# Create feature branch
git checkout -b feature/your-feature-name

# Stage changes
git add .

# Commit
git commit -m "Description"

# Push
git push origin feature/your-feature-name
```

## Project-Specific Utilities

```bash
# Find Python files
find app -name "*.py"

# Search for patterns in code
grep -r "pattern" app/

# List directory structure
tree app/ -L 2

# Check Python version
python --version
```
