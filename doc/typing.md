# Typing & Static Analysis

CherryAI uses Python type hints and mypy for static analysis across `functions`, `formats`, and `modi`.

## How to Run

Use the project mypy settings in `pyproject.toml`:

```
# Full project coverage (recommended)
python -m mypy -p CherryAI.functions -p CherryAI.formats -p CherryAI.modi

# Or directly by paths
python -m mypy CherryAI/functions CherryAI/formats CherryAI/modi
```

## Highlights

- Centralized mypy config lives in `pyproject.toml` with `follow_imports = "skip"` and `explicit_package_bases = true`.
- Consistent package-relative imports within CherryAI modules to prevent duplicate-definition errors.
- Precise types for CLI task structures using `TypedDict` and `Literal`.
- Optional integrations guarded with `Optional[...]` and explicit `None` checks.
- Targeted type ignores for libraries without stubs (e.g., `openpyxl` imports).
- Pillow text measurement uses `ImageDraw.textlength` with a `textbbox` fallback (no `attr-defined` issues).
- OpenAI SDK call sites use localized `Any` casts for overload compatibility.
- Optional `tiktoken` is typed as `Any` when unavailable so we can assign `None` safely.

## Future Work

- Expand type coverage into GUI or auxiliary scripts if desired.
- Add stub packages for optional dependencies (e.g., `types-openpyxl`) to replace targeted ignores.
- Replace localized `Any` casts with typed adapters as upstream SDK typings stabilize.