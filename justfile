check:
    uv tool run nox -s check

test:
    uv tool run nox -s test

typecheck:
    uv tool run nox -s typecheck

prerelease version:
    gh release create {{version}} --prerelease --generate-notes

review-pr number:
    gh pr diff {{number}} | delta
    gh pr view {{number}}

merge-pr number:
    gh pr merge {{number}} -d --squash
