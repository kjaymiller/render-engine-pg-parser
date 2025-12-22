---
title: Contributing
order: 5
slug: contributing
layout: doc
---

# Contributing Guide

We welcome contributions to `render-engine-pg`! This guide will help you set up your development environment, understand the architecture, and submit changes.

## Development Setup

We use `uv` for dependency management and `just` for running common tasks.

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/render-engine-pg-parser.git
cd render-engine-pg-parser
```

### 2. Install Dependencies

You can install the package in editable mode with development dependencies:

```bash
uv pip install -e ".[test]"
```

### 3. Run Checks

Before making changes, ensure the current tests pass:

```bash
just check
```

This runs both type checking (`mypy`) and tests (`pytest`).

## Testing

We prioritize testing to ensure reliability. Our test suite covers parsers, query generation, and connection handling.

### Running Tests

Use `just` for convenience:

```bash
# Run all tests and type checking (Recommended before commit)
just check

# Run only tests
just test

# Run only type checking
just typecheck
```

Or use `pytest` directly:

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=render_engine_pg

# Run a specific test file
uv run pytest tests/test_parsers.py -v
```

## Architecture Deep Dive

Understanding the core components helps when adding features or fixing bugs.

### Core Components

1.  **Parsers** (`render_engine_pg/parsers.py`)
    *   `PGPageParser`: Converts database rows into `Page` objects. Handles single-row (attributes) and multi-row (lists) results.
    *   `PGMarkdownCollectionParser`: Handles markdown files with frontmatter, executing pre-configured SQL inserts.

2.  **Settings** (`render_engine_pg/re_settings_parser.py`)
    *   `PGSettings`: Loads configuration from `pyproject.toml`.
    *   Manages `insert_sql` and `read_sql` queries.

3.  **Connection** (`render_engine_pg/connection.py`)
    *   `PostgresQuery`: A named tuple for connection + query string.
    *   `get_db_connection()`: Utility to create `psycopg` connections.

4.  **Content Manager** (`render_engine_pg/content_manager.py`)
    *   `PostgresContentManager`: The bridge between `render-engine` and PostgreSQL. It iterates over query results and yields pages.

5.  **CLI Tools** (`render_engine_pg/cli/`)
    *   Parses SQL schema (`sql_parser.py`).
    *   Analyzes relationships (`relationship_analyzer.py`).
    *   Generates dependency-ordered INSERTs (`query_generator.py`) and SELECTs with JOINs (`read_query_generator.py`).

### Data Flow

When generating configuration:

```
SQL Schema (annotated)
    ↓
SQLParser → Extracts objects/types
    ↓
RelationshipAnalyzer → Finds FKs & M2M
    ↓
InsertionQueryGenerator → Orders INSERTs
ReadQueryGenerator → Builds SELECTs
    ↓
TOMLConfigGenerator → Output TOML
```

When building the site:

```
pyproject.toml
    ↓
PostgresContentManager (loads query)
    ↓
Database Execution
    ↓
PGPageParser (row → page)
    ↓
Render Engine (page → html)
```

## Release Workflow

If you are a maintainer, here is the process for releasing a new version:

1.  **Create a PR** with your changes.
2.  **Verify** that `just check` passes and GitHub Actions succeed.
3.  **Merge** the PR (after approval).
4.  **Create a Release** using the GitHub CLI:

```bash
# Create a prerelease (e.g., if current is b4, next is b5)
gh release create <VERSION> --prerelease --generate-notes
```

Always use `--prerelease` for beta versions and `--generate-notes` to populate the changelog.

## Getting Help

If you get stuck, check the [Issues](https://github.com/your-username/render-engine-pg-parser/issues) or start a [Discussion](https://github.com/your-username/render-engine-pg-parser/discussions).
