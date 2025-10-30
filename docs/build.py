"""
Render Engine documentation site configuration for render-engine-pg settings parser.
"""

from pathlib import Path
from render_engine import Site, Collection, Page
from render_engine_markdown import MarkdownPageParser


# Get the docs directory
DOCS_DIR = Path(__file__).parent.resolve()

# Initialize the site
site = Site()

# Configure site variables
site.update_site_vars(
    SITE_TITLE="render-engine-pg Documentation",
    SITE_URL="https://example.com/docs/",
    SITE_DESCRIPTION="Configuration-driven INSERT handling for render-engine PostgreSQL plugin",
)

# Set output and template paths
site.output_path = DOCS_DIR / "output"
site._template_path = DOCS_DIR / "templates"
site.static_paths = {DOCS_DIR / "static"}


# Documentation collection
@site.collection
class Docs(Collection):
    """Documentation pages collection."""

    content_path = DOCS_DIR / "content" / "docs"
    template = "base.html"
    parser = MarkdownPageParser
    sort_by = "title"
    routes = ["docs/"]


# Index/home page
@site.page
class Index(Page):
    """Documentation index page."""

    content = """---
title: render-engine-pg Settings Parser
layout: index
---

# render-engine-pg Settings Parser

Configuration-driven INSERT handling for the render-engine PostgreSQL plugin.

## Features

- **Centralized Configuration** - Define inserts in `pyproject.toml`
- **Collection-Based** - Map collections to pre-configured SQL statements
- **Flexible Format** - Use semicolon-separated strings or lists
- **Backward Compatible** - Optional parameter, existing code works unchanged
- **Auto-Discovery** - Settings loaded automatically at runtime

## Quick Links

- [Overview](./docs/overview/) - Start here
- [Configuration](./docs/configuration/) - Configure insert_sql
- [Usage Guide](./docs/usage/) - Real-world examples
- [API Reference](./docs/api-reference/) - Complete API documentation

## Installation

The settings parser is built into `render-engine-pg`:

```bash
pip install render-engine-pg
```

## Basic Usage

### 1. Configure in `pyproject.toml`

```toml
[tool.render-engine.pg]
insert_sql = { posts = "INSERT INTO authors (name) VALUES ('John Doe')" }
```

### 2. Use in Code

```python
from render_engine_pg.parsers import PGMarkdownCollectionParser

PGMarkdownCollectionParser.create_entry(
    content="---\ntitle: My Post\n---\nContent",
    collection_name="posts",
    connection=db,
    table="posts"
)
```

The pre-configured inserts execute automatically before the markdown entry is inserted.

## Documentation Structure

```
Getting Started
├── Overview - What and why
├── Configuration - How to configure
├── Usage Guide - Practical examples
└── API Reference - Complete API docs
```

## Next Steps

[Start with the Overview →](./docs/overview/)
"""

    slug = "index"
    layout = "base.html"


if __name__ == "__main__":
    site.render()
    print(f"Documentation built to: {site.output_path}")
