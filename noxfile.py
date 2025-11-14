import nox
import os

# Test against these Python versions
PYTHON_VERSIONS = ["3.11", "3.12", "3.13", "3.14"]

# Use pyenv for locating Python interpreters
os.environ["PYENV_VERSION"] = "3.11.13:3.12.11:3.13.0:3.14.0"
nox.options.pythons = PYTHON_VERSIONS
nox.options.reuse_existing_virtualenvs = True


@nox.session(python=PYTHON_VERSIONS)
def test(session: nox.Session) -> None:
    """Run tests with pytest."""
    session.run("uv", "pip", "install", "-e", ".[test]", external=True)
    session.run("uv", "pip", "install", "pytest-cov", external=True)
    session.run("pytest", "tests/", "-v", "--cov=render_engine_pg")


@nox.session(python=PYTHON_VERSIONS)
def typecheck(session: nox.Session) -> None:
    """Run type checking with mypy."""
    session.run("uv", "pip", "install", "-e", ".[test]", external=True)
    session.run("mypy", "render_engine_pg", f"--python-version={session.python}")


@nox.session(python=PYTHON_VERSIONS)
def check(session: nox.Session) -> None:
    """Run both type checking and tests."""
    session.run("uv", "pip", "install", "-e", ".[test]", external=True)
    session.run("uv", "pip", "install", "pytest-cov", external=True)
    session.run("mypy", "render_engine_pg", f"--python-version={session.python}")
    session.run("pytest", "tests/", "-v", "--cov=render_engine_pg")
