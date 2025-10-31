# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`render-engine-pg` is a PostgreSQL plugin for [render-engine](https://render-engine.io) that enables creating pages and collections from database queries. It provides database-driven content parsing, markdown support with YAML frontmatter, and configuration-driven SQL insert handling via `pyproject.toml`.

Key use case: Define SQL INSERT statements in `pyproject.toml` under `[tool.render-engine.pg]`, then use them automatically when creating collection entries.

## Essential Commands

### Development & Testing
```bash
# Install in development mode
uv pip install -e ".[test]"

# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_parsers.py -v

# Run with coverage
uv run pytest --cov=render_engine_pg

# Run single test
uv run pytest tests/test_query_generator.py::TestBasicQueryGeneration::test_simple_insert_query -v
```

### CLI Tool
```bash
# Generate TOML config with insert_sql and read_sql from SQL schema
uv run python -m render_engine_pg.cli.sql_cli schema.sql

# Output to file
uv run python -m render_engine_pg.cli.sql_cli schema.sql -o config.toml

# With verbose output
uv run python -m render_engine_pg.cli.sql_cli schema.sql -v

# Filter by object types
uv run python -m render_engine_pg.cli.sql_cli schema.sql --objects collections attributes
```

### Documentation
```bash
# Build documentation site
cd docs && uv run python build.py

# View docs locally
cd docs/output && python -m http.server 8000
# Visit http://localhost:8000
```

## Architecture

### Core Components

1. **Parsers** (`render_engine_pg/parsers.py`)
   - `PGPageParser`: Converts database query results into page attributes
     - Single row: attributes become page properties
     - Multiple rows: creates list attributes + `page.data` with all rows
   - `PGMarkdownCollectionParser`: Parses markdown with frontmatter, executes pre-configured inserts

2. **Settings & Configuration** (`render_engine_pg/re_settings_parser.py`)
   - `PGSettings`: Loads `[tool.render-engine.pg]` from `pyproject.toml`
   - Manages `insert_sql` (dict of queries per collection) and `read_sql` (select queries)
   - Supports both string and list formats for `insert_sql`

3. **Connection Management** (`render_engine_pg/connection.py`)
   - `PostgresQuery`: NamedTuple holding connection + query string
   - `get_db_connection()`: Creates psycopg connection from host/db/user/password or connection string

4. **Content Manager** (`render_engine_pg/content_manager.py`)
   - `PostgresContentManager`: Yields multiple Page objects from a database query

5. **CLI Tools** (`render_engine_pg/cli/`)
   - `SQLParser`: Parses CREATE TABLE statements, extracts columns and object types from comments (`@page`, `@collection`, `@attribute`, `@junction`)
   - `RelationshipAnalyzer`: Detects foreign keys and many-to-many relationships
   - `InsertionQueryGenerator`: Generates INSERT statements in proper dependency order
   - `ReadQueryGenerator`: Generates SELECT statements with appropriate JOINs
   - `TOMLConfigGenerator`: Produces TOML config grouped by collection name

### Data Flow: SQL Schema → TOML Config

```
SQL Schema File (with @comments)
    ↓
SQLParser → Extract objects, columns, types
    ↓
RelationshipAnalyzer → Find FKs and M2M relationships
    ↓
InsertionQueryGenerator → Generate INSERT in dependency order
ReadQueryGenerator → Generate SELECT with JOINs
    ↓
TOMLConfigGenerator → Group by collection, output as TOML
    ↓
pyproject.toml [tool.render-engine.pg]
```

### TOML Output Structure

The CLI generates this structure:
```toml
[tool.render-engine.pg.insert_sql]
collection_name = [
    "INSERT INTO dependency_table ...",
    "INSERT INTO collection_table ...",
    "INSERT INTO junction_table ...",
]

[tool.render-engine.pg.read_sql]
collection_name = "SELECT collection_table ... LEFT JOIN dependency_table ..."
```

This allows multiple collections in one `pyproject.toml`.

## Key Implementation Details

### SQL Schema Annotations
Mark tables with comments to identify their type:
```sql
-- @collection
CREATE TABLE blog (id SERIAL PRIMARY KEY, ...);

-- @attribute
CREATE TABLE tags (id SERIAL PRIMARY KEY, ...);

-- @junction
CREATE TABLE blog_tags (blog_id INT, tag_id INT, ...);
```

### Query Generation Dependencies
- `InsertionQueryGenerator.generate()` returns `(ordered_objects, queries)` tuple
- Objects are topologically sorted so dependencies insert first (tags before blog_tags)
- `TOMLConfigGenerator` uses ordered objects to correctly map queries to collection names

### Read Query Generation
- Uses metadata from `RelationshipAnalyzer` to find junction table names and FK column names
- Generates LEFT JOINs through junction tables for many-to-many relationships
- Only generates forward relationships (not duplicates for reverse M2M)

### Settings Loading
`PGSettings` searches up the directory tree for `pyproject.toml`:
```python
from render_engine_pg.re_settings_parser import PGSettings

settings = PGSettings()
# Access via: settings.settings['insert_sql'], settings.get_insert_sql(collection_name)
```

## Common Patterns

### Single Query → Single Page Attributes
```python
from render_engine_pg import PostgresQuery, PGPageParser

query = PostgresQuery(
    connection=db,
    query="SELECT id, title, content FROM posts WHERE id = 1"
)
page = Page(content_path=query, parser=PGPageParser)
# page.id, page.title, page.content available
```

### Multiple Rows → Collection with Lists
```python
@site.collection
class AllPosts(Collection):
    content_path = PostgresQuery(
        connection=db,
        query="SELECT * FROM posts"
    )
    parser = PGPageParser
# page.data has all rows; page.id, page.title, etc. are lists
```

### Pre-Configured Inserts
```python
# In pyproject.toml:
# [tool.render-engine.pg]
# insert_sql = { blog = ["INSERT INTO tags ...", "INSERT INTO blog ..."] }

result = PGMarkdownCollectionParser.create_entry(
    content="---\ntitle: My Post\n---\nContent",
    collection_name="blog",
    connection=db,
    table="posts"
)
# Inserts execute automatically before markdown insert
```

## Testing Patterns

- Tests use `pytest` with fixtures from `conftest.py`
- Mock database connections with `pytest-mock`
- Query generator tests focus on dependency ordering and placeholder format
- Parser tests verify attribute extraction and data handling

## Files You'll Most Often Edit

1. `render_engine_pg/parsers.py` - Page/collection parsing logic
2. `render_engine_pg/cli/query_generator.py` - INSERT statement generation
3. `render_engine_pg/cli/read_query_generator.py` - SELECT statement generation
4. `render_engine_pg/cli/toml_generator.py` - TOML output format
5. `render_engine_pg/re_settings_parser.py` - Settings loading and access

## Dependencies & Versions

- Python 3.10+
- psycopg 3.0+ (PostgreSQL adapter)
- render-engine 2025.10.2a1+ (static site generator)
- python-frontmatter 1.0+ (YAML frontmatter parsing)
- click 8.3.0+ (CLI framework)
- tomli_w 1.0.0+ (TOML writing)

Install: `uv pip install -e ".[test]"` (uses uv for package management)
