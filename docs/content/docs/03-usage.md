---
title: Usage Guide
slug: usage
layout: doc
---

# Usage Guide

Learn how to use collection-based insert configuration in your render-engine PostgreSQL project.

## Basic Usage

### 1. Define Configuration

In your `pyproject.toml`:

```toml
[tool.render-engine.pg]
insert_sql = { blog_posts = "INSERT INTO authors (name) VALUES ('John Doe')" }
```

### 2. Use in Code

```python
from render_engine_pg.parsers import PGMarkdownCollectionParser
from render_engine_pg.connection import get_db_connection

# Get database connection
connection = get_db_connection(
    host="localhost",
    database="myblog",
    user="postgres",
    password="secret"
)

# Create entry with pre-configured inserts
result = PGMarkdownCollectionParser.create_entry(
    content="""---
title: My First Post
author: John Doe
---

This is my first blog post!
""",
    collection_name="blog_posts",
    connection=connection,
    table="posts"
)

print(f"Created post with query: {result}")
```

## Real-World Examples

### Blog with Categories and Tags

**Configuration:**

```toml
[tool.render-engine.pg]
insert_sql = {
    blog_posts = """
        INSERT INTO categories (name) VALUES ('Technology');
        INSERT INTO categories (name) VALUES ('Travel');
        INSERT INTO categories (name) VALUES ('Lifestyle')
    """
}
```

**Code:**

```python
# This will create the categories before inserting the post
PGMarkdownCollectionParser.create_entry(
    content=post_markdown,
    collection_name="blog_posts",
    connection=db,
    table="posts",
    category_id=1  # Can reference the inserted categories
)
```

### E-Commerce Product Collection

**Configuration:**

```toml
[tool.render-engine.pg]
insert_sql = {
    products = [
        "INSERT INTO suppliers (name) VALUES ('Supplier A')",
        "INSERT INTO suppliers (name) VALUES ('Supplier B')",
        "INSERT INTO product_statuses (status) VALUES ('active')",
        "INSERT INTO product_statuses (status) VALUES ('discontinued')"
    ]
}
```

**Code:**

```python
for product_data in products:
    PGMarkdownCollectionParser.create_entry(
        content=product_data["markdown"],
        collection_name="products",
        connection=db,
        table="products",
        supplier_id=1,
        status_id=1
    )
```

### Documentation Site

**Configuration:**

```toml
[tool.render-engine.pg]
insert_sql = {
    docs = "INSERT INTO doc_versions (version) VALUES ('1.0.0')",
    api_reference = "INSERT INTO api_categories (name) VALUES ('REST'); INSERT INTO api_categories (name) VALUES ('GraphQL')"
}
```

**Code:**

```python
# Create documentation
PGMarkdownCollectionParser.create_entry(
    content=doc_markdown,
    collection_name="docs",
    connection=db,
    table="pages",
    doc_version_id=1
)

# Create API reference
PGMarkdownCollectionParser.create_entry(
    content=api_markdown,
    collection_name="api_reference",
    connection=db,
    table="pages",
    category_id=1
)
```

## Advanced Patterns

### Conditional Inserts

Use Python logic to choose which collection to use:

```python
from render_engine_pg.parsers import PGMarkdownCollectionParser

def create_post(markdown, post_type="article"):
    collection_name = f"blog_{post_type}"

    return PGMarkdownCollectionParser.create_entry(
        content=markdown,
        collection_name=collection_name,
        connection=db,
        table="posts"
    )

# Uses different pre-configured inserts based on post type
create_post(markdown, "article")   # Uses blog_article config
create_post(markdown, "tutorial")  # Uses blog_tutorial config
```

### Programmatic Settings Access

```python
from render_engine_pg.re_settings_parser import PGSettings

settings = PGSettings()

# Get all queries for a collection
queries = settings.get_insert_sql("my_collection")

# Check if collection has inserts configured
if queries:
    print(f"Found {len(queries)} pre-configured inserts")
else:
    print("No pre-configured inserts for this collection")

# Use settings in your logic
for query in queries:
    cursor.execute(query)
```

### Multi-Stage Inserts

Split complex setups across multiple collections:

```toml
[tool.render-engine.pg]
insert_sql = {
    collection_setup = "-- Initial setup\nINSERT INTO config (key, value) VALUES ('initialized', 'true')",
    collection_main = "-- Main collection inserts\nINSERT INTO roles (name) VALUES ('admin'); INSERT INTO roles (name) VALUES ('user')"
}
```

```python
# First, run setup
PGMarkdownCollectionParser.create_entry(
    content="---\ntitle: Setup\n---",
    collection_name="collection_setup",
    connection=db,
    table="setup_log"
)

# Then run main logic
PGMarkdownCollectionParser.create_entry(
    content=main_markdown,
    collection_name="collection_main",
    connection=db,
    table="pages"
)
```

## Without Collection Names

If you don't use `collection_name`, the code works exactly as before:

```python
# This will NOT execute any pre-configured inserts
PGMarkdownCollectionParser.create_entry(
    content=markdown,
    connection=db,
    table="pages"
)
```

All existing code remains compatible.

## Troubleshooting

### Pre-configured inserts aren't executing

**Check:**
1. Is `collection_name` passed to `create_entry()`?
2. Does the `pyproject.toml` have the `[tool.render-engine.pg]` section?
3. Is the collection name spelled correctly in both config and code?

```python
# Debug: Check loaded settings
from render_engine_pg.re_settings_parser import PGSettings

settings = PGSettings()
print(f"Loaded settings: {settings.settings}")
print(f"Queries for 'my_collection': {settings.get_insert_sql('my_collection')}")
```

### SQL syntax errors

**Verify:**
1. Each query is valid SQL
2. Queries are properly terminated (either with `;` or as separate list items)
3. No trailing commas in semicolon-separated format

```toml
# ✓ Good
insert_sql = { posts = "INSERT INTO users (name) VALUES ('Alice'); INSERT INTO users (name) VALUES ('Bob')" }

# ✗ Bad - trailing semicolon creates empty query
insert_sql = { posts = "INSERT INTO users (name) VALUES ('Alice');" }

# ✓ Good - empty queries are filtered
insert_sql = { posts = "INSERT INTO users (name) VALUES ('Alice');;" }
```

### Settings not loading

Ensure `pyproject.toml` is in a parent directory of your Python script:

```
project-root/
├── pyproject.toml           # Must be here or parent
├── src/
│   └── my_app.py           # Script looking for settings
└── venv/
```

Next, see [API reference](./04-api-reference.md).
