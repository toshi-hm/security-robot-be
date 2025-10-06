# Task Completion Checklist

When a task is completed, follow this checklist:

## 1. Code Quality

- [ ] Code follows project naming conventions (snake_case, PascalCase)
- [ ] Type hints are added to function signatures
- [ ] Imports are organized (stdlib, third-party, local)
- [ ] No unused imports or variables
- [ ] Error handling is appropriate

## 2. Testing (when applicable)

- [ ] Unit tests written for new functionality
- [ ] Tests pass: `pytest`
- [ ] Consider integration tests for complex features

## 3. Database Changes (if applicable)

- [ ] Database models updated in `app/models/`
- [ ] Pydantic schemas updated in `app/schemas/`
- [ ] Consider creating Alembic migration: `alembic revision --autogenerate -m "description"`

## 4. Documentation

- [ ] Update `report/PROGRESS.md` with completed tasks
- [ ] Mark items as ✅ completed
- [ ] Move items from TODO to completed section
- [ ] Add any new issues or discoveries to "Known Issues"

- [ ] Add session entry to `report/DIARY.md`
  - Session goal
  - What was implemented
  - Deliverables
  - Learnings and insights
  - Next session plans

- [ ] Update `CLAUDE.md` if workflow or architecture changes

## 5. Code Verification

- [ ] Run the development server: `uvicorn app.main:app --reload`
- [ ] Check for import errors and startup issues
- [ ] Test endpoints manually (if applicable)

## 6. API Changes (if applicable)

- [ ] Endpoint routes are correct
- [ ] Request/response schemas are validated
- [ ] Error responses are appropriate
- [ ] Consider OpenAPI docs at `/docs`

## 7. Git (when ready to commit)

- [ ] Stage changes: `git add .`
- [ ] Commit with descriptive message: `git commit -m "feat: description"`
- [ ] Check status: `git status`

## 8. Progress File Updates (CRITICAL)

**ALWAYS do this at the end of each session:**

1. **Update PROGRESS.md:**
   - Mark completed items with ✅
   - Update progress percentages
   - Add new TODOs discovered during work
   - Update "Next Action Items" section

2. **Append to DIARY.md:**
   - Use the session template provided in the file
   - Document what was done
   - Note any problems encountered and solutions
   - Record learnings and insights
   - Plan for next session

## Notes

- **No linter/formatter config found yet**: Consider adding Black, Flake8, mypy
- **Test coverage goal**: Aim for 70%+ coverage (per PROGRESS.md)
- **Always verify imports**: Run server after changes to catch import errors early
