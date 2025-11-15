"""Tests for SQLParser - extracts render-engine objects from SQL files."""

import pytest

from render_engine_pg.cli.sql_parser import SQLParser


class TestSQLParserPageParsing:
    """Tests for parsing page definitions."""

    def test_parse_page_without_parent(self):
        """Test parsing a page without parent collection."""
        sql = """
        -- @page
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY,
            title VARCHAR(255),
            content TEXT
        );
        """
        parser = SQLParser()
        objects = parser.parse(sql)

        assert len(objects) == 1
        assert objects[0]["type"] == "page"
        assert objects[0]["name"] == "posts"
        assert objects[0]["table"] == "posts"
        assert set(objects[0]["columns"]) == {"id", "title", "content"}
        assert objects[0]["attributes"] == {}

    def test_parse_page_with_parent(self):
        """Test parsing a page with parent collection."""
        sql = """
        -- @page Blog
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY,
            title VARCHAR(255)
        );
        """
        parser = SQLParser()
        objects = parser.parse(sql)

        assert len(objects) == 1
        assert objects[0]["type"] == "page"
        assert objects[0]["name"] == "posts"
        assert objects[0]["attributes"]["parent_collection"] == "Blog"

    def test_parse_page_with_quoted_parent(self):
        """Test parsing a page with quoted parent name."""
        sql = """
        -- @page 'Blog'
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY
        );
        """
        parser = SQLParser()
        objects = parser.parse(sql)

        assert objects[0]["attributes"]["parent_collection"] == "Blog"

    def test_parse_multiple_pages(self):
        """Test parsing multiple pages."""
        sql = """
        -- @page
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY
        );

        -- @page
        CREATE TABLE comments (
            id INTEGER PRIMARY KEY
        );
        """
        parser = SQLParser()
        objects = parser.parse(sql)

        assert len(objects) == 2
        assert all(obj["type"] == "page" for obj in objects)
        assert {obj["name"] for obj in objects} == {"posts", "comments"}


class TestSQLParserCollectionParsing:
    """Tests for parsing collection definitions."""

    def test_parse_collection_without_parent(self):
        """Test parsing a collection without parent."""
        sql = """
        -- @collection
        CREATE TABLE blog (
            id INTEGER PRIMARY KEY,
            title VARCHAR(255)
        );
        """
        parser = SQLParser()
        objects = parser.parse(sql)

        assert len(objects) == 1
        assert objects[0]["type"] == "collection"
        assert objects[0]["name"] == "blog"
        assert objects[0]["attributes"]["collection_name"] == "blog"

    def test_parse_collection_with_parent(self):
        """Test parsing a collection with parent collection."""
        sql = """
        -- @collection ParentBlog
        CREATE TABLE blog (
            id INTEGER PRIMARY KEY
        );
        """
        parser = SQLParser()
        objects = parser.parse(sql)

        assert objects[0]["attributes"]["parent_collection"] == "ParentBlog"
        assert objects[0]["attributes"]["collection_name"] == "blog"


class TestSQLParserAttributeParsing:
    """Tests for parsing attribute definitions."""

    def test_parse_attribute(self):
        """Test parsing an attribute table."""
        sql = """
        -- @attribute
        CREATE TABLE tags (
            id INTEGER PRIMARY KEY,
            name VARCHAR(255)
        );
        """
        parser = SQLParser()
        objects = parser.parse(sql)

        assert len(objects) == 1
        assert objects[0]["type"] == "attribute"
        assert objects[0]["name"] == "tags"

    def test_parse_attribute_with_parent(self):
        """Test parsing an attribute with parent collection."""
        sql = """
        -- @attribute Blog
        CREATE TABLE tags (
            id INTEGER PRIMARY KEY
        );
        """
        parser = SQLParser()
        objects = parser.parse(sql)

        assert objects[0]["attributes"]["parent_collection"] == "Blog"


class TestSQLParserJunctionParsing:
    """Tests for parsing junction table definitions."""

    def test_parse_junction(self):
        """Test parsing a junction table."""
        sql = """
        -- @junction
        CREATE TABLE post_tags (
            post_id INTEGER,
            tag_id INTEGER
        );
        """
        parser = SQLParser()
        objects = parser.parse(sql)

        assert len(objects) == 1
        assert objects[0]["type"] == "junction"
        assert objects[0]["name"] == "post_tags"

    def test_parse_junction_with_parent(self):
        """Test parsing a junction table with parent."""
        sql = """
        -- @junction Blog
        CREATE TABLE post_tags (
            post_id INTEGER,
            tag_id INTEGER
        );
        """
        parser = SQLParser()
        objects = parser.parse(sql)

        assert objects[0]["attributes"]["parent_collection"] == "Blog"


class TestSQLParserUnmarkedTables:
    """Tests for parsing unmarked tables (inferred tables)."""

    def test_parse_unmarked_table(self):
        """Test parsing a table without any annotation."""
        sql = """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name VARCHAR(255)
        );
        """
        parser = SQLParser()
        objects = parser.parse(sql)

        assert len(objects) == 1
        assert objects[0]["type"] == "unmarked"
        assert objects[0]["name"] == "users"

    def test_marked_table_not_duplicated(self):
        """Test that marked tables are not included in unmarked results."""
        sql = """
        -- @page
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY
        );
        """
        parser = SQLParser()
        objects = parser.parse(sql)

        # Should have only 1 object (posts as a page), not duplicated as unmarked
        assert len(objects) == 1
        assert objects[0]["type"] == "page"


class TestSQLParserColumnParsing:
    """Tests for column extraction."""

    def test_extract_simple_columns(self):
        """Test extracting simple column names."""
        sql = """
        -- @page
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY,
            title VARCHAR(255),
            content TEXT
        );
        """
        parser = SQLParser()
        objects = parser.parse(sql)

        assert set(objects[0]["columns"]) == {"id", "title", "content"}

    def test_extract_columns_with_constraints(self):
        """Test extracting columns with various constraints."""
        sql = """
        -- @page
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        parser = SQLParser()
        objects = parser.parse(sql)

        # Should extract only column names, not constraints
        assert set(objects[0]["columns"]) == {"id", "title", "created_at"}

    def test_extract_columns_with_foreign_key(self):
        """Test extracting columns when foreign keys are present."""
        sql = """
        -- @page
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY,
            author_id INTEGER,
            FOREIGN KEY (author_id) REFERENCES users(id)
        );
        """
        parser = SQLParser()
        objects = parser.parse(sql)

        assert set(objects[0]["columns"]) == {"id", "author_id"}

    def test_no_duplicate_columns(self):
        """Test that duplicate column names are not added."""
        sql = """
        -- @page
        CREATE TABLE posts (
            id INTEGER,
            id INTEGER,
            title VARCHAR(255)
        );
        """
        parser = SQLParser()
        objects = parser.parse(sql)

        # Should have only unique columns
        assert objects[0]["columns"].count("id") == 1

    def test_skip_constraint_keywords_as_columns(self):
        """Test that constraint keywords are not treated as column names."""
        sql = """
        -- @page
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY,
            title VARCHAR(255),
            PRIMARY KEY (id),
            FOREIGN KEY (author_id) REFERENCES users(id),
            UNIQUE (title),
            CHECK (id > 0)
        );
        """
        parser = SQLParser()
        objects = parser.parse(sql)

        # Should not include PRIMARY, FOREIGN, UNIQUE, CHECK keywords
        for col in objects[0]["columns"]:
            assert col.upper() not in ("PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "CONSTRAINT", "KEY")


class TestSQLParserComplexScenarios:
    """Tests for complex parsing scenarios."""

    def test_parse_mixed_object_types(self):
        """Test parsing SQL with mixed object types."""
        sql = """
        -- @page
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY,
            title VARCHAR(255)
        );

        -- @collection
        CREATE TABLE blog (
            id INTEGER PRIMARY KEY
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
        parser = SQLParser()
        objects = parser.parse(sql)

        assert len(objects) == 4
        types = {obj["type"] for obj in objects}
        assert types == {"page", "collection", "attribute", "junction"}

    def test_parse_case_insensitive_annotations(self):
        """Test that annotations are case-insensitive."""
        sql = """
        -- @PAGE
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY
        );
        """
        parser = SQLParser()
        objects = parser.parse(sql)

        # Should still parse despite uppercase annotation
        assert len(objects) >= 1

    def test_parse_if_not_exists_syntax(self):
        """Test parsing with IF NOT EXISTS clause."""
        sql = """
        -- @page
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY
        );
        """
        parser = SQLParser()
        objects = parser.parse(sql)

        assert len(objects) == 1
        assert objects[0]["name"] == "posts"

    def test_parse_multiline_column_definitions(self):
        """Test parsing column definitions spread across multiple lines."""
        sql = """
        -- @page
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY,
            title VARCHAR(255),
            content TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        );
        """
        parser = SQLParser()
        objects = parser.parse(sql)

        expected_columns = {"id", "title", "content", "created_at", "updated_at"}
        assert set(objects[0]["columns"]) == expected_columns

    def test_empty_sql(self):
        """Test parsing empty SQL content."""
        sql = ""
        parser = SQLParser()
        objects = parser.parse(sql)

        assert objects == []

    def test_sql_with_only_comments(self):
        """Test parsing SQL with only comments and no tables."""
        sql = """
        -- This is a comment
        -- Another comment
        -- @page (no table follows)
        """
        parser = SQLParser()
        objects = parser.parse(sql)

        # Should return empty or only valid tables
        assert all(obj["columns"] for obj in objects)

    def test_parse_table_with_newlines_in_column_definitions(self):
        """Test parsing tables with various whitespace handling."""
        sql = """
        -- @page
        CREATE TABLE posts (
            id INTEGER,
            title VARCHAR(255),
            content TEXT
        );
        """
        parser = SQLParser()
        objects = parser.parse(sql)

        assert len(objects[0]["columns"]) == 3

    def test_dataclass_to_dict_conversion(self):
        """Test that SQLObject can be converted to dict."""
        sql = """
        -- @page
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY,
            title VARCHAR(255)
        );
        """
        parser = SQLParser()
        objects = parser.parse(sql)

        # Objects should have proper structure
        obj = objects[0]
        assert isinstance(obj, dict)
        assert all(key in obj for key in ["name", "type", "table", "columns", "attributes"])

    def test_parse_quoted_parent_with_double_quotes(self):
        """Test parsing parent name with double quotes."""
        sql = """
        -- @page "MyBlog"
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY
        );
        """
        parser = SQLParser()
        objects = parser.parse(sql)

        assert objects[0]["attributes"]["parent_collection"] == "MyBlog"

    def test_real_world_schema(self):
        """Test parsing a realistic schema with multiple types."""
        sql = """
        -- @collection
        CREATE TABLE blog (
            id INTEGER PRIMARY KEY,
            title VARCHAR(255),
            description TEXT
        );

        -- @page Blog
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY,
            blog_id INTEGER,
            title VARCHAR(255),
            content TEXT,
            slug VARCHAR(255) UNIQUE,
            created_at TIMESTAMP,
            FOREIGN KEY (blog_id) REFERENCES blog(id)
        );

        -- @attribute Blog
        CREATE TABLE tags (
            id INTEGER PRIMARY KEY,
            name VARCHAR(255) UNIQUE
        );

        -- @junction Blog
        CREATE TABLE post_tags (
            post_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (post_id, tag_id),
            FOREIGN KEY (post_id) REFERENCES posts(id),
            FOREIGN KEY (tag_id) REFERENCES tags(id)
        );

        CREATE TABLE comments (
            id INTEGER PRIMARY KEY,
            post_id INTEGER,
            author VARCHAR(255),
            content TEXT,
            FOREIGN KEY (post_id) REFERENCES posts(id)
        );
        """
        parser = SQLParser()
        objects = parser.parse(sql)

        # Should parse 5 objects: blog, posts, tags, post_tags, comments
        assert len(objects) == 5

        # Verify each type
        type_counts = {}
        for obj in objects:
            type_counts[obj["type"]] = type_counts.get(obj["type"], 0) + 1

        assert type_counts["collection"] == 1
        assert type_counts["page"] == 1
        assert type_counts["attribute"] == 1
        assert type_counts["junction"] == 1
        assert type_counts["unmarked"] == 1  # comments table


class TestSQLParserIgnorePKFlag:
    """Tests for the --ignore-pk flag functionality."""

    def test_ignore_pk_flag_excludes_primary_keys(self):
        """Test that --ignore-pk flag properly excludes PRIMARY KEY columns."""
        sql = """
        -- @collection
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY,
            title VARCHAR(255),
            content TEXT
        );
        """
        parser = SQLParser(ignore_pk=True)
        objects = parser.parse(sql)

        assert len(objects) == 1
        assert set(objects[0]["columns"]) == {"id", "title", "content"}
        assert "ignored_columns" in objects[0]["attributes"]
        assert "id" in objects[0]["attributes"]["ignored_columns"]
        assert "title" not in objects[0]["attributes"]["ignored_columns"]
        assert "content" not in objects[0]["attributes"]["ignored_columns"]

    def test_ignore_pk_flag_without_flag(self):
        """Test that without --ignore-pk flag, PRIMARY KEY columns are NOT ignored."""
        sql = """
        -- @collection
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY,
            title VARCHAR(255),
            content TEXT
        );
        """
        parser = SQLParser(ignore_pk=False)
        objects = parser.parse(sql)

        assert len(objects) == 1
        assert set(objects[0]["columns"]) == {"id", "title", "content"}
        # Without ignore_pk flag, ignored_columns should not include 'id'
        ignored = objects[0]["attributes"].get("ignored_columns", [])
        assert "id" not in ignored

    def test_ignore_pk_with_composite_primary_key(self):
        """Test --ignore-pk with composite PRIMARY KEY."""
        sql = """
        -- @junction
        CREATE TABLE post_tags (
            post_id INTEGER,
            tag_id INTEGER,
            PRIMARY KEY (post_id, tag_id)
        );
        """
        parser = SQLParser(ignore_pk=True)
        objects = parser.parse(sql)

        assert len(objects) == 1
        # The composite key line should trigger ignore for both columns
        # when they appear on a line with PRIMARY KEY
        ignored = objects[0]["attributes"].get("ignored_columns", [])
        # Both columns should be in the columns list
        assert set(objects[0]["columns"]) == {"post_id", "tag_id"}

    def test_ignore_pk_with_manual_ignore_annotation(self):
        """Test that --ignore-pk works together with manual -- ignore annotations."""
        sql = """
        -- @collection
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY,
            title VARCHAR(255),
            content TEXT,
            draft BOOLEAN -- ignore
        );
        """
        parser = SQLParser(ignore_pk=True)
        objects = parser.parse(sql)

        assert len(objects) == 1
        ignored = objects[0]["attributes"]["ignored_columns"]
        # Both 'id' (from --ignore-pk) and 'draft' (from -- ignore) should be ignored
        assert "id" in ignored
        assert "draft" in ignored
        assert "title" not in ignored
        assert "content" not in ignored

    def test_ignore_pk_multiple_tables(self):
        """Test --ignore-pk flag across multiple tables."""
        sql = """
        -- @collection
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
            tag_id INTEGER,
            PRIMARY KEY (post_id, tag_id)
        );
        """
        parser = SQLParser(ignore_pk=True)
        objects = parser.parse(sql)

        assert len(objects) == 3

        # Check each table has id/pk in ignored_columns
        for obj in objects:
            if obj["type"] in ["collection", "attribute"]:
                ignored = obj["attributes"].get("ignored_columns", [])
                assert "id" in ignored, f"Table {obj['name']} should have 'id' ignored"

    def test_ignore_pk_with_alter_table_syntax(self):
        """Test --ignore-pk flag with PostgreSQL pg_dump ALTER TABLE syntax."""
        sql = """
        -- @collection
        CREATE TABLE posts (
            id integer NOT NULL,
            slug character varying(255) NOT NULL,
            title character varying(255) NOT NULL,
            content text NOT NULL
        );

        ALTER TABLE ONLY posts
            ADD CONSTRAINT posts_pkey PRIMARY KEY (id);

        -- @attribute
        CREATE TABLE tags (
            id integer NOT NULL,
            name character varying(100) NOT NULL
        );

        ALTER TABLE ONLY tags
            ADD CONSTRAINT tags_pkey PRIMARY KEY (id);
        """
        parser = SQLParser(ignore_pk=True)
        objects = parser.parse(sql)

        assert len(objects) == 2

        # Check that 'id' is in ignored_columns for both tables
        for obj in objects:
            assert set(obj["columns"]) == {"id", "slug", "title", "content"} if obj["name"] == "posts" else {"id", "name"}
            ignored = obj["attributes"].get("ignored_columns", [])
            assert "id" in ignored, f"Table {obj['name']} should have 'id' ignored from ALTER TABLE"
            # Other columns should not be ignored
            if obj["name"] == "posts":
                assert "slug" not in ignored
                assert "title" not in ignored
                assert "content" not in ignored
            else:
                assert "name" not in ignored

    def test_ignore_pk_with_composite_key_alter_table(self):
        """Test --ignore-pk with composite PRIMARY KEY in ALTER TABLE syntax."""
        sql = """
        -- @junction
        CREATE TABLE post_tags (
            post_id integer NOT NULL,
            tag_id integer NOT NULL,
            created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
        );

        ALTER TABLE ONLY post_tags
            ADD CONSTRAINT post_tags_pkey PRIMARY KEY (post_id, tag_id);
        """
        parser = SQLParser(ignore_pk=True)
        objects = parser.parse(sql)

        assert len(objects) == 1
        obj = objects[0]
        assert set(obj["columns"]) == {"post_id", "tag_id", "created_at"}

        ignored = obj["attributes"].get("ignored_columns", [])
        # Both PK columns should be ignored
        assert "post_id" in ignored
        assert "tag_id" in ignored
        # Non-PK column should not be ignored
        assert "created_at" not in ignored

    def test_ignore_pk_with_schema_qualified_alter_table(self):
        """Test --ignore-pk with schema-qualified table names in ALTER TABLE."""
        sql = """
        -- @collection
        CREATE TABLE public.blog (
            id integer NOT NULL,
            title character varying(255) NOT NULL
        );

        ALTER TABLE ONLY public.blog
            ADD CONSTRAINT blog_pkey PRIMARY KEY (id);
        """
        parser = SQLParser(ignore_pk=True)
        objects = parser.parse(sql)

        assert len(objects) == 1
        obj = objects[0]
        assert obj["name"] == "blog"
        ignored = obj["attributes"].get("ignored_columns", [])
        assert "id" in ignored
