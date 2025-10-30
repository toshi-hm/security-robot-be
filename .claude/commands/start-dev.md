---
description: '設計書と進捗レポートを参照し、テストが全て成功するまで自律的に開発を継続します。進捗は report/DIARY*.md / report/PROGRESS.md に記録され、必要に応じて /git-commit-push を実行します。セッション終了時にPRが未作成の場合は /create-pr を実行します。'
allowed-tools: Bash(uv, pytest, git:*, gh:*), View, Read, Write
---

# Claude Code カスタムスラッシュコマンド: 開発開始 (`/start-dev`)

このスラッシュコマンドは、設計書・進捗レポートを読み込み、**テストが全て成功するまで開発を継続**する自律的な実装ループを開始します。
Git 連携はカスタムコマンド **`/git-commit-push`** を用い、セッション終了時には **`/create-pr`** で Pull Request を作成します（PRが未作成の場合）。

use MCP Servers:

- context7
- serena

---

## Main Instruction (Initial Prompt for Claude)

**Instruction**: Based on the design documents (`instructions/*`) and prompts (`instructions/prompts/*`), please continue the implementation. Progress and development logs up to this point are recorded in `report/PROGRESS.md`, `report/summary/*`, and `report/DIARY*.md`, so make sure to review these first.

**Constraints and Operational Rules**

- **ALWAYS answer in Japanese**.
- For each session, always update `report/PROGRESS.md` and the corresponding `report/DIARY*.md`.
- When the number of entries in `report/DIARY*.md` exceeds **10**, create a **comprehensive summary** in `report/summary/DIARY*.md`, then create a **new index `report/DIARY*.md` file** and **continue appending entries to the new file**.
- Maintain and achieve **at least 80% unit test coverage** (continue implementing and testing if coverage is insufficient).
- **Do not stop development until all tests pass**.
- At logical milestones (each small, self-contained completion), execute **`/git-commit-push`** (Claude Code custom slash command).
- When encountering ambiguities in the specifications, form a **consistent hypothesis** based on design documents, existing code, and testing policy, then proceed and record the reasoning in the diary.

---

## Execution Flow (Checklist)

1. **Git Branch Setup** (IMPORTANT)

- **NEVER work directly on `main` branch**
- Check current branch: `git branch --show-current`
- If on `main`, create a new feature branch:
  - Branch naming convention: `feature/session-NNN-short-description` or `fix/issue-description`
  - Example: `git checkout -b feature/session-094-api-improvements`
- Always create a new branch for each session or feature
- Push feature branch to remote: `git push -u origin <branch-name>`

2. **Reading**

- Understand the overall picture from `instructions/00_SUMMARY.md`.
- Extract key points from `instructions/*` (Design, API, Backend, Test, Infrastructure).
- Review `instructions/prompts/*` to align on implementation tone & direction.
- Carefully read `report/PROGRESS.md`, `report/summary/*`, and `report/DIARY*.md` to extract **recent TODOs, unresolved issues, and reasons for pending tasks**.

3. **Planning (record in `report/DIARY*.md`)**

- Define this session's **goals / scope / Definition of Done (DoD)**.
- List risks, assumptions, and testing perspectives (normal, abnormal, boundary cases).

4. **Implementation & Test-Driven Development**

- Run existing tests to identify green/red status.
- Based on the specifications, iterate in the order of **Add Tests → Implement → Refactor**.

5. **Coverage Check (Reference Commands)**

- Use `uv run pytest --cov=app --cov=rl --cov-report=term-missing --cov-report=html`.
- Achieve **at least 80%** for all metrics: statements, branches, lines, and functions.

6. **Report Update**

- `report/PROGRESS.md`: summarize progress, completed items, incomplete items, and next actions.
- `report/DIARY*.md`: record start/end times, trial and error, decisions, issues, and reflections.
- If **diary entries exceed 10**, create a **summary** in `report/summary/DIARY*.md`, then issue a new `report/DIARY{NN+1}.md` to continue logging.

7. **Commit & Push to Feature Branch**

- At each milestone, execute **`/git-commit-push`**.
- **IMPORTANT**: Push to feature branch, NOT main: `git push origin <feature-branch-name>`
- `/git-commit-push` automatically detects the current branch and pushes to it

8. **Pull Request Management**

- **Check PR status**: Use `gh pr list --head <current-branch>` to check if PR already exists
- **If NO PR exists yet**:
  - Execute **`/create-pr`** to create a new Pull Request to `main`
  - The command automatically generates PR title and description from commits
  - Returns PR URL for review
- **If PR already exists**:
  - Continue using **`/git-commit-push`** to push additional commits
  - Additional commits are automatically added to the existing PR
  - No need to create a new PR

9. **Exit Criteria**

- Close the session once **all unit tests pass** and **coverage ≥ 80%** is achieved
- Append completion summary to `report/PROGRESS.md`
- Push final commit to feature branch
- Ensure Pull Request is created (use `/create-pr` if not yet created)
- **Do NOT merge to main directly** - PR requires review before merge

---

## Commit Message Template for `/git-commit-push`

feat(scope): concise summary of the purpose

- Changes: bullet-point list of key implementations/fixes
- Tests: overview and focus of added/updated tests
- Impact: affected areas such as API/Database/RL/Celery/etc.
- Notes: reasons for important decisions or temporary measures (see DIARY for details)

Refs: <related issue or document reference (optional)>

**Scope examples**: `api`, `db`, `rl`, `celery`, `tasks`, `tests`, `docs`, etc.
**Commit frequency**: keep commits small and meaningful (recommended: logically complete unit of about 1–3 files)

---

## Notes for Appending to `report/DIARY{NN}.md`

### When Exceeding 10 Entries

1. Create a new `report/summary/DIARY{NN}.md` containing a comprehensive summary of the file — lessons learned, bottlenecks, improvement plans, and metric trends.
2. Create a new `report/DIARY{NN+1}.md` and continue logging entries there from that point onward.

---

## Test Operations

- **Mandatory**: Continue development until all unit tests pass.
- For new or modified code, tests should generally be written first (add at least one test to lock down expected behavior).
- If coverage is insufficient, improve it through additional tests, design review, or simplification of branches.
- Utilize `tests/mocks` for mocks/stubs. Separate dependencies for areas with side effects.

---

## Failure Handling

- **Test Failure**: Record the minimal reproducible case in the diary → isolate the cause (input/state/external dependency) → apply targeted fix → rerun tests.
- **Unclear Specification**: Prioritize consistency between design documents and existing implementations. Record any provisional decisions with justification in **`report/DIARY*.md`**.
- **Blockers**: Propose alternatives (scope reduction or phased approach) and document escalation items in **`report/PROGRESS.md`**.

---

## Command Examples

### Development & Server

- Start API server (development mode): `uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
- Start API server (default): `uv run uvicorn app.main:app --reload`
- Export OpenAPI schema: `uv run python scripts/export_openapi.py`

### Testing

- Run all tests: `uv run pytest`
- Run unit tests only: `uv run pytest tests/unit`
- Run integration tests only: `uv run pytest tests/integration`
- Run tests with coverage report: `uv run pytest --cov=app --cov=rl --cov-report=term-missing --cov-report=html`
- Run tests in quiet mode: `uv run pytest -q`
- Run specific test file: `uv run pytest tests/unit/test_example.py`
- Run with verbose output: `uv run pytest -v`

### Lint / Type Checking

- Type checking with mypy: `uv run mypy app/ rl/`
- Format code with black (if configured): `black app/ tests/ rl/`
- Lint with flake8 (if configured): `flake8 app/ tests/ rl/`
- Lint with ruff (if configured): `ruff check app/ tests/ rl/`
- Auto-fix with ruff (if configured): `ruff check --fix app/ tests/ rl/`

### Database

- Create database tables (automatic on startup): Tables are created automatically when FastAPI starts
- For manual migration with Alembic (if needed):
  - Generate migration: `uv run alembic revision --autogenerate -m "migration message"`
  - Apply migrations: `uv run alembic upgrade head`
  - Downgrade: `uv run alembic downgrade -1`

### Docker & Services

- Start all services (API, Redis, PostgreSQL, Celery): `cd docker && docker compose up --build`
- Start in background: `cd docker && docker compose up -d`
- View logs: `docker compose logs -f`
- View specific service logs: `docker compose logs -f api` or `docker compose logs -f celery-worker`
- Stop services: `docker compose down`
- Check service health: `docker compose ps`

### Celery

- Start Celery worker (standalone): `uv run celery -A app.tasks.celery_app worker --loglevel=info`
- Monitor Celery tasks: `uv run celery -A app.tasks.celery_app events`
- Check Celery status: `uv run celery -A app.tasks.celery_app inspect active`

---

## Coverage Standards

- Maintain **at least 80% coverage** for both branches and functions.
- Example command to generate a coverage report: `uv run pytest --cov=app --cov=rl --cov-report=term-missing --cov-report=html`
- HTML report will be generated in `htmlcov/` directory

---

## Git Branch Strategy

### Feature Branch Workflow

1. **Always start by checking current branch**:

   ```bash
   git branch --show-current
   ```

2. **If on `main`, create a new feature branch**:

   ```bash
   git checkout -b feature/session-NNN-description
   ```

   - Examples:
     - `feature/session-094-celery-improvements`
     - `feature/add-websocket-notifications`
     - `fix/database-connection-leak`

3. **Push feature branch to remote**:

   ```bash
   git push -u origin feature/session-NNN-description
   ```

4. **Commit frequently to feature branch**:
   - Use `/git-commit-push` for automatic commit + push
   - The command will automatically detect current branch and push to it

5. **Pull Request workflow**:
   - Check if PR already exists: `gh pr list --head <current-branch>`
   - **First time (no PR yet)**: Use `/create-pr` to create Pull Request
   - **Subsequent commits (PR exists)**: Use `/git-commit-push` to add commits to existing PR
   - PR will automatically update with new commits from the feature branch

6. **After session completion**:
   - Ensure all tests pass and coverage ≥ 80%
   - Push final commit to feature branch with `/git-commit-push`
   - Create PR with `/create-pr` if not yet created
   - PR requires review before merging to `main` (do NOT merge directly)

### Branch Naming Convention

- Feature: `feature/session-NNN-short-description` or `feature/feature-name`
- Bug fix: `fix/issue-description`
- Documentation: `docs/update-description`
- Test improvement: `test/coverage-improvement`
- Refactoring: `refactor/component-name`

---

## Output Style (for Claude)

- **FIRST**: Check if on `main` branch. If yes, create and switch to a feature branch.
- Log all changes and decisions in `report/DIARY*.md` in real time.
- Update `report/PROGRESS.md` with a summary at the end of each session.
- Execute `/git-commit-push` at appropriate milestones to maintain a robust commit history resilient to interruptions.
- **Push to feature branch**, not `main`.
- Automatically proceed to the next task only after achieving **all tests passing & coverage ≥ 80%**.
- **At session end**:
  - Check if PR exists for current branch: `gh pr list --head <current-branch>`
  - If NO PR: Execute `/create-pr` to create Pull Request
  - If PR exists: Inform user that commits have been added to existing PR
  - Display PR URL for user to review
