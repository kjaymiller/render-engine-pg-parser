# Documentation

The documentation for the render-engine-pg settings parser feature is built as a static site using render-engine.

## Quick Start

### View the Documentation

The documentation is pre-built and ready to view:

```bash
cd docs/output
python -m http.server 8000
```

Then visit `http://localhost:8000/docs/` in your browser.

### Build the Documentation

To rebuild the documentation after making changes:

```bash
cd docs
python build.py
```

This regenerates all HTML files in the `output/` directory.

## Documentation Structure

The docs/ folder contains a complete render-engine static site:

```
docs/
├── build.py                    # Build script and site configuration
├── content/docs/              # Markdown documentation files
│   ├── 01-overview.md        # Overview of the feature
│   ├── 02-configuration.md   # Configuration guide
│   ├── 03-usage.md           # Usage examples and patterns
│   └── 04-api-reference.md   # Complete API reference
├── templates/                 # Jinja2 HTML templates
│   ├── base.html             # Main layout
│   ├── doc.html              # Doc page template
│   └── index.html            # Index template
├── static/css/style.css       # Styling
└── output/                    # Generated static site (gitignored)
    ├── index.html
    ├── docs/
    │   ├── overview.html
    │   ├── configuration.html
    │   ├── usage.html
    │   └── api-reference.html
    └── static/css/style.css
```

## Documentation Contents

### 1. Overview
- What the collection-based insert configuration feature does
- Key features and benefits
- When to use this feature
- Quick start guide

### 2. Configuration
- Complete configuration reference
- Settings structure and options
- Multiple examples
- Error handling and defaults
- Best practices

### 3. Usage Guide
- Basic usage examples
- Real-world use cases (blog, e-commerce, docs site)
- Advanced patterns
- Troubleshooting
- Without collection names (backward compatibility)

### 4. API Reference
- `PGSettings` class API
- `PGMarkdownCollectionParser.create_entry()` method
- Configuration schema
- Type hints
- Performance considerations
- Thread safety

## Editing Documentation

### Adding a New Page

1. Create a new markdown file in `docs/content/docs/`:

```markdown
---
title: Your Page Title
slug: your-page-slug
layout: doc
---

# Your Page Title

Your content here...
```

2. Rebuild the site:
```bash
cd docs
python build.py
```

3. Check your changes:
```bash
cd output
python -m http.server 8000
```

### Editing Existing Pages

1. Edit the markdown file in `docs/content/docs/`
2. Rebuild the site: `python build.py`
3. Preview the changes

### Customizing Styling

Edit `docs/static/css/style.css` to customize the appearance. The CSS includes:

- Color scheme variables
- Typography
- Layout (navbar, sidebar, main content)
- Responsive design
- Code highlighting

### Customizing Templates

Edit template files in `docs/templates/`:

- `base.html` - Main layout, header, footer, navigation
- `doc.html` - Specific styling for doc pages (if needed)
- `index.html` - Homepage specific styling

All templates use Jinja2 syntax.

## Deployment

### GitHub Pages

Copy the contents of `docs/output/` to a `gh-pages` branch:

```bash
# Build docs
cd docs
python build.py

# Deploy (example)
cp -r output/* ../my-gh-pages-branch/
cd ../my-gh-pages-branch
git add .
git commit -m "Update docs"
git push origin gh-pages
```

### Netlify

1. Connect your repository to Netlify
2. Set build command: `cd docs && python build.py`
3. Set publish directory: `docs/output`
4. Deploy

### Self-Hosted / AWS S3 / Other

Simply upload the contents of `docs/output/` to your hosting:

```bash
# AWS S3 example
aws s3 sync docs/output/ s3://my-bucket/docs/
```

## Generated Files

The `build.py` script generates:

- HTML files for each markdown page
- `docs.rss` - RSS feed of documentation updates
- Copies of static assets (CSS, etc.)
- Proper URL structure for navigation

## Technology Stack

- **render-engine** - Static site generator for Python
- **Jinja2** - HTML templating
- **Markdown** - Content format
- **CSS** - Styling (vanilla, no frameworks)
- **Python** - Build scripting

## Configuration

The site configuration is defined in `docs/build.py`:

```python
# Site variables
site.update_site_vars(
    SITE_TITLE="render-engine-pg Documentation",
    SITE_URL="https://example.com/docs/",
    SITE_DESCRIPTION="...",
)

# Paths
site.output_path = DOCS_DIR / "output"
site._template_path = DOCS_DIR / "templates"
site.static_paths = {DOCS_DIR / "static"}
```

## Troubleshooting

### Build fails with "jinja2.exceptions.TemplateNotFound"

Make sure you're running `build.py` from the `docs/` directory:
```bash
cd docs
python build.py
```

### Changes not appearing in output

Rebuild the site:
```bash
python build.py
```

Clear your browser cache or use incognito mode.

### CSS not loading

Make sure static paths are configured correctly in `build.py` and files exist in `docs/static/`.

## Contributing to Documentation

When contributing:

1. Write clear, concise documentation
2. Include practical examples
3. Add troubleshooting sections for complex topics
4. Keep code samples up-to-date
5. Use consistent markdown formatting
6. Test the build process locally

## See Also

- [render-engine documentation](https://render-engine.io)
- [Jinja2 template documentation](https://jinja.palletsprojects.com/)
- [Markdown guide](https://www.markdownguide.org/)
