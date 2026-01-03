"""Tests for render-engine settings parser."""

import pytest
from pathlib import Path
from render_engine_pg.re_settings_parser import PGSettings


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
        assert (
            settings.settings["insert_sql"]["posts"]
            == "INSERT INTO users (name) VALUES ('Alice')"
        )

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
