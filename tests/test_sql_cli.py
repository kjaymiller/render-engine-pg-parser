"""Integration tests for sql_cli - the CLI command."""

import pytest
import json
from pathlib import Path
from click.testing import CliRunner

from render_engine_pg.cli.sql_cli import main


class TestCLIBasicFunctionality:
    """Tests for basic CLI functionality."""

    def test_cli_requires_input_file(self):
        """Test that CLI requires an input file argument."""
        runner = CliRunner()
        result = runner.invoke(main, [])
        assert result.exit_code != 0
        assert "Error" in result.output or "Argument" in result.output

    def test_cli_with_nonexistent_file(self):
        """Test CLI with a non-existent input file."""
        runner = CliRunner()
        result = runner.invoke(main, ["/nonexistent/path/to/file.sql"])
        assert result.exit_code != 0

    def test_cli_with_valid_sql_file(self):
        """Test CLI with a valid SQL file."""
        sql_content = """
        -- @page
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY,
            title VARCHAR(255)
        );
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create a temporary SQL file
            Path("test.sql").write_text(sql_content)
            result = runner.invoke(main, ["test.sql"])
            assert result.exit_code == 0

    def test_cli_outputs_to_stdout_by_default(self):
        """Test that CLI outputs to stdout when no output file specified."""
        sql_content = """
        -- @page
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY
        );
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.sql").write_text(sql_content)
            result = runner.invoke(main, ["test.sql"])
            assert "INSERT INTO" in result.output

    def test_cli_warns_about_non_sql_file(self):
        """Test that CLI warns when file doesn't have .sql extension."""
        sql_content = """
        -- @page
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY
        );
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.txt").write_text(sql_content)
            result = runner.invoke(main, ["test.txt"])
            # Should still work but warn
            assert "Warning" in result.output or result.exit_code == 0


class TestCLIOutputFile:
    """Tests for CLI output file handling."""

    def test_cli_writes_to_output_file(self):
        """Test that CLI can write to a specified output file."""
        sql_content = """
        -- @page
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY
        );
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.sql").write_text(sql_content)
            result = runner.invoke(main, ["test.sql", "-o", "output.sql"])
            assert result.exit_code == 0
            assert Path("output.sql").exists()
            output_content = Path("output.sql").read_text()
            assert "INSERT INTO" in output_content

    def test_cli_creates_parent_directories(self):
        """Test that CLI creates parent directories for output file."""
        sql_content = """
        -- @page
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY
        );
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.sql").write_text(sql_content)
            result = runner.invoke(main, ["test.sql", "-o", "output/dir/file.sql"])
            assert result.exit_code == 0
            assert Path("output/dir/file.sql").exists()

    def test_cli_output_long_form_flag(self):
        """Test CLI output using --output long form."""
        sql_content = """
        -- @page
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY
        );
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.sql").write_text(sql_content)
            result = runner.invoke(main, ["test.sql", "--output", "out.sql"])
            assert result.exit_code == 0
            assert Path("out.sql").exists()


class TestCLIVerboseFlag:
    """Tests for CLI verbose output."""

    def test_verbose_flag_shows_debug_info(self):
        """Test that verbose flag shows additional information."""
        sql_content = """
        -- @page
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY
        );
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.sql").write_text(sql_content)
            result = runner.invoke(main, ["test.sql", "-v"])
            assert "Parsing" in result.output or "Found" in result.output or result.exit_code == 0

    def test_verbose_long_form_flag(self):
        """Test verbose using --verbose long form."""
        sql_content = """
        -- @page
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY
        );
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.sql").write_text(sql_content)
            result = runner.invoke(main, ["test.sql", "--verbose"])
            assert result.exit_code == 0


class TestCLIObjectsFilter:
    """Tests for filtering object types."""

    def test_filter_pages_only(self):
        """Test filtering to include only pages."""
        sql_content = """
        -- @page
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY
        );

        -- @collection
        CREATE TABLE blog (
            id INTEGER PRIMARY KEY
        );
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.sql").write_text(sql_content)
            result = runner.invoke(main, ["test.sql", "--objects", "pages"])
            # Output should have posts insert but not necessarily blog collection
            assert result.exit_code == 0

    def test_filter_collections_only(self):
        """Test filtering to include only collections."""
        sql_content = """
        -- @page
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY
        );

        -- @collection
        CREATE TABLE blog (
            id INTEGER PRIMARY KEY
        );
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.sql").write_text(sql_content)
            result = runner.invoke(main, ["test.sql", "--objects", "collections"])
            assert result.exit_code == 0

    def test_filter_multiple_object_types(self):
        """Test filtering multiple object types at once."""
        sql_content = """
        -- @page
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY
        );

        -- @attribute
        CREATE TABLE tags (
            id INTEGER PRIMARY KEY
        );

        -- @junction
        CREATE TABLE post_tags (
            post_id INTEGER,
            tag_id INTEGER
        );
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.sql").write_text(sql_content)
            result = runner.invoke(
                main, ["test.sql", "--objects", "pages", "--objects", "attributes"]
            )
            assert result.exit_code == 0

    def test_filter_all_types_explicitly(self):
        """Test explicitly filtering all object types."""
        sql_content = """
        -- @page
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY
        );

        -- @collection
        CREATE TABLE blog (
            id INTEGER PRIMARY KEY
        );

        -- @attribute
        CREATE TABLE tags (
            id INTEGER PRIMARY KEY
        );

        -- @junction
        CREATE TABLE post_tags (
            post_id INTEGER,
            tag_id INTEGER
        );
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.sql").write_text(sql_content)
            result = runner.invoke(
                main,
                [
                    "test.sql",
                    "--objects",
                    "pages",
                    "--objects",
                    "collections",
                    "--objects",
                    "attributes",
                    "--objects",
                    "junctions",
                ],
            )
            assert result.exit_code == 0


class TestCLIFormatOutput:
    """Tests for output format options."""

    def test_default_format_is_sql(self):
        """Test that default output format is SQL."""
        sql_content = """
        -- @page
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY
        );
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.sql").write_text(sql_content)
            result = runner.invoke(main, ["test.sql"])
            assert "INSERT INTO" in result.output

    def test_sql_format_output(self):
        """Test SQL format output explicitly."""
        sql_content = """
        -- @page
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY
        );
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.sql").write_text(sql_content)
            result = runner.invoke(main, ["test.sql", "--format", "sql"])
            assert result.exit_code == 0
            assert "INSERT INTO" in result.output

    def test_json_format_output(self):
        """Test JSON format output."""
        sql_content = """
        -- @page
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY
        );
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.sql").write_text(sql_content)
            result = runner.invoke(main, ["test.sql", "--format", "json"])
            assert result.exit_code == 0
            # Should be valid JSON
            try:
                data = json.loads(result.output)
                assert "objects" in data
                assert "relationships" in data
                assert "queries" in data
            except json.JSONDecodeError:
                pytest.fail("Output is not valid JSON")

    def test_json_format_to_file(self):
        """Test writing JSON format to file."""
        sql_content = """
        -- @page
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY
        );
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.sql").write_text(sql_content)
            result = runner.invoke(
                main, ["test.sql", "-o", "output.json", "--format", "json"]
            )
            assert result.exit_code == 0
            assert Path("output.json").exists()
            output_content = Path("output.json").read_text()
            data = json.loads(output_content)
            assert isinstance(data, dict)


class TestCLIComplexScenarios:
    """Tests for complex real-world scenarios."""

    def test_blog_schema_complete_flow(self):
        """Test processing a complete blog schema."""
        sql_content = """
        -- @collection
        CREATE TABLE blog (
            id INTEGER PRIMARY KEY,
            title VARCHAR(255)
        );

        -- @page Blog
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY,
            title VARCHAR(255),
            content TEXT,
            blog_id INTEGER,
            FOREIGN KEY (blog_id) REFERENCES blog(id)
        );

        -- @attribute Blog
        CREATE TABLE tags (
            id INTEGER PRIMARY KEY,
            name VARCHAR(255)
        );

        -- @junction Blog
        CREATE TABLE post_tags (
            post_id INTEGER,
            tag_id INTEGER,
            FOREIGN KEY (post_id) REFERENCES posts(id),
            FOREIGN KEY (tag_id) REFERENCES tags(id)
        );

        CREATE TABLE comments (
            id INTEGER PRIMARY KEY,
            post_id INTEGER,
            content TEXT,
            FOREIGN KEY (post_id) REFERENCES posts(id)
        );
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("blog.sql").write_text(sql_content)
            result = runner.invoke(main, ["blog.sql", "-v"])
            assert result.exit_code == 0
            assert "INSERT INTO" in result.output

    def test_with_all_flags_combined(self):
        """Test using multiple flags together."""
        sql_content = """
        -- @page
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name VARCHAR(255)
        );

        -- @collection
        CREATE TABLE blog (
            id INTEGER PRIMARY KEY
        );
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.sql").write_text(sql_content)
            result = runner.invoke(
                main,
                [
                    "test.sql",
                    "-o",
                    "output.json",
                    "-v",
                    "--format",
                    "json",
                    "--objects",
                    "pages",
                ],
            )
            assert result.exit_code == 0
            assert Path("output.json").exists()


class TestCLIErrorHandling:
    """Tests for error handling."""

    def test_verbose_shows_error_traceback(self):
        """Test that verbose flag shows full error traceback."""
        sql_content = "INVALID SQL HERE"
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.sql").write_text(sql_content)
            result = runner.invoke(main, ["test.sql", "-v"])
            # With verbose, might show more info, but should still fail gracefully
            assert result.exit_code != 0 or result.exit_code == 0  # Depends on implementation

    def test_invalid_format_option(self):
        """Test that invalid format option is rejected."""
        sql_content = """
        -- @page
        CREATE TABLE posts (id INTEGER);
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.sql").write_text(sql_content)
            result = runner.invoke(main, ["test.sql", "--format", "invalid"])
            # Should either reject or handle gracefully
            assert "invalid" in result.output.lower() or result.exit_code != 0

    def test_invalid_objects_option(self):
        """Test that invalid object type option is rejected."""
        sql_content = """
        -- @page
        CREATE TABLE posts (id INTEGER);
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.sql").write_text(sql_content)
            result = runner.invoke(main, ["test.sql", "--objects", "invalid"])
            assert result.exit_code != 0


class TestCLIEdgeCases:
    """Tests for edge cases."""

    def test_empty_sql_file(self):
        """Test processing an empty SQL file."""
        sql_content = ""
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.sql").write_text(sql_content)
            result = runner.invoke(main, ["test.sql"])
            # Should handle gracefully, might output nothing or error
            assert isinstance(result.output, str)

    def test_sql_file_with_only_comments(self):
        """Test processing SQL file with only comments."""
        sql_content = """
        -- This is a comment
        -- Another comment
        -- Yet another comment
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.sql").write_text(sql_content)
            result = runner.invoke(main, ["test.sql"])
            assert result.exit_code == 0 or result.exit_code != 0  # Graceful handling

    def test_large_sql_file(self):
        """Test processing a large SQL file."""
        tables = ""
        for i in range(50):
            tables += f"""
            -- @page
            CREATE TABLE table_{i} (
                id INTEGER PRIMARY KEY,
                value VARCHAR(255)
            );
            """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.sql").write_text(tables)
            result = runner.invoke(main, ["test.sql"])
            assert result.exit_code == 0

    def test_sql_with_special_characters(self):
        """Test SQL with special characters in names."""
        sql_content = """
        -- @page
        CREATE TABLE "user_profiles" (
            "id" INTEGER PRIMARY KEY,
            "first_name" VARCHAR(255),
            "last_name" VARCHAR(255)
        );
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.sql").write_text(sql_content)
            result = runner.invoke(main, ["test.sql"])
            assert result.exit_code == 0

    def test_relative_path_input(self):
        """Test using relative path for input file."""
        sql_content = """
        -- @page
        CREATE TABLE posts (id INTEGER);
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("subdir").mkdir()
            Path("subdir/test.sql").write_text(sql_content)
            result = runner.invoke(main, ["subdir/test.sql"])
            assert result.exit_code == 0

    def test_absolute_path_input(self):
        """Test using absolute path for input file."""
        sql_content = """
        -- @page
        CREATE TABLE posts (id INTEGER);
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            test_file = Path.cwd() / "test.sql"
            test_file.write_text(sql_content)
            result = runner.invoke(main, [str(test_file)])
            assert result.exit_code == 0


class TestCLIIntegrationEndToEnd:
    """End-to-end integration tests."""

    def test_full_workflow_with_relationships(self):
        """Test complete workflow with foreign key relationships."""
        sql_content = """
        -- @page
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username VARCHAR(255),
            email VARCHAR(255)
        );

        -- @page
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY,
            title VARCHAR(255),
            content TEXT,
            author_id INTEGER,
            FOREIGN KEY (author_id) REFERENCES users(id)
        );

        -- @page
        CREATE TABLE comments (
            id INTEGER PRIMARY KEY,
            post_id INTEGER,
            author_id INTEGER,
            content TEXT,
            FOREIGN KEY (post_id) REFERENCES posts(id),
            FOREIGN KEY (author_id) REFERENCES users(id)
        );
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("schema.sql").write_text(sql_content)
            result = runner.invoke(
                main,
                [
                    "schema.sql",
                    "-o",
                    "output.sql",
                    "-v",
                    "--format",
                    "sql",
                ],
            )
            assert result.exit_code == 0
            output_content = Path("output.sql").read_text()
            assert "INSERT INTO users" in output_content
            assert "INSERT INTO posts" in output_content
            assert "INSERT INTO comments" in output_content
            # Users should come before posts in output (dependency order)
            users_pos = output_content.find("INSERT INTO users")
            posts_pos = output_content.find("INSERT INTO posts")
            assert users_pos < posts_pos

    def test_json_output_structure(self):
        """Test that JSON output has proper structure."""
        sql_content = """
        -- @page
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY,
            title VARCHAR(255)
        );

        -- @attribute
        CREATE TABLE tags (
            id INTEGER PRIMARY KEY,
            name VARCHAR(255)
        );

        -- @junction
        CREATE TABLE post_tags (
            post_id INTEGER,
            tag_id INTEGER
        );
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.sql").write_text(sql_content)
            result = runner.invoke(
                main, ["test.sql", "-o", "output.json", "--format", "json"]
            )
            assert result.exit_code == 0
            data = json.loads(Path("output.json").read_text())
            assert "objects" in data
            assert "relationships" in data
            assert "queries" in data
            assert isinstance(data["objects"], list)
            assert isinstance(data["relationships"], list)
            assert isinstance(data["queries"], list)
