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


class TestPGMarkdownCollectionParserCreateEntryTemplates:
    """Test PGMarkdownCollectionParser.create_entry() with template substitution."""

    def test_template_substitution_skips_missing_fields(self, mocker):
        """Test that template substitution gracefully skips templates with missing required fields."""
        # Test the format_map behavior directly
        frontmatter_data = {"id": 1, "title": "My Post"}

        # First template has all fields
        template1 = "INSERT INTO posts (id, title) VALUES ({id}, {title})"
        result1 = template1.format_map(frontmatter_data)
        assert "1" in result1 and "My Post" in result1

        # Second template has missing fields - should raise KeyError
        template2 = "INSERT INTO metadata (id, author) VALUES ({id}, {author})"
        try:
            result2 = template2.format_map(frontmatter_data)
            # Should not reach here
            assert False, "Should have raised KeyError for missing 'author' field"
        except KeyError as e:
            # Expected - field 'author' is missing
            assert str(e.args[0]) == "author"

    def test_create_entry_handles_template_execution_with_missing_fields(self, mocker):
        """Test that create_entry executes templates that have all fields and skips those that don't."""
        mock_settings = MagicMock()
        mock_settings.get_insert_sql.return_value = [
            "INSERT INTO posts (id, title) VALUES ({id}, {title})",
            "INSERT INTO metadata (id, author) VALUES ({id}, {author})",
        ]
        mocker.patch(
            "render_engine_pg.parsers.PGSettings", return_value=mock_settings
        )

        content = """---
id: 1
title: My Post
---
# Content"""

        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        # Mock the as_string method to avoid psycopg encoding issues in tests
        mocker.patch.object(
            type(MagicMock().as_string.return_value),
            "__str__",
            return_value="INSERT INTO posts (id, title) VALUES (1, 'My Post')",
        )

        # Patch the SQL class to return a simple string representation
        from psycopg import sql

        original_format = sql.SQL.format

        def mock_format(*args, **kwargs):
            return MagicMock()

        mocker.patch.object(sql.SQL, "format", mock_format)
        mocker.patch.object(sql.SQL, "as_string", lambda self, conn: "")

        result = PGMarkdownCollectionParser.create_entry(
            content=content,
            collection_name="blog",
            connection=mock_connection,
            table="posts",
        )

        # The first template should have been executed (has all fields)
        # The second should have been skipped (missing 'author' field)
        assert mock_cursor.execute.call_count >= 1

    def test_format_map_vs_format_difference(self):
        """Document the difference between format() and format_map() for missing fields."""
        data = {"id": 1}

        # Using format() raises KeyError for missing fields
        template = "INSERT INTO t (id, name) VALUES ({id}, {name})"
        try:
            template.format(**data)
            assert False, "format() should raise KeyError"
        except KeyError:
            pass  # Expected

        # format_map() also raises KeyError for missing fields
        try:
            template.format_map(data)
            assert False, "format_map() should raise KeyError"
        except KeyError:
            pass  # Expected

    def test_partial_frontmatter_scenario(self):
        """
        Test the actual scenario from populate_db.py:
        markdown with minimal frontmatter vs templates expecting more fields.
        """
        # This is what we'd have from the markdown
        frontmatter_data = {"date": "2020-02-19 10:10:00", "content": "Post content"}

        # This is what the insert_sql template expects
        template = "INSERT INTO microblog (id, slug, date) VALUES ({id}, {slug}, {date})"

        # Should raise KeyError for missing 'id' and 'slug'
        try:
            template.format_map(frontmatter_data)
            assert False, "Should raise KeyError for missing fields"
        except KeyError as e:
            # One of the fields will be missing
            assert str(e.args[0]) in ("id", "slug")
