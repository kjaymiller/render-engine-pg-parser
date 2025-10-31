---
title: Overview
slug: overview
layout: doc
---

# render-engine PostgreSQL Plugin

The render-engine PostgreSQL plugin enables you to build static sites with database-driven content. It provides:

1. **Automated Configuration Generation** - Generate TOML config from SQL schema
2. **Collection Management** - Fetch pages from PostgreSQL via SQL queries
3. **Smart Relationship Handling** - Auto-generate queries for foreign keys and many-to-many relationships

## What It Does

### Generate Configuration from Schema

Use the CLI tool to automatically generate your configuration from a SQL schema file:

```bash
uv run python -m render_engine_pg.cli.sql_cli schema.sql -o config.toml
```

Input schema:
```sql
-- @collection
CREATE TABLE blog (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(255) NOT NULL,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    date TIMESTAMP NOT NULL
);

-- @attribute
CREATE TABLE tags (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL -- @aggregate
);

-- @junction
CREATE TABLE blog_tags (
    blog_id INT REFERENCES blog(id),
    tag_id INT REFERENCES tags(id)
);
```

Generated configuration:
```toml
[tool.render-engine.pg.read_sql]
blog = "SELECT blog.*, array_agg(DISTINCT tags.name) as tags_names FROM blog LEFT JOIN blog_tags ... GROUP BY blog.id"

[tool.render-engine.pg.insert_sql]
blog = [
    "INSERT INTO tags (name) VALUES (...)",
    "INSERT INTO blog_tags (blog_id, tag_id) VALUES (...)",
    "INSERT INTO blog (slug, title, content, date) VALUES (...)"
]
```

### Use Collections in Your Site

Define a Collection class that fetches data from the database:

```python
from render_engine import Collection
from render_engine_pg.content_manager import PostgresContentManager
from render_engine_pg.parsers import PGPageParser
from render_engine_pg.connection import get_db_connection

connection = get_db_connection(
    host="localhost",
    database="myblog",
    user="postgres",
    password="secret"
)

@site.collection
class Blog(Collection):
    """Blog posts fetched from PostgreSQL"""

    ContentManager = PostgresContentManager
    content_manager_extras = {"connection": connection}

    parser = PGPageParser
    routes = ["blog/{slug}/"]
```

The `ContentManager` automatically:
- Looks up `read_sql['blog']` from `pyproject.toml`
- Executes the query against your database
- Yields a Page object for each row
- Makes all columns available as page attributes

## Key Features

- **CLI Configuration Generation** - Automatically create TOML from SQL schema
- **Intelligent Relationship Handling** - Auto-generates JOINs for foreign keys and M2M relationships
- **Dependency Ordering** - INSERT statements execute in correct order
- **Array Aggregation** - Combine related data into arrays with `@aggregate` annotations
- **Column Filtering** - Mark columns to ignore in INSERT statements with `-- ignore` comments
- **Automatic Name Lookup** - Collections automatically use their lowercased class name to look up config

## When to Use This

✓ You have a PostgreSQL database powering your static site
✓ You want collections from database queries instead of files
✓ You have complex relationships (foreign keys, many-to-many)
✓ You want configuration generated from schema, not hand-written
✓ You need array aggregation of related records

## Typical Workflow

1. **Define your database schema** with render-engine annotations
2. **Run the CLI tool** to generate TOML configuration
3. **Define your Collection classes** using PostgresContentManager
4. **Build your site** - render-engine handles fetching and rendering

```bash
# Step 1: Define schema.sql with annotations
# Step 2: Generate config
uv run python -m render_engine_pg.cli.sql_cli schema.sql -o config.toml

# Step 3: Merge config.toml into pyproject.toml
# Step 4: Define collections in Python
# Step 5: Build site
uv run render-engine build
```

## File Structure

```
your-project/
├── pyproject.toml              # Configuration with [tool.render-engine.pg]
├── schema.sql                  # Database schema with annotations
├── src/
│   └── main.py                 # Collection definitions
└── output/                     # Built site
```

Next, learn how to [configure your setup](./02-configuration.md).
