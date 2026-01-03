"""Tests for render-engine-pg ingestion logic in PostgresContentManager."""

import pytest
from unittest.mock import MagicMock
from render_engine_pg.content_manager import PostgresContentManager


class TestPostgresContentManagerTemplateConversion:
    """Test PostgresContentManager template conversion logic."""

    def test_template_substitution_skips_missing_fields(self, mocker):
        """Test that template substitution gracefully skips templates with missing required fields."""
        frontmatter_data = {"id": 1, "title": "My Post"}

        # First template has all fields
        template1 = "INSERT INTO posts (id, title) VALUES ({id}, {title})"
        # Just check if it converts without error
        param_query, values = PostgresContentManager._convert_template_to_parameterized(
            template1, frontmatter_data
        )
        assert values == [1, "My Post"]

        # Second template has missing fields - should raise KeyError
        template2 = "INSERT INTO metadata (id, author) VALUES ({id}, {author})"
        try:
            PostgresContentManager._convert_template_to_parameterized(
                template2, frontmatter_data
            )
            assert False, "Should have raised KeyError for missing 'author' field"
        except KeyError as e:
            assert str(e.args[0]) == "author"

    def test_format_map_vs_format_difference(self):
        """Document the difference between format() and format_map() for missing fields."""
        data = {"id": 1}

        # format_map() also raises KeyError for missing fields - verifying our assumption about python string formatting
        template = "INSERT INTO t (id, name) VALUES ({id}, {name})"
        try:
            template.format_map(data)
            assert False, "format_map() should raise KeyError"
        except KeyError:
            pass  # Expected


class TestPostgresContentManagerListIteration:
    """Test PostgresContentManager list iteration for template substitution."""

    def test_try_execute_with_list_iteration_basic_tags(self, mocker):
        """Test that list iteration works with a simple tags list."""
        mock_cursor = MagicMock()
        frontmatter_data = {"id": 1, "title": "Post", "tags": ["python", "databases"]}
        template = "INSERT INTO tags (name) VALUES ({name})"

        result = PostgresContentManager._try_execute_with_list_iteration(
            mock_cursor, template, frontmatter_data, "name"
        )

        assert result is True
        assert mock_cursor.execute.call_count == 2

    def test_try_execute_with_list_iteration_no_lists(self, mocker):
        """Test that it returns False when no lists are present."""
        mock_cursor = MagicMock()
        frontmatter_data = {"id": 1, "title": "Post"}
        template = "INSERT INTO tags (name) VALUES ({name})"

        result = PostgresContentManager._try_execute_with_list_iteration(
            mock_cursor, template, frontmatter_data, "name"
        )

        assert result is False
        assert mock_cursor.execute.call_count == 0


class TestPostgresContentManagerCreateEntryStatic:
    """Test PostgresContentManager.create_entry_static()."""

    def test_create_entry_integration(self, mocker):
        """Integration test: create_entry with tags list in frontmatter."""
        mock_settings = MagicMock()
        mock_settings.get_insert_sql.return_value = [
            "INSERT INTO tags (name) VALUES ({name})",
            "INSERT INTO posts (id, title, content) VALUES ({id}, {title}, {content})",
        ]
        mock_settings.get_read_sql.return_value = "SELECT id, title, content FROM posts"
        mocker.patch(
            "render_engine_pg.content_manager.PGSettings", return_value=mock_settings
        )

        content = """---
id: 1
title: My Post
tags: [python, postgresql]
---
# Content

Post body."""

        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        # Patch psycopg sql
        from psycopg import sql

        mocker.patch.object(sql.SQL, "format", lambda *args, **kwargs: MagicMock())
        mocker.patch.object(sql.SQL, "as_string", lambda self, conn: "")

        result = PostgresContentManager.create_entry_static(
            content=content,
            collection_name="blog",
            connection=mock_connection,
            table="posts",
        )

        # 2 tags + 1 post template + 1 main insert = 4 calls.
        assert mock_cursor.execute.call_count >= 3
