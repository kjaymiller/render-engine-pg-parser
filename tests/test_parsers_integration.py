"""Integration tests for PGPageParser with real pyproject.toml configuration."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from psycopg.rows import dict_row

from render_engine_pg.parsers import PGPageParser
from render_engine_pg.connection import PostgresQuery
from render_engine_pg.re_settings_parser import PGSettings


@pytest.fixture
def temp_pyproject_with_read_sql():
    """Create a temporary pyproject.toml with read_sql configuration."""
    toml_content = """[tool.render-engine.pg]
read_sql = { blog = "SELECT id, title, slug FROM blog_posts WHERE id = %s", tags = "SELECT id, tag_name, post_count FROM tags", authors = "SELECT id, name, email FROM authors" }
"""
    with tempfile.TemporaryDirectory() as tmpdir:
        pyproject_path = Path(tmpdir) / "pyproject.toml"
        pyproject_path.write_text(toml_content)
        yield tmpdir, pyproject_path


@pytest.fixture
def mock_connection_for_integration():
    """Create a mock connection for integration tests."""
    mock_conn = MagicMock()
    mock_conn.autocommit = True
    return mock_conn


class TestPGPageParserIntegration:
    """Integration tests for PGPageParser with pyproject.toml."""

    def test_single_row_with_real_settings(self, temp_pyproject_with_read_sql, mock_connection_for_integration):
        """Test single row query using collection_name with real settings loading."""
        tmpdir, pyproject_path = temp_pyproject_with_read_sql

        # Setup mock cursor
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"id": 1, "title": "First Post", "slug": "first-post"}
        ]
        mock_connection_for_integration.cursor.return_value.__enter__.return_value = mock_cursor

        # Create PostgresQuery with collection_name
        query = PostgresQuery(
            connection=mock_connection_for_integration,
            collection_name="blog"
        )

        # Load settings from temp pyproject.toml
        settings = PGSettings(config_path=pyproject_path)
        read_sql = settings.get_read_sql("blog")

        # Verify settings loaded correctly
        assert read_sql is not None
        assert "SELECT" in read_sql
        assert "blog_posts" in read_sql

    def test_multiple_rows_with_real_settings(self, temp_pyproject_with_read_sql, mock_connection_for_integration):
        """Test multiple rows query using collection_name with real settings."""
        tmpdir, pyproject_path = temp_pyproject_with_read_sql

        # Setup mock cursor for multiple rows
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"id": 1, "tag_name": "python", "post_count": 10},
            {"id": 2, "tag_name": "database", "post_count": 8},
            {"id": 3, "tag_name": "web", "post_count": 12},
        ]
        mock_connection_for_integration.cursor.return_value.__enter__.return_value = mock_cursor

        # Create settings with temp pyproject
        settings = PGSettings(config_path=pyproject_path)
        read_sql = settings.get_read_sql("tags")

        # Verify we got the right query
        assert read_sql is not None
        assert "tags" in read_sql

    def test_multiple_collections_in_settings(self, temp_pyproject_with_read_sql, mock_connection_for_integration):
        """Test that multiple collections can be configured."""
        tmpdir, pyproject_path = temp_pyproject_with_read_sql

        settings = PGSettings(config_path=pyproject_path)

        # Verify all three collections are configured
        blog_sql = settings.get_read_sql("blog")
        tags_sql = settings.get_read_sql("tags")
        authors_sql = settings.get_read_sql("authors")

        assert blog_sql is not None
        assert tags_sql is not None
        assert authors_sql is not None

        # Verify they're different queries
        assert "blog_posts" in blog_sql
        assert "tags" in tags_sql
        assert "authors" in authors_sql

    def test_nonexistent_collection_returns_none(self, temp_pyproject_with_read_sql):
        """Test that asking for non-existent collection returns None."""
        tmpdir, pyproject_path = temp_pyproject_with_read_sql

        settings = PGSettings(config_path=pyproject_path)
        result = settings.get_read_sql("nonexistent_collection")

        assert result is None

    def test_parser_with_collection_name_integration(
        self, temp_pyproject_with_read_sql, mock_connection_for_integration, mocker
    ):
        """Test full integration: PGPageParser using collection_name with real settings."""
        tmpdir, pyproject_path = temp_pyproject_with_read_sql

        # Setup mock cursor
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"id": 42, "title": "Integration Test", "slug": "integration-test"}
        ]
        mock_connection_for_integration.cursor.return_value.__enter__.return_value = mock_cursor

        # Patch PGSettings to use our temp pyproject
        original_find = PGSettings._find_pyproject_toml

        def mock_find(*args, **kwargs):
            return pyproject_path

        mocker.patch.object(PGSettings, "_find_pyproject_toml", side_effect=mock_find)

        # Create query using collection_name
        query = PostgresQuery(
            connection=mock_connection_for_integration,
            collection_name="blog"
        )

        # Parse the content
        attrs, data = PGPageParser.parse_content_path(query)

        # Verify results
        assert attrs["id"] == 42
        assert attrs["title"] == "Integration Test"
        assert attrs["slug"] == "integration-test"
        assert data is None

    def test_parser_with_multiple_rows_collection_integration(
        self, temp_pyproject_with_read_sql, mock_connection_for_integration, mocker
    ):
        """Test PGPageParser with multiple rows using collection_name."""
        tmpdir, pyproject_path = temp_pyproject_with_read_sql

        # Setup mock cursor for multiple rows
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"id": 1, "tag_name": "python", "post_count": 15},
            {"id": 2, "tag_name": "rust", "post_count": 8},
        ]
        mock_connection_for_integration.cursor.return_value.__enter__.return_value = mock_cursor

        # Patch settings
        def mock_find(*args, **kwargs):
            return pyproject_path

        mocker.patch.object(PGSettings, "_find_pyproject_toml", side_effect=mock_find)

        # Create query using collection_name
        query = PostgresQuery(
            connection=mock_connection_for_integration,
            collection_name="tags"
        )

        # Parse
        attrs, data = PGPageParser.parse_content_path(query)

        # Verify list results
        assert "data" in attrs
        assert len(attrs["data"]) == 2
        assert attrs["id"] == [1, 2]
        assert attrs["tag_name"] == ["python", "rust"]
        assert attrs["post_count"] == [15, 8]
