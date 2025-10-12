# Claude Agent Guide

Guidance for Claude Code when collaborating on this repository.

## 📚 Required references
- [Project overview](instructions/00_SUMMARY.md)
- [System architecture design](instructions/01_system_architecture_design_standalone.md)
- [Backend API design](instructions/02_backend_api_design_standalone.md)
- [Test plan](instructions/04_test_design_standalone.md)
- [Implementation prompts](instructions/prompts)
- [Progress tracker](report/PROGRESS.md)
- [Development diary summary](report/summary/DIARY01.md)
- [Current development diary](report/DIARY02.md)

## 🛠️ Environment & setup
- Provision the Python environment with `uv`: run `uv venv`, then `uv pip install -r requirements.txt`.
- Start the API server with `uvicorn app.main:app --reload` or `uv run uvicorn app.main:app --reload`.
- When Redis, Celery, or other infrastructure is required, consult `README.md` for service configuration details.

## ✅ Workflow expectations
1. Begin every session by reviewing `report/PROGRESS.md`, `report/summary/DIARY01.md`, and `report/DIARY02.md` to capture current objectives and context.
2. Study the applicable design documents and prompts before editing code to ensure that acceptance criteria and constraints are satisfied.
3. Follow strict test-driven development: introduce or update tests first, then implement code, and keep running `pytest` until the suite succeeds.
4. Close each session by updating `report/PROGRESS.md` and logging a new entry in `report/DIARY02.md` that summarizes the changes and decisions.

## 🔍 Review & prompt usage
- When performing reviews, follow the prompts located in [`instructions/prompts`](instructions/prompts), especially [`02_codex_review_prompt.md`](instructions/prompts/02_codex_review_prompt.md) when coordinating with Codex outputs.
- For implementation assignments, lean on guides such as `00_implementation_guide.md` and `01_backend_implementation_guide.md` to align with architectural expectations.

## 🧪 Testing & quality gates
- Execute `pytest` to cover unit and integration paths, expanding scenarios in line with the documented test plan as needed.
- Apply additional security or performance checks for sensitive changes, referencing the architecture and reinforcement learning design documents for specific criteria.
