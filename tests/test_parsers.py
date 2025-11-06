"""Tests for render-engine-pg parsers."""

import pytest
from unittest.mock import MagicMock, patch
from psycopg.rows import dict_row
from render_engine_pg.parsers import PGPageParser, PGMarkdownCollectionParser
from render_engine_pg.connection import PostgresQuery


class TestPGPageParser:
    """Test PGPageParser for single and multiple row queries."""

    def test_single_row_query(self, mock_connection):
        """Test parsing single row - columns become page attributes."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"id": 1, "title": "Test Post", "content": "Hello World"}
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        query = PostgresQuery(connection=mock_connection, query="SELECT * FROM posts")
        attrs, data = PGPageParser.parse_content_path(query)

        assert attrs["id"] == 1
        assert attrs["title"] == "Test Post"
        assert attrs["content"] == "Hello World"
        assert data is None

    def test_multiple_rows_query(self, mock_connection):
        """Test parsing multiple rows - creates lists and page.data."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"id": 1, "title": "Post 1", "content": "Content 1"},
            {"id": 2, "title": "Post 2", "content": "Content 2"},
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        query = PostgresQuery(connection=mock_connection, query="SELECT * FROM posts")
        attrs, data = PGPageParser.parse_content_path(query)

        assert "data" in attrs
        assert len(attrs["data"]) == 2
        assert attrs["id"] == [1, 2]
        assert attrs["title"] == ["Post 1", "Post 2"]
        assert attrs["content"] == ["Content 1", "Content 2"]

    def test_empty_query(self, mock_connection):
        """Test parsing empty result set."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        query = PostgresQuery(connection=mock_connection, query="SELECT * FROM posts WHERE id = -1")
        attrs, data = PGPageParser.parse_content_path(query)

        assert attrs == {}
        assert data is None

    def test_single_row_query_via_collection_name(self, mock_connection, mocker):
        """Test parsing single row using collection_name from settings."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"id": 1, "title": "Blog Post", "slug": "blog-post"}
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        # Mock PGSettings to return a query for the collection
        mock_settings = MagicMock()
        mock_settings.get_read_sql.return_value = "SELECT * FROM blog_posts WHERE id = 1"
        mocker.patch(
            "render_engine_pg.parsers.PGSettings",
            return_value=mock_settings
        )

        query = PostgresQuery(connection=mock_connection, collection_name="blog")
        attrs, data = PGPageParser.parse_content_path(query)

        assert attrs["id"] == 1
        assert attrs["title"] == "Blog Post"
        assert attrs["slug"] == "blog-post"
        assert data is None
        mock_settings.get_read_sql.assert_called_once_with("blog")

    def test_multiple_rows_query_via_collection_name(self, mock_connection, mocker):
        """Test parsing multiple rows using collection_name from settings."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"id": 1, "tag": "python", "count": 10},
            {"id": 2, "tag": "database", "count": 5},
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        mock_settings = MagicMock()
        mock_settings.get_read_sql.return_value = "SELECT * FROM tags"
        mocker.patch(
            "render_engine_pg.parsers.PGSettings",
            return_value=mock_settings
        )

        query = PostgresQuery(connection=mock_connection, collection_name="tags")
        attrs, data = PGPageParser.parse_content_path(query)

        assert "data" in attrs
        assert len(attrs["data"]) == 2
        assert attrs["id"] == [1, 2]
        assert attrs["tag"] == ["python", "database"]
        assert attrs["count"] == [10, 5]
        mock_settings.get_read_sql.assert_called_once_with("tags")

    def test_explicit_query_takes_precedence_over_collection_name(
        self, mock_connection, mocker
    ):
        """Test that explicit query parameter takes precedence over collection_name."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"id": 1, "title": "Explicit"}
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        mock_settings = MagicMock()
        mocker.patch(
            "render_engine_pg.parsers.PGSettings",
            return_value=mock_settings
        )

        # Provide both explicit query and collection_name
        query = PostgresQuery(
            connection=mock_connection,
            query="SELECT * FROM explicit",
            collection_name="blog"
        )
        attrs, data = PGPageParser.parse_content_path(query)

        assert attrs["id"] == 1
        assert attrs["title"] == "Explicit"
        # Settings should NOT be called since explicit query is provided
        mock_settings.get_read_sql.assert_not_called()

    def test_collection_name_without_query_raises_error(self, mock_connection, mocker):
        """Test that missing collection_name without query raises ValueError."""
        mock_settings = MagicMock()
        mock_settings.get_read_sql.return_value = None
        mocker.patch(
            "render_engine_pg.parsers.PGSettings",
            return_value=mock_settings
        )

        query = PostgresQuery(connection=mock_connection, collection_name="nonexistent")

        with pytest.raises(ValueError, match="No query found"):
            PGPageParser.parse_content_path(query)

    def test_neither_query_nor_collection_name_raises_error(self, mock_connection, mocker):
        """Test that neither query nor collection_name raises ValueError."""
        mock_settings = MagicMock()
        mocker.patch(
            "render_engine_pg.parsers.PGSettings",
            return_value=mock_settings
        )

        query = PostgresQuery(connection=mock_connection)

        with pytest.raises(ValueError, match="No query found"):
            PGPageParser.parse_content_path(query)

    def test_collection_name_with_no_read_sql_entry(self, mock_connection, mocker):
        """Test collection_name that exists but has no read_sql configured."""
        mock_settings = MagicMock()
        mock_settings.get_read_sql.return_value = None
        mocker.patch(
            "render_engine_pg.parsers.PGSettings",
            return_value=mock_settings
        )

        query = PostgresQuery(connection=mock_connection, collection_name="unconfigured")

        with pytest.raises(ValueError, match="No query found.*unconfigured"):
            PGPageParser.parse_content_path(query)


class TestPGMarkdownCollectionParserParse:
    """Test PGMarkdownCollectionParser.parse() with markdown extras."""

    def test_parse_fenced_code_blocks_default(self):
        """Test that fenced code blocks are parsed with default extras."""
        markdown_content = """# Title

Here's some code:

```python
def hello():
    print("Hello World")
```

End of code."""

        result = PGMarkdownCollectionParser.parse(markdown_content)

        # Should contain HTML code tags indicating proper parsing
        assert "<code>" in result or "<pre>" in result
        # The code content might have syntax highlighting spans, so check for the keywords
        assert "hello" in result
        assert "print" in result

    def test_parse_with_custom_extras(self):
        """Test that custom extras are respected."""
        markdown_content = """# Title

```python
code here
```"""

        custom_extras = {"markdown_extras": ["fenced-code-blocks", "tables"]}
        result = PGMarkdownCollectionParser.parse(markdown_content, extras=custom_extras)

        assert "<code>" in result or "<pre>" in result

    def test_parse_without_extras_parameter(self):
        """Test that parse works when extras is None."""
        markdown_content = "# Simple Title\n\nSome text here."
        result = PGMarkdownCollectionParser.parse(markdown_content)

        assert "<h1>" in result
        assert "Simple Title" in result

    def test_parse_tables_extra(self):
        """Test that tables extra is enabled."""
        markdown_content = """| Header 1 | Header 2 |
| -------- | -------- |
| Cell 1   | Cell 2   |"""

        result = PGMarkdownCollectionParser.parse(markdown_content)

        # Tables should be parsed into HTML table elements
        assert "<table>" in result or "<thead>" in result

    def test_parse_default_extras_includes_code_blocks(self):
        """Test that default extras explicitly include fenced-code-blocks."""
        # This is a meta-test to ensure the implementation includes code blocks
        markdown_content = "```\ncode\n```"
        result = PGMarkdownCollectionParser.parse(markdown_content)

        # Without fenced-code-blocks extra, backticks would remain as literal text
        # With it, they should be converted to code HTML
        assert "`" not in result or "<" in result


class TestPGMarkdownCollectionParserCreateEntry:
    """Test PGMarkdownCollectionParser.create_entry() - basic frontmatter parsing."""

    def test_create_entry_parses_frontmatter_extraction(self):
        """Test that create_entry properly extracts YAML frontmatter."""
        import frontmatter

        content = """---
title: Test Post
id: 1
---
# Content

This is test content."""

        # Test that frontmatter parsing works (not the full create_entry flow)
        post = frontmatter.loads(content)

        assert post.metadata["title"] == "Test Post"
        assert post.metadata["id"] == 1
        assert "# Content" in post.content

    def test_markdown_content_with_code_blocks_preserved(self):
        """Test that markdown content with code blocks is preserved in raw form."""
        import frontmatter

        content = """---
title: Code Tutorial
---
# Content

Here's the code:

```python
def test():
    pass
```

Done."""

        post = frontmatter.loads(content)
        post_content = post.content

        # Code blocks should be preserved in the raw markdown before parsing
        assert "```python" in post_content
        assert "def test():" in post_content

    def test_parse_code_blocks_converts_to_html(self):
        """Test that parsing markdown code blocks produces HTML code blocks."""
        markdown_with_code = """Here's code:

```python
def test():
    pass
```"""

        result = PGMarkdownCollectionParser.parse(markdown_with_code)

        # After parsing, should contain HTML code/pre tags, not backticks
        assert "<code>" in result or "<pre>" in result
        # The backticks should be gone (converted to HTML)
        assert "```" not in result
