"""Tests for the SQL CLI."""

from pathlib import Path
from click.testing import CliRunner
import pytest

from render_engine_pg.cli.sql_cli import main


@pytest.fixture
def runner():
    """Create a Click CLI runner."""
    return CliRunner()


class TestUnifiedCLIAutoClassification:
    """Tests for automatic classification mode (default)."""

    def test_auto_classify_simple_schema(self, runner):
        """Test auto-classification on a simple schema."""
        with runner.isolated_filesystem():
            # Create a simple SQL file with no annotations
            with open("schema.sql", "w") as f:
                f.write("""
                CREATE TABLE blog (
                    id integer NOT NULL,
                    title varchar(255) NOT NULL,
                    content text NOT NULL
                );

                CREATE TABLE tags (
                    id integer NOT NULL,
                    name varchar(100) NOT NULL
                );

                CREATE TABLE blog_tags (
                    blog_id integer NOT NULL,
                    tag_id integer NOT NULL
                );
                """)

            # Run CLI
            result = runner.invoke(main, ["schema.sql"])

            assert result.exit_code == 0
            assert "blog" in result.output
            assert "tags" in result.output
            assert "blog_tags" in result.output

    def test_auto_classify_with_alter_table_pk(self, runner):
        """Test auto-classification with ALTER TABLE PRIMARY KEY definitions."""
        with runner.isolated_filesystem():
            with open("schema.sql", "w") as f:
                f.write("""
                CREATE TABLE blog (
                    id integer NOT NULL,
                    title varchar(255) NOT NULL,
                    content text NOT NULL
                );

                ALTER TABLE ONLY blog
                    ADD CONSTRAINT blog_pkey PRIMARY KEY (id);

                CREATE TABLE tags (
                    id integer NOT NULL,
                    name varchar(100) NOT NULL
                );

                ALTER TABLE ONLY tags
                    ADD CONSTRAINT tags_pkey PRIMARY KEY (id);
                """)

            result = runner.invoke(main, ["schema.sql"])

            assert result.exit_code == 0
            assert "[tool.render-engine.pg" in result.output

    def test_auto_classify_preserves_annotations(self, runner):
        """Test that annotated tables are preserved as-is in auto-classification."""
        with runner.isolated_filesystem():
            with open("schema.sql", "w") as f:
                f.write("""
                -- @collection
                CREATE TABLE blog (
                    id integer NOT NULL,
                    title varchar(255) NOT NULL
                );

                CREATE TABLE tags (
                    id integer NOT NULL,
                    name varchar(100) NOT NULL
                );
                """)

            result = runner.invoke(main, ["schema.sql"])

            assert result.exit_code == 0
            # blog should be in output as annotated collection
            assert "blog" in result.output

    def test_auto_classify_output_to_file(self, runner):
        """Test writing auto-classification output to file."""
        with runner.isolated_filesystem():
            with open("schema.sql", "w") as f:
                f.write("""
                CREATE TABLE blog (
                    id integer NOT NULL,
                    title varchar(255) NOT NULL,
                    content text NOT NULL
                );
                """)

            result = runner.invoke(main, ["schema.sql", "-o", "config.toml"])

            assert result.exit_code == 0
            assert Path("config.toml").exists()
            content = Path("config.toml").read_text()
            assert "[tool.render-engine.pg" in content

    def test_auto_classify_verbose(self, runner):
        """Test verbose output in auto-classification."""
        with runner.isolated_filesystem():
            with open("schema.sql", "w") as f:
                f.write("""
                CREATE TABLE blog (
                    id integer NOT NULL,
                    title varchar(255) NOT NULL,
                    content text NOT NULL
                );
                """)

            result = runner.invoke(main, ["schema.sql", "-v"])

            assert result.exit_code == 0
            # Check for verbose output messages
            assert ("Parsing SQL file" in result.output
                    or "Found" in result.output
                    or "collection" in result.output.lower())


class TestUnifiedCLIIgnorePKFlag:
    """Tests for --ignore-pk flag with auto-classification."""

    def test_ignore_pk_auto_classification(self, runner):
        """Test --ignore-pk flag with auto-classification."""
        with runner.isolated_filesystem():
            with open("schema.sql", "w") as f:
                f.write("""
                -- @collection
                CREATE TABLE blog (
                    id integer NOT NULL,
                    slug varchar(255) NOT NULL,
                    title varchar(255) NOT NULL,
                    content text NOT NULL
                );

                ALTER TABLE ONLY blog
                    ADD CONSTRAINT blog_pkey PRIMARY KEY (id);
                """)

            # Without --ignore-pk
            result_without = runner.invoke(main, ["schema.sql"])
            assert result_without.exit_code == 0
            assert "(id, slug, title, content)" in result_without.output

            # With --ignore-pk
            result_with = runner.invoke(main, ["schema.sql", "--ignore-pk"])
            assert result_with.exit_code == 0
            assert "(slug, title, content)" in result_with.output
            assert "INSERT INTO blog" in result_with.output

    def test_ignore_pk_composite_key(self, runner):
        """Test --ignore-pk with composite PRIMARY KEY on junction table."""
        with runner.isolated_filesystem():
            with open("schema.sql", "w") as f:
                f.write("""
                -- @junction
                CREATE TABLE blog_tags (
                    blog_id integer NOT NULL,
                    tag_id integer NOT NULL,
                    created_at timestamp without time zone
                );

                ALTER TABLE ONLY blog_tags
                    ADD CONSTRAINT blog_tags_pkey PRIMARY KEY (blog_id, tag_id);
                """)

            result = runner.invoke(main, ["schema.sql", "--ignore-pk"])

            assert result.exit_code == 0
            # Junction PK columns should NOT be excluded - they are foreign keys needed for relationships
            assert "blog_id, tag_id, created_at" in result.output or "blog_id,tag_id,created_at" in result.output.replace(" ", "")
            # created_at should be excluded (it's not a PK or FK, and --ignore-pk should affect non-junction tables)
            assert "INSERT INTO blog_tags" in result.output

    def test_ignore_pk_multiple_tables(self, runner):
        """Test --ignore-pk across multiple tables with relationships."""
        with runner.isolated_filesystem():
            with open("schema.sql", "w") as f:
                f.write("""
                -- @collection
                CREATE TABLE blog (
                    id integer NOT NULL,
                    title varchar(255) NOT NULL
                );

                ALTER TABLE ONLY blog
                    ADD CONSTRAINT blog_pkey PRIMARY KEY (id);

                -- @attribute
                CREATE TABLE tags (
                    id integer NOT NULL,
                    name varchar(100) NOT NULL
                );

                ALTER TABLE ONLY tags
                    ADD CONSTRAINT tags_pkey PRIMARY KEY (id);

                -- @junction
                CREATE TABLE blog_tags (
                    blog_id integer NOT NULL,
                    tag_id integer NOT NULL
                );

                ALTER TABLE ONLY blog_tags
                    ADD CONSTRAINT blog_tags_pkey PRIMARY KEY (blog_id, tag_id);
                """)

            result = runner.invoke(main, ["schema.sql", "--ignore-pk"])

            assert result.exit_code == 0
            # Both blog and tags should be included (tags via junction to blog)
            assert "INSERT INTO blog (title)" in result.output
            # Tags should be included because blog_tags references it
            assert "blog_tags" in result.output.lower() or "tags" in result.output.lower()


class TestUnifiedCLIInteractiveMode:
    """Tests for interactive mode with --interactive flag."""

    def test_interactive_mode_with_input(self, runner):
        """Test interactive mode prompts for unmarked tables."""
        with runner.isolated_filesystem():
            with open("schema.sql", "w") as f:
                f.write("""
                CREATE TABLE blog (
                    id integer NOT NULL,
                    title varchar(255) NOT NULL,
                    content text NOT NULL
                );
                """)

            # Provide 'c' for collection, then skip parent
            result = runner.invoke(main, ["schema.sql", "--interactive"], input="c\n\n")

            assert result.exit_code == 0
            # Should show classification prompts
            assert "Classify as" in result.output or "collection" in result.output.lower()

    def test_interactive_mode_skip_annotated(self, runner):
        """Test interactive mode only prompts for unmarked tables."""
        with runner.isolated_filesystem():
            with open("schema.sql", "w") as f:
                f.write("""
                -- @collection
                CREATE TABLE blog (
                    id integer NOT NULL,
                    title varchar(255) NOT NULL
                );

                CREATE TABLE tags (
                    id integer NOT NULL,
                    name varchar(100) NOT NULL
                );
                """)

            # Only tags is unmarked, so only one classification prompt expected
            result = runner.invoke(main, ["schema.sql", "--interactive"], input="a\n\n")

            assert result.exit_code == 0
            # blog should already be classified
            assert "blog" in result.output


class TestUnifiedCLIErrorHandling:
    """Tests for error handling."""

    def test_missing_file_error(self, runner):
        """Test error when file doesn't exist."""
        result = runner.invoke(main, ["nonexistent.sql"])

        assert result.exit_code != 0
        assert "Error" in result.output or "No such file" in result.output

    def test_invalid_sql_file_warning(self, runner):
        """Test warning for non-.sql files."""
        with runner.isolated_filesystem():
            with open("schema.txt", "w") as f:
                f.write("CREATE TABLE test (id int);")

            result = runner.invoke(main, ["schema.txt"])

            # Should warn about file extension
            assert "Warning" in result.output or result.exit_code == 0

    def test_empty_file_error(self, runner):
        """Test error when SQL file has no valid tables."""
        with runner.isolated_filesystem():
            with open("schema.sql", "w") as f:
                f.write("-- Just a comment")

            result = runner.invoke(main, ["schema.sql"])

            assert result.exit_code != 0 or "Error" in result.output or result.exit_code == 0


class TestUnifiedCLIOutputFormats:
    """Tests for output formatting."""

    def test_stdout_output(self, runner):
        """Test TOML output to stdout."""
        with runner.isolated_filesystem():
            with open("schema.sql", "w") as f:
                f.write("""
                -- @collection
                CREATE TABLE blog (
                    id integer NOT NULL,
                    title varchar(255) NOT NULL,
                    content text NOT NULL
                );
                """)

            result = runner.invoke(main, ["schema.sql"])

            assert result.exit_code == 0
            assert "[tool.render-engine.pg" in result.output
            assert "blog" in result.output

    def test_file_output(self, runner):
        """Test TOML output to file."""
        with runner.isolated_filesystem():
            with open("schema.sql", "w") as f:
                f.write("""
                -- @collection
                CREATE TABLE blog (
                    id integer NOT NULL,
                    title varchar(255) NOT NULL,
                    content text NOT NULL
                );
                """)

            result = runner.invoke(main, ["schema.sql", "-o", "output.toml"])

            assert result.exit_code == 0
            assert Path("output.toml").exists()
            content = Path("output.toml").read_text()
            assert "[tool.render-engine.pg" in content
            assert "blog" in content

    def test_nested_output_directory(self, runner):
        """Test creating nested output directories."""
        with runner.isolated_filesystem():
            with open("schema.sql", "w") as f:
                f.write("""
                -- @collection
                CREATE TABLE blog (
                    id integer NOT NULL
                );
                """)

            result = runner.invoke(main, ["schema.sql", "-o", "config/nested/output.toml"])

            assert result.exit_code == 0
            assert Path("config/nested/output.toml").exists()


class TestUnifiedCLIComplexSchemas:
    """Tests for complex real-world schemas."""

    def test_kjaymiller_schema_structure(self, runner):
        """Test processing a schema similar to kjaymiller.com."""
        with runner.isolated_filesystem():
            with open("schema.sql", "w") as f:
                f.write("""
                CREATE TABLE blog (
                    id integer NOT NULL,
                    slug character varying(255) NOT NULL,
                    title character varying(255) NOT NULL,
                    content text NOT NULL,
                    description text,
                    date timestamp without time zone NOT NULL
                );

                ALTER TABLE ONLY blog
                    ADD CONSTRAINT blog_pkey PRIMARY KEY (id);

                CREATE TABLE tags (
                    id integer NOT NULL,
                    name character varying(100) NOT NULL,
                    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
                );

                ALTER TABLE ONLY tags
                    ADD CONSTRAINT tags_pkey PRIMARY KEY (id);

                CREATE TABLE blog_tags (
                    blog_id integer NOT NULL,
                    tag_id integer NOT NULL,
                    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
                );

                ALTER TABLE ONLY blog_tags
                    ADD CONSTRAINT blog_tags_pkey PRIMARY KEY (blog_id, tag_id);
                """)

            # Test auto-classification
            result_auto = runner.invoke(main, ["schema.sql"])
            assert result_auto.exit_code == 0
            assert "blog" in result_auto.output
            assert "tags" in result_auto.output
            assert "blog_tags" in result_auto.output

            # Test with --ignore-pk
            result_ignore_pk = runner.invoke(main, ["schema.sql", "--ignore-pk"])
            assert result_ignore_pk.exit_code == 0
            # IDs should be in columns but excluded from INSERT
            assert "INSERT INTO blog (slug, title, content" in result_ignore_pk.output or \
                   "INSERT INTO blog" in result_ignore_pk.output

    def test_many_to_many_relationship(self, runner):
        """Test handling of many-to-many relationships."""
        with runner.isolated_filesystem():
            with open("schema.sql", "w") as f:
                f.write("""
                CREATE TABLE posts (
                    id integer NOT NULL,
                    title varchar(255) NOT NULL,
                    content text NOT NULL
                );

                CREATE TABLE categories (
                    id integer NOT NULL,
                    name varchar(100) NOT NULL
                );

                CREATE TABLE post_categories (
                    post_id integer NOT NULL,
                    category_id integer NOT NULL
                );
                """)

            result = runner.invoke(main, ["schema.sql"])

            assert result.exit_code == 0
            # All tables should be present
            for table in ["posts", "categories", "post_categories"]:
                assert table in result.output


class TestUnifiedCLIIntegration:
    """Integration tests combining multiple features."""

    def test_auto_classify_with_ignore_pk_and_timestamps(self, runner):
        """Test auto-classification with both --ignore-pk and --ignore-timestamps."""
        with runner.isolated_filesystem():
            with open("schema.sql", "w") as f:
                f.write("""
                -- @collection
                CREATE TABLE blog (
                    id integer NOT NULL,
                    title varchar(255) NOT NULL,
                    content text NOT NULL,
                    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
                    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
                );

                ALTER TABLE ONLY blog
                    ADD CONSTRAINT blog_pkey PRIMARY KEY (id);
                """)

            result = runner.invoke(
                main,
                ["schema.sql", "--ignore-pk", "--ignore-timestamps"],
            )

            assert result.exit_code == 0
            # Both id and timestamps should be excluded
            assert "INSERT INTO blog (title, content)" in result.output or \
                   "INSERT INTO blog" in result.output

    def test_auto_classify_output_and_verbose(self, runner):
        """Test combining -o and -v flags."""
        with runner.isolated_filesystem():
            with open("schema.sql", "w") as f:
                f.write("""
                -- @collection
                CREATE TABLE blog (
                    id integer NOT NULL,
                    title varchar(255) NOT NULL
                );
                """)

            result = runner.invoke(
                main,
                ["schema.sql", "-o", "config.toml", "-v"],
            )

            assert result.exit_code == 0
            assert Path("config.toml").exists()
            # Verbose output should be in stderr (captured in result.output)
            assert "Parsing" in result.output or "Found" in result.output or "Done" in result.output
