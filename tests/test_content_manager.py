"""Tests for PostgresContentManager.create_entry() functionality."""

import pytest
from unittest.mock import MagicMock, patch
from render_engine_pg.content_manager import PostgresContentManager
from render_engine_pg.connection import PostgresQuery
from render_engine_pg.page import PGPage
from render_engine_markdown import MarkdownPageParser


class TestPostgresContentManagerCreateEntry:
    """Test PostgresContentManager.create_entry() method."""

    def test_create_entry_calls_parser_with_database_parameters(self, mock_connection):
        """Test that create_entry calls parser's create_entry with correct database parameters."""
        # Setup collection mock
        mock_collection = MagicMock()
        mock_collection.__class__.__name__ = "BlogPosts"

        # Setup postgres_query
        postgres_query = PostgresQuery(
            connection=mock_connection,
            query="SELECT * FROM posts",
            collection_name="blog",
        )

        # Create content manager
        content_manager = PostgresContentManager(
            collection=mock_collection, postgres_query=postgres_query
        )

        # Mock PostgresContentManager's create_entry_static
        with patch.object(PostgresContentManager, "create_entry_static") as mock_create:
            mock_create.return_value = "INSERT INTO posts ..."

            result = content_manager.create_entry(
                content="---\ntitle: Test\n---\n# Hello",
                metadata={"author": "John"},
                table="posts",
            )

            # Verify parser was called with correct parameters
            mock_create.assert_called_once()
            call_args = mock_create.call_args

            assert call_args[1]["content"] == "---\ntitle: Test\n---\n# Hello"
            assert call_args[1]["connection"] == mock_connection
            assert call_args[1]["table"] == "posts"
            assert call_args[1]["collection_name"] == "blog"
            assert call_args[1]["author"] == "John"

            # Verify return message
            assert "INSERT INTO posts" in result

    def test_create_entry_uses_connection_from_postgres_query(self, mock_connection):
        """Test that create_entry uses the connection from postgres_query."""
        mock_collection = MagicMock()
        mock_collection.__class__.__name__ = "Posts"

        postgres_query = PostgresQuery(
            connection=mock_connection, query="SELECT * FROM posts"
        )

        content_manager = PostgresContentManager(
            collection=mock_collection, postgres_query=postgres_query
        )

        with patch.object(PostgresContentManager, "create_entry_static") as mock_create:
            mock_create.return_value = "INSERT query"

            content_manager.create_entry(content="# Test", table="posts")

            # Verify connection passed to parser
            call_args = mock_create.call_args
            assert call_args[1]["connection"] == mock_connection

    def test_create_entry_collection_name_from_postgres_query(self, mock_connection):
        """Test collection_name is taken from postgres_query.collection_name."""
        mock_collection = MagicMock()
        mock_collection.__class__.__name__ = "SomeClass"

        postgres_query = PostgresQuery(
            connection=mock_connection,
            query="SELECT * FROM posts",
            collection_name="custom_blog",
        )

        content_manager = PostgresContentManager(
            collection=mock_collection, postgres_query=postgres_query
        )

        with patch.object(PostgresContentManager, "create_entry_static") as mock_create:
            mock_create.return_value = "INSERT query"

            content_manager.create_entry(content="# Test")

            # Verify collection_name from postgres_query was used
            call_args = mock_create.call_args
            assert call_args[1]["collection_name"] == "custom_blog"

    def test_create_entry_collection_name_from_collection_attribute(
        self, mock_connection
    ):
        """Test collection_name falls back to collection.collection_name attribute."""
        mock_collection = MagicMock()
        mock_collection.collection_name = "articles"
        mock_collection.__class__.__name__ = "SomeClass"

        postgres_query = PostgresQuery(
            connection=mock_connection,
            query="SELECT * FROM posts",
            collection_name=None,
        )

        content_manager = PostgresContentManager(
            collection=mock_collection, postgres_query=postgres_query
        )

        with patch.object(PostgresContentManager, "create_entry_static") as mock_create:
            mock_create.return_value = "INSERT query"

            content_manager.create_entry(content="# Test")

            # Verify collection_name from collection attribute was used
            call_args = mock_create.call_args
            assert call_args[1]["collection_name"] == "articles"

    def test_create_entry_collection_name_from_class_name(self, mock_connection):
        """Test collection_name falls back to collection class name (lowercased)."""
        mock_collection = MagicMock()
        mock_collection.__class__.__name__ = "BlogPosts"
        # No collection_name attribute
        del mock_collection.collection_name

        postgres_query = PostgresQuery(
            connection=mock_connection,
            query="SELECT * FROM posts",
            collection_name=None,
        )

        content_manager = PostgresContentManager(
            collection=mock_collection, postgres_query=postgres_query
        )

        with patch.object(PostgresContentManager, "create_entry_static") as mock_create:
            mock_create.return_value = "INSERT query"

            content_manager.create_entry(content="# Test")

            # Verify collection_name from class name (lowercased) was used
            call_args = mock_create.call_args
            assert call_args[1]["collection_name"] == "blogposts"

    def test_create_entry_table_defaults_to_collection_name(self, mock_connection):
        """Test that table parameter defaults to collection_name when not provided."""
        mock_collection = MagicMock()
        mock_collection.__class__.__name__ = "Posts"

        postgres_query = PostgresQuery(
            connection=mock_connection,
            query="SELECT * FROM posts",
            collection_name="blog",
        )

        content_manager = PostgresContentManager(
            collection=mock_collection, postgres_query=postgres_query
        )

        with patch.object(PostgresContentManager, "create_entry_static") as mock_create:
            mock_create.return_value = "INSERT query"

            result = content_manager.create_entry(content="# Test")

            # Verify table defaults to collection_name
            call_args = mock_create.call_args
            assert call_args[1]["table"] == "blog"
            assert "INSERT query" in result

    def test_create_entry_table_explicit_parameter(self, mock_connection):
        """Test that explicit table parameter is used when provided."""
        mock_collection = MagicMock()
        mock_collection.__class__.__name__ = "Posts"

        postgres_query = PostgresQuery(
            connection=mock_connection,
            query="SELECT * FROM posts",
            collection_name="blog",
        )

        content_manager = PostgresContentManager(
            collection=mock_collection, postgres_query=postgres_query
        )

        with patch.object(PostgresContentManager, "create_entry_static") as mock_create:
            mock_create.return_value = "INSERT query"

            result = content_manager.create_entry(
                content="# Test", table="custom_posts"
            )

            # Verify explicit table parameter was used
            call_args = mock_create.call_args
            assert call_args[1]["table"] == "custom_posts"
            assert "INSERT query" in result

    def test_create_entry_metadata_handling(self, mock_connection):
        """Test that metadata is properly passed through to parser."""
        mock_collection = MagicMock()
        mock_collection.__class__.__name__ = "Posts"

        postgres_query = PostgresQuery(
            connection=mock_connection, query="SELECT * FROM posts"
        )

        content_manager = PostgresContentManager(
            collection=mock_collection, postgres_query=postgres_query
        )

        with patch.object(PostgresContentManager, "create_entry_static") as mock_create:
            mock_create.return_value = "INSERT query"

            content_manager.create_entry(
                content="# Test",
                metadata={"author": "Jane", "tags": ["python", "database"]},
                table="posts",
            )

            # Verify metadata was unpacked and passed to parser
            call_args = mock_create.call_args
            assert call_args[1]["author"] == "Jane"
            assert call_args[1]["tags"] == ["python", "database"]

    def test_create_entry_empty_content(self, mock_connection):
        """Test that empty content is handled (defaults to empty string)."""
        mock_collection = MagicMock()
        mock_collection.__class__.__name__ = "Posts"

        postgres_query = PostgresQuery(
            connection=mock_connection, query="SELECT * FROM posts"
        )

        content_manager = PostgresContentManager(
            collection=mock_collection, postgres_query=postgres_query
        )

        with patch.object(PostgresContentManager, "create_entry_static") as mock_create:
            mock_create.return_value = "INSERT query"

            content_manager.create_entry(table="posts")

            # Verify empty string was passed for content
            call_args = mock_create.call_args
            assert call_args[1]["content"] == ""

    def test_create_entry_kwargs_passed_through(self, mock_connection):
        """Test that additional kwargs are passed through to parser."""
        mock_collection = MagicMock()
        mock_collection.__class__.__name__ = "Posts"

        postgres_query = PostgresQuery(
            connection=mock_connection, query="SELECT * FROM posts"
        )

        content_manager = PostgresContentManager(
            collection=mock_collection, postgres_query=postgres_query
        )

        with patch.object(PostgresContentManager, "create_entry_static") as mock_create:
            mock_create.return_value = "INSERT query"

            content_manager.create_entry(
                content="# Test", table="posts", custom_param="value", another_param=42
            )

            # Verify kwargs were passed through
            call_args = mock_create.call_args
            assert call_args[1]["custom_param"] == "value"
            assert call_args[1]["another_param"] == 42

    def test_create_entry_return_value_format(self, mock_connection):
        """Test the return value message format."""
        mock_collection = MagicMock()
        mock_collection.__class__.__name__ = "Posts"

        postgres_query = PostgresQuery(
            connection=mock_connection, query="SELECT * FROM posts"
        )

        content_manager = PostgresContentManager(
            collection=mock_collection, postgres_query=postgres_query
        )

        with patch.object(PostgresContentManager, "create_entry_static") as mock_create:
            mock_create.return_value = "INSERT INTO posts (title) VALUES ('Test')"

            result = content_manager.create_entry(content="# Test", table="blog_posts")

            # Verify return message format
            assert result.startswith("INSERT INTO posts")

    def test_create_entry_none_metadata_handled(self, mock_connection):
        """Test that None metadata is properly handled (converted to empty dict)."""
        mock_collection = MagicMock()
        mock_collection.__class__.__name__ = "Posts"

        postgres_query = PostgresQuery(
            connection=mock_connection, query="SELECT * FROM posts"
        )

        content_manager = PostgresContentManager(
            collection=mock_collection, postgres_query=postgres_query
        )

        with patch.object(PostgresContentManager, "create_entry_static") as mock_create:
            mock_create.return_value = "INSERT query"

            # Call with metadata=None (default)
            content_manager.create_entry(content="# Test", table="posts")

            # Should not raise an error, metadata should be empty dict
            mock_create.assert_called_once()


class TestPostgresContentManagerExecution:
    def test_execute_query_sets_collection_parser(self):
        """Test that execute_query sets the parser from the collection on yielded pages."""
        # Setup mocks
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        # Create a mock row (PGPage instance)
        mock_page = MagicMock(spec=PGPage)
        mock_cursor.__iter__.return_value = [mock_page]

        postgres_query = PostgresQuery(
            connection=mock_connection, query="SELECT * FROM posts"
        )

        # Create a specific MockParser to verify
        class CustomMockParser:
            pass

        mock_collection = MagicMock()
        # Set the parser on the collection (simulate render_engine collection)
        mock_collection.Parser = CustomMockParser
        mock_collection.parser = CustomMockParser  # Set both to be safe/realistic

        content_manager = PostgresContentManager(
            collection=mock_collection, postgres_query=postgres_query
        )

        # Execute
        pages = list(content_manager.execute_query())

        # Verify
        assert len(pages) == 1
        page = pages[0]
        assert page.Parser == CustomMockParser
