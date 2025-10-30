---
title: API Reference
slug: api-reference
layout: doc
---

# API Reference

Complete API documentation for the settings parser and updated parser methods.

## PGSettings Class

Manages render-engine PostgreSQL plugin settings from `pyproject.toml`.

### Constructor

```python
PGSettings(config_path: Path | str | None = None)
```

**Parameters:**

- `config_path` (Path | str | None): Optional path to `pyproject.toml`. If not provided, searches parent directories automatically.

**Example:**

```python
from render_engine_pg.re_settings_parser import PGSettings

# Auto-discover pyproject.toml
settings = PGSettings()

# Use specific path
settings = PGSettings(config_path="/path/to/pyproject.toml")
```

### Attributes

#### `config_path`

The path to the loaded `pyproject.toml` file or `None` if not found.

```python
settings = PGSettings()
print(settings.config_path)  # Path('/Users/user/project/pyproject.toml')
```

#### `settings`

Dictionary containing all loaded settings.

```python
settings = PGSettings()
print(settings.settings)
# Output:
# {
#     'insert_sql': {'posts': '...'},
#     'default_table': None,
#     'auto_commit': True
# }
```

#### `DEFAULT_SETTINGS`

Class attribute with default configuration.

```python
PGSettings.DEFAULT_SETTINGS
# Output:
# {
#     'insert_sql': {},
#     'default_table': None,
#     'auto_commit': True
# }
```

### Methods

#### `get_insert_sql(collection_name: str) -> list[str]`

Retrieves SQL insert statements for a collection.

**Parameters:**

- `collection_name` (str): Name of the collection as defined in `pyproject.toml`

**Returns:**

- `list[str]`: List of SQL queries. Empty list if collection not found or has no inserts.

**Example:**

```python
settings = PGSettings()

# Single collection with multiple queries
queries = settings.get_insert_sql("posts")
# Returns: ['INSERT INTO users (name) VALUES (...)', 'INSERT INTO roles ...']

# Non-existent collection
queries = settings.get_insert_sql("nonexistent")
# Returns: []

# Iterate and execute
for query in queries:
    cursor.execute(query)
```

**Behavior:**

- Splits semicolon-separated strings into individual queries
- Filters out empty queries
- Accepts both string and list formats in `pyproject.toml`
- Returns empty list if collection not found

### Static Methods

#### `_find_pyproject_toml(start_path: Path | None = None) -> Path | None`

Searches for `pyproject.toml` starting from a directory and moving up.

**Parameters:**

- `start_path` (Path | None): Starting directory. Defaults to current directory.

**Returns:**

- `Path`: Path to found `pyproject.toml`
- `None`: If file not found within search depth limit

**Notes:**

- Searches up to 10 parent directories
- Stops when reaching filesystem root
- Used automatically by constructor

## PGMarkdownCollectionParser Class

Extends `MarkdownPageParser` with collection-based insert support.

### `create_entry` Method

```python
@staticmethod
def create_entry(*, content: str = "Hello World", **kwargs) -> str
```

Converts markdown frontmatter to SQL INSERT query and executes it. Optionally executes pre-configured insert SQL from settings.

**Parameters (Keyword-only):**

- `content` (str): Markdown content with optional YAML frontmatter
  - Default: `"Hello World"`

- `connection` (psycopg.Connection): PostgreSQL database connection
  - Required

- `table` (str): Target database table name for the markdown entry insert
  - Required

- `collection_name` (str): Optional collection name to load pre-configured inserts
  - Default: `None`
  - If provided, triggers execution of pre-configured SQL statements

- `**kwargs`: Additional metadata to add to frontmatter
  - Excluded from insertion: `connection`, `table`, `collection_name`
  - All others become page attributes

**Returns:**

- `str`: The SQL INSERT query that was executed (for the markdown entry, not pre-configured inserts)

**Execution Order:**

1. If `collection_name` provided, load and execute pre-configured inserts
2. Parse markdown frontmatter
3. Build and execute INSERT query for markdown entry
4. Commit transaction

**Example:**

```python
from render_engine_pg.parsers import PGMarkdownCollectionParser

result = PGMarkdownCollectionParser.create_entry(
    content="""---
title: My Post
author: Jane Doe
---
Post content here""",
    collection_name="blog_posts",
    connection=db_connection,
    table="posts",
    status="published"
)

print(result)
# INSERT INTO posts (title, author, content, status) VALUES (%s, %s, %s, %s)
```

**Without Collection Name (Backward Compatible):**

```python
# Pre-configured inserts are skipped
PGMarkdownCollectionParser.create_entry(
    content="# Hello\nContent",
    connection=db,
    table="pages"
)
```

**Exception Handling:**

The method may raise:

- `psycopg.Error`: Database connection or execution errors
- `FileNotFoundError`: `pyproject.toml` not found (uses defaults)
- `ValueError`: Invalid configuration format

## Configuration Schema

### TOML Structure

```toml
[tool.render-engine.pg]
insert_sql = { <collection_name> = <sql_definition> }
default_table = <table_name>
auto_commit = <bool>
```

### Valid `insert_sql` Formats

**String (Semicolon-Separated):**

```toml
insert_sql = { posts = "INSERT ...; INSERT ..." }
```

**List:**

```toml
insert_sql = { posts = ["INSERT ...", "INSERT ..."] }
```

**Multiple Collections:**

```toml
insert_sql = {
    posts = "INSERT ...",
    comments = "INSERT ..."
}
```

**Mixed Formats:**

```toml
insert_sql = {
    posts = "INSERT ...; INSERT ...",
    comments = ["INSERT ...", "INSERT ..."]
}
```

## Exception Hierarchy

All exceptions are standard Python exceptions or `psycopg` exceptions:

- `FileNotFoundError`: Configuration file issues
- `psycopg.DatabaseError`: Database operation failures
- `psycopg.IntegrityError`: Constraint violations
- `ValueError`: Invalid configuration

## Logging

The module logs to `render_engine_pg.re_settings_parser` logger:

```python
import logging

logger = logging.getLogger('render_engine_pg.re_settings_parser')
logger.setLevel(logging.DEBUG)
```

**Log Levels:**

- `DEBUG`: Found pyproject.toml, loaded settings
- `WARNING`: pyproject.toml not found, using defaults
- `ERROR`: Error reading configuration file

## Type Hints

All type hints use Python 3.10+ syntax:

```python
from pathlib import Path
from typing import Any

class PGSettings:
    settings: dict[str, Any]
    config_path: Path | None

    def get_insert_sql(self, collection_name: str) -> list[str]: ...
```

## Thread Safety

`PGSettings` instances are not thread-safe. If using in multi-threaded code:

```python
import threading

# Create one instance per thread
local = threading.local()

def get_settings():
    if not hasattr(local, 'settings'):
        local.settings = PGSettings()
    return local.settings
```

## Performance Considerations

- **Initial Load**: `PGSettings()` reads and parses `pyproject.toml` once
- **Repeated Access**: Use a single instance across your application
- **Query Execution**: Pre-configured inserts are executed sequentially in order

```python
# Good: Reuse instance
settings = PGSettings()
for collection in collections:
    queries = settings.get_insert_sql(collection)
    # ...

# Avoid: Creating new instance each time
for collection in collections:
    queries = PGSettings().get_insert_sql(collection)  # Inefficient
```

## Version Compatibility

- **Python**: 3.10+
- **psycopg**: 3.0+
- **render-engine**: 2025.10.2a1+

Next, see [examples](./03-usage.md) for practical applications.
