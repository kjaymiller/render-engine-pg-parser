---
title: Usage Guide
order: 3
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
render-engine-pg sql schema.sql -o config.toml

# Or with options to ignore PRIMARY KEY and TIMESTAMP columns
render-engine-pg sql schema.sql \
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

## Populating the Database from Markdown

Once you've created your database schema and configuration, you can populate the database from markdown files using the populate command.

### Basic Workflow

1. **Create markdown files** with YAML frontmatter in a directory:

```markdown
---
title: My First Post
tags: [python, render-engine]
---

# My First Post

This is the content of my first blog post.
```

2. **Set database connection**:

```bash
export CONNECTION_STRING="postgresql://user:password@localhost:5432/myblog"
```

3. **Run populate command**:

```bash
render-engine-pg populate blog content/blog/
```

### How Populate Works

The populate command:

1. Scans the directory for `.md` files
2. For each file:
   - Reads the YAML frontmatter as metadata
   - Derives a slug from the filename (e.g., `my-first-post.md` → `my-first-post`)
   - Executes the pre-configured `insert_sql` templates from `pyproject.toml`
   - Inserts the metadata and content into the database

### Markdown File Format

Your markdown files should have YAML frontmatter with fields matching your database columns:

```markdown
---
title: Post Title
tags: [tag1, tag2]
author: John Doe
date: 2024-01-15
---

# Post Title

Your content goes here...
```

The fields in the frontmatter become values for the SQL placeholders in your `insert_sql` templates.

### Example Configuration

Given this `pyproject.toml`:

```toml
[tool.render-engine.pg.insert_sql]
blog = [
    "INSERT INTO tags (name) VALUES ({tags}) ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING id;",
    "INSERT INTO blog (slug, title, content, author) VALUES ({slug}, {title}, {content}, {author});"
]
```

When you run:

```bash
render-engine-pg populate blog content/blog/
```

For each markdown file:
- `{slug}` is derived from the filename
- `{title}`, `{tags}`, `{author}` come from the frontmatter
- `{content}` is the markdown body after frontmatter

### Verbose Mode

Get detailed information about what's being inserted:

```bash
render-engine-pg populate blog content/blog/ -v
```

This shows:
- Found insert_sql templates
- Processing each file
- Success/failure for each insertion

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
    "INSERT INTO authors (name) VALUES ({name}) ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING id;",
    "INSERT INTO categories (name) VALUES ({name}) ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING id;",
    "INSERT INTO posts (slug, title, content, author_id, category_id) VALUES ({slug}, {title}, {content}, {author_id}, {category_id});"
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
    "INSERT INTO tags (name) VALUES ({name}) ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING id;",
    "INSERT INTO blog_tags (blog_id, tag_id) VALUES ({blog_id}, {tag_id});",
    "INSERT INTO blog (slug, title, content, date) VALUES ({slug}, {title}, {date});"
]
```

The INSERT statements execute in order when data is being set up. Attribute tables with UNIQUE constraints use the get-or-create pattern (`ON CONFLICT ... DO UPDATE ... RETURNING id`) to safely handle repeated runs while capturing the correct ID for relationships.

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

Define multiple collections, each with its own configuration from `pyproject.toml`:

```python
@site.collection
class Blog(Collection):
    """Blog posts with tags"""
    ContentManager = PostgresContentManager
    content_manager_extras = {"connection": connection}
    parser = PGPageParser
    routes = ["blog/{slug}/"]

@site.collection
class Microblog(Collection):
    """Short-form posts with tags"""
    ContentManager = PostgresContentManager
    content_manager_extras = {"connection": connection}
    parser = PGPageParser
    routes = ["micro/{slug}/"]

@site.collection
class Documentation(Collection):
    """API documentation pages"""
    ContentManager = PostgresContentManager
    content_manager_extras = {"connection": connection}
    parser = PGPageParser
    routes = ["docs/{slug}/"]
```

**Configuration in `pyproject.toml`:**

```toml
[tool.render-engine.pg.read_sql]
blog = "SELECT blog.id, blog.slug, blog.title, blog.content, blog.date, array_agg(DISTINCT tags.name) as tags_names FROM blog LEFT JOIN blog_tags ON blog.id = blog_tags.blog_id LEFT JOIN tags ON blog_tags.tag_id = tags.id GROUP BY blog.id ORDER BY blog.date DESC;"

microblog = "SELECT microblog.id, microblog.slug, microblog.content, microblog.external_link, microblog.created_at, array_agg(DISTINCT tags.name) as tags_names FROM microblog LEFT JOIN microblog_tags ON microblog.id = microblog_tags.microblog_id LEFT JOIN tags ON microblog_tags.tag_id = tags.id GROUP BY microblog.id ORDER BY microblog.created_at DESC;"

documentation = "SELECT id, slug, title, content, version FROM documentation ORDER BY version DESC;"

[tool.render-engine.pg.insert_sql]
blog = [
    "INSERT INTO tags (name) VALUES ({name}) ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING id;",
    "INSERT INTO blog (slug, title, content, date) VALUES ({slug}, {title}, {content}, {date});",
    "INSERT INTO blog_tags (blog_id, tag_id) VALUES ({blog_id}, {tag_id});"
]

microblog = [
    "INSERT INTO tags (name) VALUES ({name}) ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING id;",
    "INSERT INTO microblog (slug, content, external_link, created_at) VALUES ({slug}, {content}, {external_link}, {created_at});",
    "INSERT INTO microblog_tags (microblog_id, tag_id) VALUES ({microblog_id}, {tag_id});"
]

documentation = [
    "INSERT INTO documentation (slug, title, content, version) VALUES ({slug}, {title}, {content}, {version});"
]
```

**Key Points:**
- Each collection's Python class name (lowercased) must match the dictionary key in `read_sql` and `insert_sql`
- Collections can share attributes (like `tags`) - the CLI automatically includes shared attributes in each collection's INSERT list
- Each collection independently fetches its data using its own `read_sql` query
- Shared attributes use the `ON CONFLICT` pattern to avoid duplicates across collections

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
