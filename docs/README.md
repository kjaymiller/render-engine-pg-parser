# Documentation Site

This is the documentation site for the render-engine-pg collection-based insert configuration feature. It's built using [render-engine](https://render-engine.io), a static site generator for Python.

## Structure

```
docs/
├── build.py                    # Site configuration and build script
├── content/
│   └── docs/                  # Documentation markdown files
│       ├── 01-overview.md
│       ├── 02-configuration.md
│       ├── 03-usage.md
│       └── 04-api-reference.md
├── templates/                 # Jinja2 templates
│   ├── base.html             # Main template with header/footer
│   ├── doc.html              # Documentation page template
│   └── index.html            # Index page template
├── static/
│   └── css/
│       └── style.css         # Site styling
├── output/                    # Generated static site (created by build)
└── README.md                 # This file
```

## Building the Documentation

### Prerequisites

The docs use the same render-engine installation as the main project:

```bash
pip install render-engine
```

### Build

From the docs directory:

```bash
cd docs
python build.py
```

This generates the static site in `output/`.

### View

Serve the generated site:

```bash
# Using Python's built-in server
cd output
python -m http.server 8000
```

Then visit `http://localhost:8000` in your browser.

## Adding Documentation

To add new documentation pages:

1. Create a new markdown file in `content/docs/`:
   ```markdown
   ---
   title: Page Title
   slug: page-slug
   layout: doc
   ---

   # Your Content Here
   ```

2. Build the site:
   ```bash
   python build.py
   ```

## Customizing the Site

### Styles

Edit `static/css/style.css` to customize the appearance.

### Templates

The templates use [Jinja2](https://jinja.palletsprojects.com/). Edit templates in the `templates/` directory:

- `base.html` - Main layout with navigation and footer
- `doc.html` - Documentation page specific template
- `index.html` - Homepage template

### Site Configuration

Edit `build.py` to modify:

- Site variables (title, URL, description)
- Routes and output paths
- Collection sorting and pagination

## Documentation Contents

The documentation covers:

1. **Overview** - What the feature does and why
2. **Configuration** - How to configure `pyproject.toml`
3. **Usage Guide** - Practical examples and patterns
4. **API Reference** - Complete API documentation

## Deployment

The generated `output/` directory can be deployed to any static hosting service:

- GitHub Pages
- Netlify
- AWS S3 + CloudFront
- Any HTTP server

Simply upload the contents of `output/` to your hosting provider.

## Development Workflow

```bash
# 1. Edit markdown in content/docs/
vim content/docs/new-page.md

# 2. Build the site
python build.py

# 3. Preview in browser
cd output && python -m http.server 8000

# 4. Commit changes
git add content/ templates/ static/
git commit -m "Update documentation"
```

## Technologies

- **render-engine** - Static site generator
- **Jinja2** - Template engine
- **Markdown** - Content format
- **CSS** - Styling (vanilla, no frameworks)

## License

Same as render-engine-pg project.
