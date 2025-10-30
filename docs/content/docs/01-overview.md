---
title: Overview
slug: overview
layout: doc
---

# Collection-Based Insert Configuration

The render-engine PostgreSQL plugin now supports **configuration-driven insert handling** through `pyproject.toml`. This feature allows you to define pre-configured SQL insert statements at the collection level, automatically executing them when creating entries.

## What It Does

Instead of manually building INSERT queries in code, you can define them once in your project configuration and reference them by collection name:

```toml
[tool.render-engine.pg]
insert_sql = { posts = "INSERT INTO users (name) VALUES ('Alice'); INSERT INTO users (name) VALUES ('Bob')" }
```

Then simply reference the collection when creating entries:

```python
PGMarkdownCollectionParser.create_entry(
    content="---\ntitle: My Post\n---\nContent here",
    collection_name="posts",
    connection=db_connection,
    table="posts"
)
```

The pre-configured inserts execute **before** the markdown content insert, ensuring any required data dependencies are satisfied.

## Key Features

- **Centralized Configuration** - All insert SQL lives in `pyproject.toml` under `[tool.render-engine.pg]`
- **Collection-Based** - Map collections to their required inserts via `insert_sql` settings
- **Flexible Format** - Define inserts as semicolon-separated strings or as lists
- **Backward Compatible** - Works with existing code; `collection_name` is optional
- **Auto-Discovery** - Settings are automatically loaded from `pyproject.toml` at runtime
- **Error Handling** - Graceful fallbacks and logging for missing settings

## Quick Start

### 1. Add Configuration to `pyproject.toml`

```toml
[tool.render-engine.pg]
insert_sql = { my_collection = "SQL QUERY1; SQL QUERY2" }
```

### 2. Use in Your Code

```python
from render_engine_pg.parsers import PGMarkdownCollectionParser

PGMarkdownCollectionParser.create_entry(
    content="---\ntitle: Example\n---\nContent",
    collection_name="my_collection",
    connection=db_connection,
    table="my_table"
)
```

That's it! The pre-configured inserts will execute automatically.

## When to Use This Feature

✓ You have setup/seed data that must exist before collection entries
✓ You want to centralize database initialization logic
✓ You're managing multiple collections with different dependencies
✓ You want configuration separate from code

## File Structure

```
your-project/
├── pyproject.toml          # Configuration with [tool.render-engine.pg]
├── render_engine_pg/       # Your render-engine code
│   ├── parsers.py
│   └── re_settings_parser.py
└── docs/                   # This documentation
```

Next, learn about [configuration options](./02-configuration.md).
