check:
    uv run mypy render_engine_pg
    uv run pytest

test:
    uv run pytest

typecheck:
    uv run mypy render_engine_pg

prerelease version:
    gh release create {{version}} --prerelease --generate-notes
