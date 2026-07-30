Review all staged changes (`git diff --cached`) with focus on these contexts:

## Client Implementation Context

**API Methods:**
- Are new methods properly typed with Pydantic models?
- Is error handling consistent?
- Are async/sync variants implemented correctly?

**Type Definitions:**
- Are Pydantic models properly defined?
- Are types properly exported in `__init__.py`?
- Is backwards compatibility maintained?

**Code Quality:**
- Does the code follow existing patterns?
- Is the code properly formatted (ruff)?
- Are type hints complete (basedpyright)?

## Testing Context

- Do new methods have corresponding tests?
- Are edge cases covered?
- Is test coverage maintained?

## Documentation Context

- Is README updated for new features?
- Are docstrings complete?
- Are examples provided for new methods?

## Packaging Context

- Is `pyproject.toml` updated if needed?
- Are dependencies properly specified?

## Output

Provide a summary with:
1. **Issues**: Problems that should be fixed before commit
2. **Suggestions**: Improvements that aren't blocking
3. **Questions**: Anything unclear that needs clarification
