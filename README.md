# render-engine-pg

A PostgreSQL plugin for [render-engine](https://render-engine.io) that enables creating pages and collections from database queries, with support for configuration-driven insert handling.

## Features

- **Database-Driven Content** - Create pages and collections directly from PostgreSQL queries
- **Markdown Support** - Parse and insert markdown content with YAML frontmatter
- **Configuration-Based Inserts** - Define pre-configured SQL insert statements in `pyproject.toml`
- **Collection Integration** - Full integration with render-engine's Collection system
- **Flexible Parsing** - Custom parsers for different content types
- **Type-Safe** - Full type hints and Python 3.10+ support

## Quick Features

- **CLI Tool** - Generate TOML configuration from SQL schema files with `@collection`, `@attribute`, and `@junction` annotations
- **PostgresContentManager** - Automatically fetch collection pages from database queries defined in `pyproject.toml`
- **Smart Relationships** - Auto-generate JOINs for foreign keys and many-to-many relationships with array aggregation
- **Column Control** - Mark columns to ignore with `-- ignore` comments or CLI flags (`--ignore-pk`, `--ignore-timestamps`)

## Installation

```bash
pip install render-engine-pg
```

Or with development dependencies:

```bash
pip install render-engine-pg[dev]
```

## Quick Start

### 1. Define Your Database Schema

Create `schema.sql` with render-engine annotations:

```sql
-- @collection
CREATE TABLE blog (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(255) UNIQUE NOT NULL,
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
    blog_id INTEGER NOT NULL REFERENCES blog(id),
    tag_id INTEGER NOT NULL REFERENCES tags(id),
    PRIMARY KEY (blog_id, tag_id)
);
```

### 2. Generate Configuration with CLI

```bash
uv run python -m render_engine_pg.cli.sql_cli schema.sql -o config.toml
```

This generates `config.toml` with `insert_sql` and `read_sql`. Merge into `pyproject.toml`.

### 3. Set Up Database Connection

```python
from render_engine_pg.connection import get_db_connection

connection = get_db_connection(
    host="localhost",
    database="mydb",
    user="postgres",
    password="secret"
)
```

### 4. Create Your Collections

```python
from render_engine import Site, Collection
from render_engine_pg.content_manager import PostgresContentManager
from render_engine_pg.parsers import PGPageParser

site = Site()

@site.collection
class Blog(Collection):
    ContentManager = PostgresContentManager
    content_manager_extras = {"connection": connection}
    parser = PGPageParser
    routes = ["blog/{slug}/"]
```

The `ContentManager` automatically loads `read_sql['blog']` from `pyproject.toml` and fetches data from your database.

## Usage Examples

### Blog with Tags (PostgreSQL)

**Database Schema:**

```sql
-- @collection
CREATE TABLE posts (id SERIAL PRIMARY KEY, slug VARCHAR(255), title VARCHAR(255), ...);

-- @attribute
CREATE TABLE tags (id SERIAL PRIMARY KEY, name VARCHAR(100) -- @aggregate);

-- @junction
CREATE TABLE post_tags (post_id INT REFERENCES posts(id), tag_id INT REFERENCES tags(id));
```

**Generated Configuration:**

```toml
[tool.render-engine.pg.read_sql]
posts = "SELECT posts.*, array_agg(DISTINCT tags.name) as tag_names FROM posts LEFT JOIN post_tags ... GROUP BY posts.id"
```

**Collection Definition:**

```python
@site.collection
class Posts(Collection):
    ContentManager = PostgresContentManager
    content_manager_extras = {"connection": connection}
    parser = PGPageParser
    routes = ["blog/{slug}/"]
```

### Documentation Site

**Collection for documentation pages:**

```python
@site.collection
class Documentation(Collection):
    ContentManager = PostgresContentManager
    content_manager_extras = {"connection": connection}
    parser = PGPageParser
    routes = ["docs/{slug}/"]
```

### Product Catalog

```python
@site.collection
class Products(Collection):
    ContentManager = PostgresContentManager
    content_manager_extras = {
        "connection": connection,
        "collection_name": "products"  # Override lookup name if needed
    }
    parser = PGPageParser
    routes = ["products/{slug}/"]
```

## Configuration

Settings are read from `[tool.render-engine.pg]` in `pyproject.toml`. Generate this automatically with the CLI:

```bash
uv run python -m render_engine_pg.cli.sql_cli schema.sql --ignore-pk --ignore-timestamps
```

This creates:

```toml
[tool.render-engine.pg.read_sql]
# SQL SELECT queries for fetching collection pages
blog = "SELECT blog.id, blog.slug, blog.title, blog.content FROM blog ORDER BY date DESC"
docs = "SELECT docs.id, docs.slug, docs.content FROM docs"

[tool.render-engine.pg.insert_sql]
# Dependency-ordered INSERT statements with get-or-create pattern for attributes
blog = [
    "INSERT INTO tags (name) VALUES (...) ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING id;",
    "INSERT INTO blog_tags (blog_id, tag_id) VALUES (...);",
    "INSERT INTO blog (slug, title, content, date) VALUES (...);"
]
```

See [Configuration Guide](./docs/content/docs/02-configuration.md) for complete details.

## Documentation

Full documentation is available in the `docs/` folder:

- [Overview](./docs/content/docs/01-overview.md) - What and why
- [Configuration](./docs/content/docs/02-configuration.md) - Configuration reference
- [Usage Guide](./docs/content/docs/03-usage.md) - Practical examples
- [API Reference](./docs/content/docs/04-api-reference.md) - Complete API docs

### View Documentation Site

```bash
cd docs/output
python -m http.server 8000
# Visit http://localhost:8000
```

### Build Documentation

```bash
cd docs
python build.py
```

See [DOCS.md](./DOCS.md) for documentation development guide.

## Architecture

### Core Components

- **`PostgresContentManager`** - Fetches collection pages from database queries in `pyproject.toml`
- **`PGPageParser`** - Parses database query results into page attributes
- **`PGSettings`** - Loads configuration from `[tool.render-engine.pg]` in `pyproject.toml`
- **CLI Tools** - Generate TOML configuration from SQL schema files
- **Connection utilities** - PostgreSQL connection management

### Data Flow

```
schema.sql (with @annotations)
    ↓
CLI Tool
    ↓
pyproject.toml [tool.render-engine.pg]
    ↓
render-engine Collection
    ↓
PostgresContentManager (loads read_sql query)
    ↓
PGPageParser (parses database rows)
    ↓
Generated static pages
```

## Testing

Run the test suite:

```bash
# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=render_engine_pg

# Run specific test file
python -m pytest tests/test_re_settings_parser.py -v
```

All tests pass ✓ (125 tests total)

## Project Structure

```
render-engine-pg-parser/
├── render_engine_pg/              # Main package
│   ├── __init__.py               # Package exports
│   ├── connection.py             # Database connection utilities
│   ├── page.py                   # Custom Page object
│   ├── parsers.py                # Page parsers
│   ├── content_manager.py        # Content manager
│   ├── re_settings_parser.py     # Settings loader (NEW)
│   └── cli/                      # Command-line tools
│       ├── sql_parser.py
│       ├── query_generator.py
│       ├── relationship_analyzer.py
│       └── sql_cli.py
├── tests/                        # Test suite (125 tests)
│   ├── test_re_settings_parser.py (NEW)
│   ├── test_connection.py
│   ├── test_sql_cli.py
│   └── ...
├── docs/                         # Documentation site (render-engine)
│   ├── build.py                  # Build script
│   ├── content/docs/             # Markdown docs
│   ├── templates/                # Jinja2 templates
│   ├── static/                   # CSS and assets
│   └── output/                   # Generated static site
├── pyproject.toml               # Project config
├── README.md                    # This file
└── DOCS.md                      # Documentation guide
```

## Requirements

- Python 3.10+
- psycopg 3.0+
- render-engine 2025.10.2a1+
- python-frontmatter 1.0+

## CLI Tools

Generate TOML configuration from SQL schema files:

```bash
uv run python -m render_engine_pg.cli.sql_cli schema.sql -o config.toml
```

**Options:**

- `-o, --output` - Output TOML file (default: stdout)
- `-v, --verbose` - Show debug information
- `--ignore-pk` - Exclude PRIMARY KEY columns from INSERT statements
- `--ignore-timestamps` - Exclude TIMESTAMP columns from INSERT statements
- `--objects` - Filter by object types (collection, attribute, junction, page)

**Example:**

```bash
uv run python -m render_engine_pg.cli.sql_cli schema.sql \
  --ignore-pk \
  --ignore-timestamps \
  -o config.toml
```

This generates `insert_sql` and `read_sql` with proper dependency ordering and relationship handling.

## Examples

### Blog Site

**1. Create schema.sql:**

```sql
-- @collection
CREATE TABLE posts (
    id SERIAL PRIMARY KEY, -- ignore
    slug VARCHAR(255) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW() -- ignore
);
```

**2. Generate config:**

```bash
uv run python -m render_engine_pg.cli.sql_cli schema.sql --ignore-pk --ignore-timestamps
```

**3. Define collection:**

```python
from render_engine import Site, Collection
from render_engine_pg.content_manager import PostgresContentManager
from render_engine_pg.parsers import PGPageParser
from render_engine_pg.connection import get_db_connection

db = get_db_connection(
    host="localhost",
    database="my_blog",
    user="postgres",
    password="secret"
)

site = Site()

@site.collection
class Posts(Collection):
    ContentManager = PostgresContentManager
    content_manager_extras = {"connection": db}
    parser = PGPageParser
    routes = ["blog/{slug}/"]
```

### Multiple Collections

```python
@site.collection
class Posts(Collection):
    ContentManager = PostgresContentManager
    content_manager_extras = {"connection": db}
    parser = PGPageParser
    routes = ["blog/{slug}/"]

@site.collection
class Documentation(Collection):
    ContentManager = PostgresContentManager
    content_manager_extras = {"connection": db}
    parser = PGPageParser
    routes = ["docs/{slug}/"]
```

Both automatically use their lowercased class names to look up `read_sql` from `pyproject.toml`.

## Troubleshooting

### Connection Issues

Verify connection parameters:
```python
from render_engine_pg.connection import get_db_connection

try:
    connection = get_db_connection(
        host="localhost",
        database="mydb",
        user="postgres",
        password="secret"
    )
    print("Connected!")
except Exception as e:
    print(f"Connection failed: {e}")
```

### Settings Not Loading

Ensure `pyproject.toml` exists in parent directory:
```bash
# From your Python script's directory
python -c "from render_engine_pg.re_settings_parser import PGSettings; print(PGSettings().settings)"
```

### Insert Queries Not Executing

Check configuration and spelling:
```python
from render_engine_pg.re_settings_parser import PGSettings

settings = PGSettings()
print(settings.settings)  # Verify settings loaded
print(settings.get_insert_sql("posts"))  # Check specific collection
```

See [Troubleshooting Guide](./docs/content/docs/03-usage.md#troubleshooting) for more help.

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Ensure all tests pass: `pytest`
5. Update documentation
6. Submit a pull request

## Development Setup

```bash
# Clone repository
git clone https://github.com/your-username/render-engine-pg-parser.git
cd render-engine-pg-parser

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Build documentation
cd docs
python build.py
```

## License

[Your License Here]

## Related Projects

- [render-engine](https://render-engine.io) - Static site generator for Python
- [render-engine-markdown](https://github.com/kjaymiller/render-engine-markdown) - Markdown parser for render-engine
- [psycopg](https://www.psycopg.org/) - PostgreSQL adapter for Python

## Support

- 📖 [Documentation](./DOCS.md)
- 🐛 [Issues](https://github.com/your-username/render-engine-pg-parser/issues)
- 💬 [Discussions](https://github.com/your-username/render-engine-pg-parser/discussions)

## Changelog

### [Unreleased]

#### Added
- Collection-based insert configuration in `pyproject.toml`
- `PGSettings` class for loading render-engine plugin settings
- Support for pre-configured SQL insert statements
- Comprehensive documentation site with render-engine
- API reference and usage guides
- Tests for new settings parser functionality

#### Changed
- Updated `PGMarkdownCollectionParser.create_entry()` to support `collection_name` parameter
- Enhanced documentation structure

### [0.1.0] - Initial Release

- Database-driven content parsing
- Markdown with frontmatter support
- CLI tools for schema analysis

---

Built with ❤️ for the [render-engine](https://render-engine.io) community
