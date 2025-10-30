---
title: Configuration
slug: configuration
layout: doc
---

# Configuration Guide

Configuration for the render-engine PostgreSQL plugin is managed through `pyproject.toml` under the `[tool.render-engine.pg]` section.

## Configuration Structure

```toml
[tool.render-engine.pg]
insert_sql = { collection_name = "SQL QUERY1; SQL QUERY2" }
default_table = "default_table_name"
auto_commit = true
```

## Settings Reference

### `insert_sql`

**Type:** `dict[str, str | list[str]]`
**Required:** No
**Default:** `{}`

Defines pre-configured SQL insert statements for collections. Maps collection names to their insert SQL.

#### String Format (Semicolon-Separated)

```toml
[tool.render-engine.pg]
insert_sql = { posts = "INSERT INTO users (name) VALUES ('Alice'); INSERT INTO users (name) VALUES ('Bob')" }
```

Queries are split by semicolons. Empty queries are automatically filtered out.

#### List Format

```toml
[tool.render-engine.pg]
insert_sql = { posts = [
    "INSERT INTO users (name) VALUES ('Alice')",
    "INSERT INTO users (name) VALUES ('Bob')"
] }
```

Use this format for better readability with complex queries.

#### Multiple Collections

```toml
[tool.render-engine.pg]
insert_sql = {
    posts = "INSERT INTO users (name) VALUES ('Alice')",
    comments = "INSERT INTO statuses (status) VALUES ('active')"
}
```

### `default_table`

**Type:** `str`
**Required:** No
**Default:** `null`

Specifies a default table name when none is provided to `create_entry()`.

```toml
[tool.render-engine.pg]
default_table = "posts"
```

### `auto_commit`

**Type:** `bool`
**Required:** No
**Default:** `true`

Whether to automatically commit transactions after executing inserts.

```toml
[tool.render-engine.pg]
auto_commit = false
```

## Loading Settings at Runtime

Settings are automatically discovered and loaded from `pyproject.toml`:

```python
from render_engine_pg.re_settings_parser import PGSettings

# Automatically finds and loads pyproject.toml
settings = PGSettings()

# Or specify custom path
settings = PGSettings(config_path="/path/to/pyproject.toml")

# Retrieve queries for a collection
queries = settings.get_insert_sql("posts")
```

## Complete Example

```toml
[project]
name = "my-blog"
version = "0.1.0"

[tool.render-engine.pg]
insert_sql = {
    posts = "INSERT INTO categories (name) VALUES ('Technology'); INSERT INTO categories (name) VALUES ('Travel')",
    comments = [
        "INSERT INTO comment_statuses (status) VALUES ('pending')",
        "INSERT INTO comment_statuses (status) VALUES ('approved')"
    ]
}
default_table = "posts"
auto_commit = true
```

## Error Handling

If `pyproject.toml` is not found, settings default to:

```python
{
    "insert_sql": {},
    "default_table": None,
    "auto_commit": True
}
```

Non-existent collections return an empty list:

```python
settings.get_insert_sql("nonexistent")  # Returns: []
```

## Best Practices

1. **Keep Queries Simple** - One logical operation per query
2. **Use Semicolons Consistently** - Add a trailing semicolon for clarity
3. **Name Collections Meaningfully** - Use descriptive collection names that reflect their purpose
4. **Comment Your Inserts** - Add SQL comments for context:
   ```toml
   posts = "-- Setup categories\nINSERT INTO categories (name) VALUES ('Tech'); INSERT INTO categories (name) VALUES ('Travel')"
   ```
5. **Separate Complex Setups** - For complex scenarios, consider using multiple collection names

## Configuration Scope

The `[tool.render-engine.pg]` section is **plugin-specific** and won't affect other render-engine plugins or tools. Other parts of your `pyproject.toml` remain unchanged.

Next, see [usage examples](./03-usage.md).
