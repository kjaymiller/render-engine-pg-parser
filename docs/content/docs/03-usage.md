---
title: Usage Guide
slug: usage
layout: doc
---

# Usage Guide

Learn how to set up collections with PostgreSQL in your render-engine site.

## Basic Workflow

### 1. Define Your Database Schema

Create a SQL schema file with render-engine annotations:

```sql
-- @collection
CREATE TABLE IF NOT EXISTS blog (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(255) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    date TIMESTAMP NOT NULL
);

-- @attribute
CREATE TABLE IF NOT EXISTS tags (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL -- @aggregate
);

-- @junction
CREATE TABLE IF NOT EXISTS blog_tags (
    blog_id INTEGER NOT NULL REFERENCES blog(id),
    tag_id INTEGER NOT NULL REFERENCES tags(id),
    PRIMARY KEY (blog_id, tag_id)
);
```

### 2. Generate Configuration with CLI

Use the SQL CLI tool to generate your TOML configuration from the schema:

```bash
uv run python -m render_engine_pg.cli.sql_cli schema.sql -o config.toml

# Or with options
uv run python -m render_engine_pg.cli.sql_cli schema.sql \
  --ignore-pk \
  --ignore-timestamps \
  -o config.toml
```

This generates a `config.toml` with:
```toml
[tool.render-engine.pg.insert_sql]
blog = [
    "INSERT INTO tags (name) VALUES (...)",
    "INSERT INTO blog_tags (blog_id, tag_id) VALUES (...)",
    "INSERT INTO blog (slug, title, content, date) VALUES (...)"
]

[tool.render-engine.pg.read_sql]
blog = "SELECT blog.id, blog.slug, blog.title, blog.content, blog.date, array_agg(DISTINCT tags.name) as tags_names FROM blog LEFT JOIN blog_tags ON blog.id = blog_tags.blog_id LEFT JOIN tags ON blog_tags.tag_id = tags.id GROUP BY blog.id, blog.slug, blog.title, blog.content, blog.date ORDER BY blog.date DESC;"
```

Merge this into your `pyproject.toml`.

### 3. Define Your Collection Class

Create a Collection class that uses the generated `read_sql`:

```python
from render_engine import Collection
from render_engine_pg.content_manager import PostgresContentManager
from render_engine_pg.parsers import PGPageParser
from render_engine_pg.connection import get_db_connection

# Get database connection
connection = get_db_connection(
    host="localhost",
    database="myblog",
    user="postgres",
    password="secret"
)

@site.collection
class Blog(Collection):
    """Blog posts with tags"""

    ContentManager = PostgresContentManager
    content_manager_extras = {"connection": connection}

    parser = PGPageParser
    routes = ["blog/{slug}/"]
```

The `ContentManager` automatically:
- Looks up `read_sql` from `pyproject.toml` using the collection name (lowercased)
- Fetches data from the database
- Yields Page objects for each row

### 4. Access Collection Data

In your templates:

```jinja2
<h1>{{ page.title }}</h1>
<time>{{ page.date }}</time>
<p>{{ page.content }}</p>

{% if page.tags_names %}
<div class="tags">
  {% for tag in page.tags_names %}
    <span class="tag">{{ tag }}</span>
  {% endfor %}
</div>
{% endif %}
```

## Real-World Examples

### Blog with Multiple Authors and Categories

**Schema:**

```sql
-- @collection
CREATE TABLE IF NOT EXISTS posts (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(255) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    author_id INT NOT NULL REFERENCES authors(id),
    category_id INT NOT NULL REFERENCES categories(id),
    created_at TIMESTAMP DEFAULT NOW() -- ignore
);

-- @attribute
CREATE TABLE IF NOT EXISTS authors (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL
);

-- @attribute
CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL
);
```

**Generated TOML:**

```toml
[tool.render-engine.pg.insert_sql]
posts = [
    "INSERT INTO authors (name) VALUES (...)",
    "INSERT INTO categories (name) VALUES (...)",
    "INSERT INTO posts (slug, title, content, author_id, category_id) VALUES (...)"
]

[tool.render-engine.pg.read_sql]
posts = "SELECT posts.id, posts.slug, posts.title, posts.content, posts.author_id, posts.category_id, authors.name as author_name, categories.name as category_name FROM posts LEFT JOIN authors ON posts.author_id = authors.id LEFT JOIN categories ON posts.category_id = categories.id ORDER BY posts.created_at DESC;"
```

**Collection Definition:**

```python
@site.collection
class Posts(Collection):
    """Blog posts with author and category"""

    ContentManager = PostgresContentManager
    content_manager_extras = {"connection": connection}

    parser = PGPageParser
    routes = ["blog/{slug}/"]
```

**Template Usage:**

```jinja2
<article>
    <h1>{{ page.title }}</h1>
    <byline>By <a href="/authors/{{ page.author_name|slugify }}/">{{ page.author_name }}</a></byline>
    <p class="category"><a href="/categories/{{ page.category_name|slugify }}/">{{ page.category_name }}</a></p>
    <div class="content">{{ page.content }}</div>
</article>
```

### Product Catalog with Variants and Reviews

**Schema:**

```sql
-- @collection
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price DECIMAL(10, 2) NOT NULL
);

-- @attribute
CREATE TABLE product_variants (
    id SERIAL PRIMARY KEY,
    product_id INT NOT NULL REFERENCES products(id),
    size VARCHAR(50),
    color VARCHAR(50),
    sku VARCHAR(100) UNIQUE NOT NULL
);

-- @attribute
CREATE TABLE product_reviews (
    id SERIAL PRIMARY KEY,
    product_id INT NOT NULL REFERENCES products(id),
    rating INT NOT NULL,
    comment TEXT
);
```

**Generated Configuration & Collection:**

```python
@site.collection
class Products(Collection):
    ContentManager = PostgresContentManager
    content_manager_extras = {"connection": connection}

    parser = PGPageParser
    routes = ["products/{slug}/"]
```

### Documentation with Versioning

**Schema:**

```sql
-- @collection
CREATE TABLE docs (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(255) NOT NULL,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    version VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW() -- ignore
);

-- @attribute
CREATE TABLE doc_metadata (
    doc_id INT NOT NULL REFERENCES docs(id),
    last_updated TIMESTAMP DEFAULT NOW(),
    status VARCHAR(50) DEFAULT 'published'
);
```

**Collection Definition:**

```python
@site.collection
class Documentation(Collection):
    ContentManager = PostgresContentManager
    content_manager_extras = {"connection": connection}

    parser = PGPageParser
    routes = ["docs/{version}/{slug}/"]
```

## How insert_sql Works

When you generate `insert_sql` with the CLI tool, it creates dependency-ordered INSERT statements. This allows multiple related tables to be set up before the main collection table.

The CLI automatically:
1. Detects foreign key relationships
2. Orders INSERT statements by dependency
3. Filters out ignored columns (PRIMARY KEY, TIMESTAMP, etc.)
4. Groups all inserts for a collection together

**Example output:**

```toml
[tool.render-engine.pg.insert_sql]
blog = [
    "INSERT INTO tags (name) VALUES ('Technology'), ('Travel')",
    "INSERT INTO blog_tags (blog_id, tag_id) VALUES (1, 1), (1, 2)",
    "INSERT INTO blog (slug, title, content, date) VALUES ('my-post', 'My Post', '...', NOW())"
]
```

The INSERT statements execute in order when data is being set up through render-engine.

## Working with the CLI Tool

### Using Ignore Comments

Mark columns to exclude from INSERT statements:

```sql
CREATE TABLE posts (
    id SERIAL PRIMARY KEY, --ignore
    slug VARCHAR(255) NOT NULL,
    title VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW() -- ignore
);
```

This prevents `id` and `created_at` from appearing in INSERT statements, allowing PostgreSQL to auto-generate them.

### Using @aggregate Annotations

When a collection has many-to-many relationships with optional array aggregation:

```sql
-- @attribute
CREATE TABLE tags (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL -- @aggregate
);
```

The CLI generates array_agg in the read_sql:

```sql
SELECT blog.*, array_agg(DISTINCT tags.name) as tags_names
FROM blog
LEFT JOIN blog_tags ON blog.id = blog_tags.blog_id
LEFT JOIN tags ON blog_tags.tag_id = tags.id
GROUP BY blog.id, ...
```

## Collection Configuration Patterns

### Single Collection from One Table

```python
@site.collection
class Posts(Collection):
    ContentManager = PostgresContentManager
    content_manager_extras = {"connection": connection}
    parser = PGPageParser
    routes = ["blog/{slug}/"]
```

### Multiple Collections from Same Database

```python
@site.collection
class Posts(Collection):
    ContentManager = PostgresContentManager
    content_manager_extras = {"connection": connection}
    parser = PGPageParser
    routes = ["blog/{slug}/"]

@site.collection
class Documentation(Collection):
    ContentManager = PostgresContentManager
    content_manager_extras = {"connection": connection}
    parser = PGPageParser
    routes = ["docs/{slug}/"]
```

Both use their own `read_sql` query from `pyproject.toml`.

### With Custom Connection String

```python
from render_engine_pg.connection import get_db_connection

# From environment or config
connection = get_db_connection(
    connection_string="postgresql://user:password@localhost:5432/myblog"
)

@site.collection
class Posts(Collection):
    ContentManager = PostgresContentManager
    content_manager_extras = {"connection": connection}
    parser = PGPageParser
    routes = ["blog/{slug}/"]
```

## Troubleshooting

### ContentManager isn't fetching data

**Check:**
1. Is the `read_sql` generated in `pyproject.toml` under `[tool.render-engine.pg.read_sql]`?
2. Does the collection name (lowercased class name) match the key in `read_sql`?
3. Is the database connection correct?

```python
# Debug: Check loaded settings
from render_engine_pg.re_settings_parser import PGSettings

settings = PGSettings()
print(f"Read SQL: {settings.get_read_sql('blog')}")  # Use lowercased class name
```

### Collection name mismatch

The `ContentManager` looks up `read_sql` using the collection class name lowercased:

```python
class Blog(Collection):  # ← Will look for read_sql['blog']
    ContentManager = PostgresContentManager
    content_manager_extras = {"connection": connection}
```

If your read_sql is under a different name, use the `collection_name` parameter:

```python
@site.collection
class PostCollection(Collection):
    ContentManager = PostgresContentManager
    content_manager_extras = {
        "connection": connection,
        "collection_name": "posts"  # ← Override lookup name
    }
```

### CLI tool not generating correct queries

**Verify your schema:**
1. Tables are annotated with `-- @collection`, `-- @attribute`, or `-- @junction`
2. Foreign keys are defined with `REFERENCES table(id)`
3. Columns to skip are marked with `-- ignore` comment

```sql
-- ✓ Good
-- @collection
CREATE TABLE posts (
    id SERIAL PRIMARY KEY, -- ignore
    slug VARCHAR(255) NOT NULL,
    title VARCHAR(255) NOT NULL
);

-- ✗ Bad - missing @collection annotation
CREATE TABLE posts (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(255) NOT NULL
);
```

### Settings not loading

Ensure `pyproject.toml` is in the project root or a parent directory:

```
project-root/
├── pyproject.toml           # Must be here or parent
├── src/
│   └── main.py
└── docs/
```

The `PGSettings()` class automatically searches parent directories.

Next, see [API reference](./04-api-reference.md).
