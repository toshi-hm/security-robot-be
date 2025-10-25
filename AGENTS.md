# Codex Agent Guide

Guidance for the gpt-5-codex agent when contributing to this repository.

## 📚 Required references
- [Project overview](instructions/00_SUMMARY.md)
- [System architecture design](instructions/01_system_architecture_design_standalone.md)
- [Backend API design](instructions/02_backend_api_design_standalone.md)
- [Test plan](instructions/04_test_design_standalone.md)
- [Implementation prompts](instructions/prompts)
- [Progress tracker](report/PROGRESS.md)
- [Development diary summary 01](report/summary/DIARY01.md)
- [Development diary summary 02](report/summary/DIARY02.md)
- [Development diary summary 03](report/summary/DIARY03.md)
- [Current development diary](report/DIARY04.md)

## 🛠️ Environment & setup
- Manage the Python environment with `uv`: create a venv via `uv venv`, then install dependencies with `uv pip install -r requirements.txt`.
- Run the API server with `uvicorn app.main:app --reload` (or `uv run uvicorn app.main:app --reload`).
- For tasks that depend on Redis, Celery, or other services, follow the guidance in `README.md`.

## ✅ Workflow expectations
1. At the start of each session, review `report/PROGRESS.md`, `report/summary/DIARY01.md`, `report/summary/DIARY02.md`, `report/summary/DIARY03.md`, and `report/DIARY04.md` to understand outstanding work and prior notes.
   - Use the dedicated summaries (`report/summary/DIARY0X.md`) to grasp historical context quickly before diving into the full diaries.
2. Read the relevant design documents and prompts before making changes so that acceptance criteria are clear.
3. Practice strict test-driven development: add or update tests first when implementing behavior, and run `pytest` after every coding session until all tests pass.
4. When the session ends, update `report/PROGRESS.md` and append a new entry to `report/DIARY04.md` summarizing the work.

## 🔍 Review & prompt usage
- For Pull Request reviews, follow [`instructions/prompts/02_codex_review_prompt.md`](instructions/prompts/02_codex_review_prompt.md) and provide the requested Japanese-language feedback.
- For implementation tasks, consult the relevant prompts in `instructions/prompts` such as `00_implementation_guide.md` and `01_backend_implementation_guide.md`.

## 🧪 Testing & quality gates
- Execute `pytest` for unit and integration coverage. If additional validation is required, extend the cases following the test plan.
- For security- or performance-sensitive changes, perform the extra checks described in the architecture and reinforcement learning design documents.
