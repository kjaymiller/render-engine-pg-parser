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

### `read_sql`

**Type:** `dict[str, str]`
**Required:** No
**Default:** `{}`

Defines SQL SELECT queries for reading collection content. These queries are used by ContentManager to fetch data from the database. Maps collection names to their SELECT queries.

```toml
[tool.render-engine.pg]
read_sql = {
    posts = "SELECT id, title, content, author_id FROM posts ORDER BY created_at DESC",
    docs = "SELECT id, slug, content FROM documentation WHERE published = true"
}
```

**Usage with ContentManager:**

When creating a collection, pass the query from settings:

```python
from render_engine_pg.re_settings_parser import PGSettings
from render_engine_pg.connection import PostgresQuery
from render_engine_pg.content_manager import PostgresContentManager

settings = PGSettings()
read_query = settings.get_read_sql("posts")

collection = Collection(
    name="blog",
    query=PostgresQuery(
        connection=db,
        query=read_query
    ),
    Parser=PGMarkdownCollectionParser,
    routes=["blog/{title}/"]
)
```

### `insert_sql`

**Type:** `dict[str, str | list[str]]`
**Required:** No
**Default:** `{}`

Defines pre-configured SQL insert statements executed when creating new entries via `create_entry()`. Maps collection names to their insert SQL. Supports t-string-like templates with variable substitution from frontmatter attributes.

#### String Format (Semicolon-Separated)

```toml
[tool.render-engine.pg]
insert_sql = { posts = "INSERT INTO categories (name) VALUES ('Tech'); INSERT INTO categories (name) VALUES ('Travel')" }
```

Queries are split by semicolons. Empty queries are automatically filtered out.

#### List Format

```toml
[tool.render-engine.pg]
insert_sql = { posts = [
    "INSERT INTO categories (name) VALUES ('Tech')",
    "INSERT INTO categories (name) VALUES ('Travel')"
] }
```

Use this format for better readability with complex queries.

#### T-String Templates with Variable Substitution

Queries can include t-string-like placeholders using `{variable}` syntax. Template variables are substituted with values from the markdown frontmatter when `create_entry()` is called.

```toml
[tool.render-engine.pg]
insert_sql = {
    posts = "INSERT INTO post_stats (post_id) VALUES ({id})"
}
```

When creating a post:

```python
PGMarkdownCollectionParser.create_entry(
    content="""---
id: 42
title: My Post
author_id: 7
---
# Content""",
    collection_name="posts",
    connection=db,
    table="posts"
)
```

This executes:
1. Template query: `INSERT INTO post_stats (post_id) VALUES (42)`
2. Main insert: `INSERT INTO posts (id, title, author_id, content) VALUES (42, 'My Post', 7, '# Content')`

**Benefits:**
- Automatically creates related records (e.g., statistics, relationships) when adding new entries
- Values are safely parameterized by psycopg, preventing SQL injection
- No need for manual query execution in your code

**Example: Multiple Templates for a Collection**

```toml
[tool.render-engine.pg]
insert_sql = {
    posts = [
        "INSERT INTO post_stats (post_id, author_id) VALUES ({id}, {author_id})",
        "INSERT INTO post_audit_log (post_id, action) VALUES ({id}, 'created')"
    ]
}
```

Both template queries execute for every new entry created.

#### Multiple Collections

```toml
[tool.render-engine.pg]
insert_sql = {
    posts = "INSERT INTO post_metadata (post_id) VALUES ({id})",
    comments = "INSERT INTO comment_metadata (comment_id) VALUES ({id})"
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
