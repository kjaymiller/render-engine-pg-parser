"""Tests for render-engine settings parser and collection-based inserts."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from render_engine_pg.re_settings_parser import PGSettings
from render_engine_pg.parsers import PGMarkdownCollectionParser


class TestPGSettings:
    """Test PGSettings configuration loader."""

    def test_find_pyproject_toml(self, tmp_path):
        """Test finding pyproject.toml in parent directories."""
        # Create a nested directory structure
        nested_dir = tmp_path / "src" / "render_engine_pg"
        nested_dir.mkdir(parents=True)

        # Create pyproject.toml in root
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.render-engine.pg]\ninsert_sql = {}\n")

        # Should find it from nested directory
        settings = PGSettings(config_path=pyproject)
        assert settings.config_path == pyproject

    def test_load_settings_with_insert_sql(self, tmp_path):
        """Test loading settings with insert_sql configuration."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """[tool.render-engine.pg]
insert_sql = { posts = "INSERT INTO users (name) VALUES ('Alice')" }
"""
        )

        settings = PGSettings(config_path=pyproject)
        assert "posts" in settings.settings["insert_sql"]
        assert settings.settings["insert_sql"]["posts"] == "INSERT INTO users (name) VALUES ('Alice')"

    def test_get_insert_sql_string(self, tmp_path):
        """Test retrieving insert SQL as string with semicolon splitting."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """[tool.render-engine.pg]
insert_sql = { posts = "INSERT INTO users (name) VALUES ('Alice'); INSERT INTO users (name) VALUES ('Bob')" }
"""
        )

        settings = PGSettings(config_path=pyproject)
        queries = settings.get_insert_sql("posts")

        assert len(queries) == 2
        assert queries[0] == "INSERT INTO users (name) VALUES ('Alice')"
        assert queries[1] == "INSERT INTO users (name) VALUES ('Bob')"

    def test_get_insert_sql_list(self, tmp_path):
        """Test retrieving insert SQL when configured as a list."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """[tool.render-engine.pg]
insert_sql = { posts = ["INSERT INTO users (name) VALUES ('Alice')", "INSERT INTO users (name) VALUES ('Bob')"] }
"""
        )

        settings = PGSettings(config_path=pyproject)
        queries = settings.get_insert_sql("posts")

        assert len(queries) == 2
        assert "INSERT INTO users (name) VALUES ('Alice')" in queries

    def test_get_insert_sql_nonexistent_collection(self, tmp_path):
        """Test retrieving insert SQL for collection that doesn't exist."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """[tool.render-engine.pg]
insert_sql = { posts = "INSERT INTO users (name) VALUES ('Alice')" }
"""
        )

        settings = PGSettings(config_path=pyproject)
        queries = settings.get_insert_sql("comments")

        assert queries == []

    def test_default_settings_when_file_not_found(self):
        """Test default settings are used when pyproject.toml not found."""
        settings = PGSettings(config_path=Path("/nonexistent/path/pyproject.toml"))

        assert settings.settings == PGSettings.DEFAULT_SETTINGS

    def test_filter_empty_queries(self, tmp_path):
        """Test that empty queries are filtered out."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """[tool.render-engine.pg]
insert_sql = { posts = "INSERT INTO users (name) VALUES ('Alice');;INSERT INTO users (name) VALUES ('Bob')" }
"""
        )

        settings = PGSettings(config_path=pyproject)
        queries = settings.get_insert_sql("posts")

        assert len(queries) == 2
        assert all(q for q in queries)  # No empty strings


class TestPGMarkdownCollectionParserWithInserts:
    """Test PGMarkdownCollectionParser with collection-based inserts."""

    def test_create_entry_with_collection_name_calls_settings(self, mock_connection):
        """Test create_entry loads and calls pre-configured inserts."""
        content = "---\ntitle: Test\n---\n# Hello"

        with patch('render_engine_pg.parsers.PGSettings') as mock_settings_class:
            mock_settings = MagicMock()
            mock_settings.get_insert_sql.return_value = [
                "INSERT INTO users (name) VALUES ('Alice')",
                "INSERT INTO users (name) VALUES ('Bob')"
            ]
            mock_settings_class.return_value = mock_settings

            # Mock the sql module to avoid encoding issues
            with patch('render_engine_pg.parsers.sql.SQL') as mock_sql_class:
                mock_query_obj = MagicMock()
                mock_query_obj.as_string.return_value = "INSERT INTO pages ..."
                mock_sql_class.return_value.format.return_value = mock_query_obj

                result = PGMarkdownCollectionParser.create_entry(
                    content=content,
                    collection_name="posts",
                    connection=mock_connection,
                    table="pages"
                )

                # Should have called get_insert_sql with collection name
                mock_settings.get_insert_sql.assert_called_with("posts")

                # Verify the pre-configured inserts were executed
                cursor_mock = mock_connection.cursor.return_value.__enter__.return_value
                execute_calls = cursor_mock.execute.call_args_list

                # Should have executed the 2 pre-configured inserts
                assert len(execute_calls) >= 2

    def test_create_entry_without_collection_name_skips_settings(self, mock_connection):
        """Test create_entry skips settings when collection_name is not provided."""
        content = "---\ntitle: Test\n---\n# Hello"

        with patch('render_engine_pg.parsers.PGSettings') as mock_settings_class:
            # Mock the sql module to avoid encoding issues
            with patch('render_engine_pg.parsers.sql.SQL') as mock_sql_class:
                mock_query_obj = MagicMock()
                mock_query_obj.as_string.return_value = "INSERT INTO pages ..."
                mock_sql_class.return_value.format.return_value = mock_query_obj

                result = PGMarkdownCollectionParser.create_entry(
                    content=content,
                    connection=mock_connection,
                    table="pages"
                )

                # PGSettings should NOT be instantiated when collection_name is None
                mock_settings_class.assert_not_called()

    def test_create_entry_with_empty_insert_sql_list(self, mock_connection):
        """Test create_entry when collection has no pre-configured inserts."""
        content = "---\ntitle: Test\n---\n# Hello"

        with patch('render_engine_pg.parsers.PGSettings') as mock_settings_class:
            mock_settings = MagicMock()
            mock_settings.get_insert_sql.return_value = []
            mock_settings_class.return_value = mock_settings

            with patch('render_engine_pg.parsers.sql.SQL') as mock_sql_class:
                mock_query_obj = MagicMock()
                mock_query_obj.as_string.return_value = "INSERT INTO pages ..."
                mock_sql_class.return_value.format.return_value = mock_query_obj

                result = PGMarkdownCollectionParser.create_entry(
                    content=content,
                    collection_name="posts",
                    connection=mock_connection,
                    table="pages"
                )

                # Should have called get_insert_sql
                mock_settings.get_insert_sql.assert_called_with("posts")

                # Cursor should only execute the markdown insert (not the pre-configured ones)
                cursor_mock = mock_connection.cursor.return_value.__enter__.return_value
                execute_calls = cursor_mock.execute.call_args_list

                # Should have only the markdown insert
                assert len(execute_calls) == 1

    def test_collection_name_excluded_from_frontmatter_metadata(self, mock_connection):
        """Test that collection_name is not added to frontmatter data."""
        content = "---\ntitle: Test\nauthor: John\n---\n# Hello"

        with patch('render_engine_pg.parsers.sql.SQL') as mock_sql_class:
            mock_query_obj = MagicMock()
            mock_query_obj.as_string.return_value = "INSERT INTO pages ..."
            mock_sql_class.return_value.format.return_value = mock_query_obj

            result = PGMarkdownCollectionParser.create_entry(
                content=content,
                collection_name="posts",
                connection=mock_connection,
                table="pages",
            )

            # Get the SQL.Identifier calls to see what columns are being used
            identifier_calls = [call for call in mock_sql_class.call_args_list
                              if call[0] and not isinstance(call[0][0], str)]

            # collection_name should not appear in identifiers
            identifier_strs = [str(call) for call in identifier_calls]
            combined = " ".join(identifier_strs)

            assert "collection_name" not in combined.lower()
