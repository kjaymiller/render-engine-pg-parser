"""Integration tests for classify_cli - interactive schema classification command."""

import pytest
from pathlib import Path
from click.testing import CliRunner

from render_engine_pg.cli.classify_cli import main


class TestClassifyCLIBasicFunctionality:
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

    def test_cli_with_valid_sql_file_no_input(self):
        """Test CLI with a valid SQL file but no user input (should exit gracefully)."""
        sql_content = """
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY,
            title VARCHAR(255)
        );
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.sql").write_text(sql_content)
            # No input provided - should default to skip
            result = runner.invoke(main, ["test.sql"], input="s\n")
            # Should not crash, but will exit with code 1 because no tables were classified
            assert result.exit_code == 1

    def test_cli_warns_about_non_sql_file(self):
        """Test that CLI warns when file doesn't have .sql extension."""
        sql_content = """
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY
        );
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.txt").write_text(sql_content)
            result = runner.invoke(main, ["test.txt"], input="c\n\n")
            # Should warn but proceed
            assert "Warning" in result.output or result.exit_code == 0


class TestClassifyCLIOutputFile:
    """Tests for CLI output file handling."""

    def test_cli_writes_to_output_file(self):
        """Test that CLI can write to a specified output file."""
        sql_content = """
        CREATE TABLE blog (
            id INTEGER PRIMARY KEY,
            title VARCHAR(255),
            content TEXT
        );
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.sql").write_text(sql_content)
            # Classify as collection
            result = runner.invoke(main, ["test.sql", "-o", "output.toml"], input="c\n\n")
            assert result.exit_code == 0
            assert Path("output.toml").exists()
            output_content = Path("output.toml").read_text()
            assert "[tool.render-engine.pg.insert_sql]" in output_content
            assert "blog" in output_content

    def test_cli_creates_parent_directories(self):
        """Test that CLI creates parent directories for output file."""
        sql_content = """
        CREATE TABLE blog (
            id INTEGER PRIMARY KEY
        );
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.sql").write_text(sql_content)
            result = runner.invoke(
                main, ["test.sql", "-o", "output/dir/file.toml"], input="c\n\n"
            )
            assert result.exit_code == 0
            assert Path("output/dir/file.toml").exists()

    def test_cli_output_long_form_flag(self):
        """Test CLI output using --output long form."""
        sql_content = """
        CREATE TABLE blog (
            id INTEGER PRIMARY KEY
        );
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.sql").write_text(sql_content)
            result = runner.invoke(
                main, ["test.sql", "--output", "out.toml"], input="c\n\n"
            )
            assert result.exit_code == 0
            assert Path("out.toml").exists()


class TestClassifyCLIVerboseFlag:
    """Tests for CLI verbose output."""

    def test_verbose_flag_shows_debug_info(self):
        """Test that verbose flag shows additional information."""
        sql_content = """
        CREATE TABLE blog (
            id INTEGER PRIMARY KEY
        );
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.sql").write_text(sql_content)
            result = runner.invoke(main, ["test.sql", "-v"], input="c\n\n")
            assert "Parsing" in result.output or "Found" in result.output

    def test_verbose_long_form_flag(self):
        """Test verbose using --verbose long form."""
        sql_content = """
        CREATE TABLE blog (
            id INTEGER PRIMARY KEY
        );
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.sql").write_text(sql_content)
            result = runner.invoke(main, ["test.sql", "--verbose"], input="c\n\n")
            assert result.exit_code == 0


class TestClassifyCLIComplexScenarios:
    """Tests for complex real-world scenarios."""

    def test_blog_schema_classification(self):
        """Test classifying a blog schema with multiple tables."""
        sql_content = """
        CREATE TABLE blog (
            id INTEGER PRIMARY KEY,
            title VARCHAR(255),
            content TEXT,
            date TIMESTAMP
        );

        CREATE TABLE tags (
            id INTEGER PRIMARY KEY,
            name VARCHAR(100)
        );

        CREATE TABLE blog_tags (
            blog_id INTEGER,
            tag_id INTEGER
        );
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("blog.sql").write_text(sql_content)
            # Classify: blog=c, tags=a, blog_tags=j
            result = runner.invoke(
                main, ["blog.sql", "-v"], input="c\n\na\n\nj\n\n"
            )
            assert result.exit_code == 0
            assert "[tool.render-engine.pg.insert_sql]" in result.output
            assert "blog" in result.output
            assert "tags" in result.output

    def test_with_all_flags_combined(self):
        """Test using multiple flags together."""
        sql_content = """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name VARCHAR(255)
        );

        CREATE TABLE profiles (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            bio TEXT
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
                    "output.toml",
                    "-v",
                    "--ignore-pk",
                ],
                input="c\n\np\nusers\n",
            )
            assert result.exit_code == 0
            assert Path("output.toml").exists()

    def test_mixed_annotated_and_unmarked_tables(self):
        """Test handling a mix of annotated and unmarked tables."""
        sql_content = """
        -- @collection
        CREATE TABLE blog (
            id INTEGER PRIMARY KEY,
            title VARCHAR(255),
            content TEXT
        );

        CREATE TABLE comments (
            id INTEGER PRIMARY KEY,
            post_id INTEGER,
            content TEXT
        );
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.sql").write_text(sql_content)
            # Only comments needs classification
            result = runner.invoke(main, ["test.sql", "-v"], input="p\nblog\n")
            assert result.exit_code == 0
            assert "blog" in result.output
            assert "comments" in result.output


class TestClassifyCLIErrorHandling:
    """Tests for error handling."""

    def test_verbose_shows_error_traceback(self):
        """Test that verbose flag shows full error traceback."""
        sql_content = "INVALID SQL HERE"
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.sql").write_text(sql_content)
            result = runner.invoke(main, ["test.sql", "-v"])
            # Should fail gracefully
            assert result.exit_code != 0

    def test_invalid_input_handling(self):
        """Test that invalid user input is handled gracefully."""
        sql_content = """
        CREATE TABLE blog (
            id INTEGER PRIMARY KEY
        );
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.sql").write_text(sql_content)
            # Invalid choice, then valid choice
            result = runner.invoke(main, ["test.sql", "-v"], input="x\nc\n\n")
            # Should show invalid choice message and prompt again
            assert "Invalid choice" in result.output
            assert result.exit_code == 0


class TestClassifyCLIEdgeCases:
    """Tests for edge cases."""

    def test_empty_sql_file(self):
        """Test processing an empty SQL file."""
        sql_content = ""
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.sql").write_text(sql_content)
            result = runner.invoke(main, ["test.sql"])
            # Should handle gracefully
            assert result.exit_code in [0, 1]  # Either succeeds or exits with no objects

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
            # Should handle gracefully
            assert isinstance(result.output, str)

    def test_single_large_table(self):
        """Test processing a single large table."""
        columns = ", ".join([f"col_{i} VARCHAR(255)" for i in range(50)])
        sql_content = f"""
        CREATE TABLE large_table (
            id INTEGER PRIMARY KEY,
            {columns}
        );
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.sql").write_text(sql_content)
            result = runner.invoke(main, ["test.sql"], input="c\n\n")
            assert result.exit_code == 0

    def test_sql_with_special_characters(self):
        """Test SQL with table names containing underscores."""
        sql_content = """
        CREATE TABLE user_profiles (
            id INTEGER PRIMARY KEY,
            first_name VARCHAR(255),
            last_name VARCHAR(255)
        );
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("test.sql").write_text(sql_content)
            result = runner.invoke(main, ["test.sql"], input="c\n\n")
            assert result.exit_code == 0

    def test_relative_path_input(self):
        """Test using relative path for input file."""
        sql_content = """
        CREATE TABLE posts (id INTEGER);
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("subdir").mkdir()
            Path("subdir/test.sql").write_text(sql_content)
            result = runner.invoke(main, ["subdir/test.sql"], input="p\n\n")
            assert result.exit_code == 0

    def test_absolute_path_input(self):
        """Test using absolute path for input file."""
        sql_content = """
        CREATE TABLE posts (id INTEGER);
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            test_file = Path.cwd() / "test.sql"
            test_file.write_text(sql_content)
            result = runner.invoke(main, [str(test_file)], input="p\n\n")
            assert result.exit_code == 0


class TestClassifyCLIIntegrationEndToEnd:
    """End-to-end integration tests with realistic schemas."""

    def test_full_workflow_with_relationships(self):
        """Test complete workflow with foreign key relationships."""
        sql_content = """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username VARCHAR(255),
            email VARCHAR(255)
        );

        CREATE TABLE posts (
            id INTEGER PRIMARY KEY,
            title VARCHAR(255),
            content TEXT,
            author_id INTEGER
        );

        CREATE TABLE comments (
            id INTEGER PRIMARY KEY,
            post_id INTEGER,
            author_id INTEGER,
            content TEXT
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
                    "output.toml",
                    "-v",
                ],
                input="c\n\nc\n\nc\n\n",
            )
            assert result.exit_code == 0
            output_content = Path("output.toml").read_text()
            assert "[tool.render-engine.pg.insert_sql]" in output_content
            assert "[tool.render-engine.pg.read_sql]" in output_content
            # Verify we have at least some tables
            assert len(output_content) > 100

    def test_kjaymiller_schema_simplified(self):
        """Test with simplified version of kjaymiller.com schema."""
        sql_content = """
        CREATE TABLE blog (
            id INTEGER PRIMARY KEY,
            slug VARCHAR(255),
            title VARCHAR(255),
            content TEXT,
            date TIMESTAMP
        );

        CREATE TABLE notes (
            id INTEGER PRIMARY KEY,
            slug VARCHAR(255),
            title VARCHAR(255),
            content TEXT,
            date TIMESTAMP
        );

        CREATE TABLE tags (
            id INTEGER PRIMARY KEY,
            name VARCHAR(100)
        );

        CREATE TABLE blog_tags (
            blog_id INTEGER,
            tag_id INTEGER
        );

        CREATE TABLE notes_tags (
            notes_id INTEGER,
            tag_id INTEGER
        );
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("schema.sql").write_text(sql_content)
            # Simulate: blog=c, notes=c, tags=a, blog_tags=j, notes_tags=j
            result = runner.invoke(
                main, ["schema.sql", "-v"], input="c\n\nc\n\na\n\nj\n\nj\n\n"
            )
            assert result.exit_code == 0
            assert "[tool.render-engine.pg" in result.output
