# render-engine-pg

A PostgreSQL plugin for [render-engine](https://render-engine.io) that enables creating pages and collections from database queries, with support for configuration-driven insert handling.

## Features

- **Database-Driven Content** - Create pages and collections directly from PostgreSQL queries
- **Markdown Support** - Parse and insert markdown content with YAML frontmatter
- **Configuration-Based Inserts** - Define pre-configured SQL insert statements in `pyproject.toml`
- **Collection Integration** - Full integration with render-engine's Collection system
- **Flexible Parsing** - Custom parsers for different content types
- **Type-Safe** - Full type hints and Python 3.10+ support

## What's New

### Collection-Based Insert Configuration

Define pre-configured SQL insert statements in your `pyproject.toml` and execute them automatically when creating entries:

```toml
[tool.render-engine.pg]
insert_sql = { posts = "INSERT INTO authors (name) VALUES ('John Doe')" }
```

Then use them in your code:

```python
PGMarkdownCollectionParser.create_entry(
    content="---\ntitle: My Post\n---\nContent",
    collection_name="posts",
    connection=db,
    table="posts"
)
```

The pre-configured inserts execute automatically before the markdown entry is inserted.

## Installation

```bash
pip install render-engine-pg
```

Or with development dependencies:

```bash
pip install render-engine-pg[dev]
```

## Quick Start

### 1. Set Up Database Connection

```python
from render_engine_pg.connection import get_db_connection

connection = get_db_connection(
    host="localhost",
    database="mydb",
    user="postgres",
    password="secret"
)
```

Or use a connection string:

```python
connection = get_db_connection(
    connection_string="postgresql://user:pass@localhost/mydb"
)
```

### 2. Configure Insert SQL in `pyproject.toml`

```toml
[tool.render-engine.pg]
insert_sql = {
    blog_posts = "INSERT INTO categories (name) VALUES ('Tech'); INSERT INTO categories (name) VALUES ('Travel')"
}
```

### 3. Use in Your Site

```python
from render_engine import Site, Collection
from render_engine_pg.parsers import PGPageParser, PGMarkdownCollectionParser
from render_engine_pg import PostgresQuery

site = Site()

@site.collection
class BlogPosts(Collection):
    content_path = PostgresQuery(
        connection=connection,
        query="SELECT * FROM posts ORDER BY created_at DESC"
    )
    parser = PGPageParser

@site.collection
class BlogEntries(Collection):
    parser = PGMarkdownCollectionParser
    # Pre-configured inserts will execute automatically
    # for collection_name="blog_entries"
```

## Usage Examples

### Single Record to Page Attributes

```python
from render_engine_pg.parsers import PGPageParser

# Query returns one row
postgres_query = PostgresQuery(
    connection=connection,
    query="SELECT id, title, content, author FROM posts WHERE id = 1"
)

# Attributes become page attributes
page = Page(content_path=postgres_query, parser=PGPageParser)
# page.id, page.title, page.content, page.author are available
```

### Multiple Records to Collection

```python
from render_engine_pg.parsers import PGPageParser

# Query returns multiple rows
postgres_query = PostgresQuery(
    connection=connection,
    query="SELECT * FROM posts"
)

@site.collection
class AllPosts(Collection):
    content_path = postgres_query
    parser = PGPageParser
    # page.data contains all rows
    # page.id, page.title, etc. contain lists of values
```

### Markdown with Pre-Configured Inserts

```python
from render_engine_pg.parsers import PGMarkdownCollectionParser

# Configure in pyproject.toml:
# [tool.render-engine.pg]
# insert_sql = { my_posts = "INSERT INTO authors..." }

# Create entry - inserts execute automatically
result = PGMarkdownCollectionParser.create_entry(
    content="---\ntitle: My Post\nauthor: Jane\n---\nContent",
    collection_name="my_posts",
    connection=connection,
    table="posts"
)
```

## Configuration

Settings are read from `[tool.render-engine.pg]` in `pyproject.toml`:

```toml
[tool.render-engine.pg]
# Define SQL insert statements for collections
insert_sql = {
    posts = "INSERT INTO users (name) VALUES ('Alice'); INSERT INTO users (name) VALUES ('Bob')",
    comments = ["INSERT INTO statuses (status) VALUES ('active')", "INSERT INTO statuses (status) VALUES ('pending')"]
}

# Optional: Default table name
default_table = "pages"

# Optional: Auto-commit transactions (default: true)
auto_commit = true
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

- **`PGPageParser`** - Parse single query results into page attributes
- **`PGMarkdownCollectionParser`** - Convert markdown with frontmatter to SQL inserts
- **`PostgresContentManager`** - Yield multiple pages from database queries
- **`PGSettings`** - Load and manage settings from `pyproject.toml`
- **Connection utilities** - PostgreSQL connection management

### Data Flow

```
pyproject.toml [tool.render-engine.pg]
    ↓
PGSettings (loads configuration)
    ↓
PGMarkdownCollectionParser.create_entry()
    ↓
Execute pre-configured inserts + markdown insert
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

Generate INSERT statements from SQL schema files:

```bash
render-engine-pg schema.sql -o inserts.sql --verbose
```

Options:
- `-o, --output` - Output file (default: stdout)
- `--verbose` - Show debug information
- `--format` - Output format: sql or json (default: sql)
- `--objects` - Filter by object types: page, collection, attribute, junction

See [CLI Guide](./docs/content/docs/03-usage.md#cli-tools) for details.

## Examples

### Blog Site

```python
from render_engine import Site
from render_engine_pg.connection import get_db_connection
from render_engine_pg.parsers import PGPageParser
from render_engine_pg import PostgresQuery

# Connect to database
db = get_db_connection(
    host="localhost",
    database="my_blog",
    user="postgres",
    password="secret"
)

# Create site
site = Site()
site.update_site_vars(SITE_TITLE="My Blog")

# Blog posts collection
@site.collection
class BlogPosts:
    content_path = PostgresQuery(
        connection=db,
        query="SELECT id, title, content, author, created_at FROM posts ORDER BY created_at DESC"
    )
    parser = PGPageParser
    routes = ["blog/"]
    sort_by = "created_at"
```

### E-Commerce Product Pages

```python
# Configure in pyproject.toml:
# [tool.render-engine.pg]
# insert_sql = { products = "INSERT INTO suppliers...; INSERT INTO categories..." }

@site.collection
class Products:
    content_path = PostgresQuery(
        connection=db,
        query="SELECT * FROM products WHERE active = true"
    )
    parser = PGPageParser
    routes = ["products/"]
```

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
