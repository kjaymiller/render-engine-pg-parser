check:
    uv tool run mypy render_engine_pg
    uv tool run pytest

test:
    uv run pytest

typecheck:
    uv run mypy render_engine_pg

prerelease version:
    gh release create {{version}} --prerelease --generate-notes

review-pr number:
    gh pr diff {{number}} | delta
    gh pr view {{number}}

merge-pr number:
    gh pr merge {{number}} -d --squash
