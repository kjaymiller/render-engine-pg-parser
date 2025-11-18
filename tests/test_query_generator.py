"""Tests for InsertionQueryGenerator - generates SQL insertion queries."""

import pytest

from render_engine_pg.cli.query_generator import InsertionQueryGenerator


class TestBasicQueryGeneration:
    """Tests for basic query generation."""

    def test_simple_insert_query(self):
        """Test generating a simple INSERT query."""
        objects = [
            {
                "name": "users",
                "type": "page",
                "table": "users",
                "columns": ["id", "name", "email"],
                "attributes": {},
            }
        ]
        relationships = []

        generator = InsertionQueryGenerator()
        ordered_objects, queries = generator.generate(objects, relationships)

        assert len(queries) == 1
        assert "INSERT INTO users" in queries[0]
        assert "id, name, email" in queries[0]
        assert "{id}" in queries[0]
        assert "{name}" in queries[0]
        assert "{email}" in queries[0]

    def test_query_has_comment(self):
        """Test that generated queries include object type comment."""
        objects = [
            {
                "name": "users",
                "type": "page",
                "table": "users",
                "columns": ["id"],
                "attributes": {},
            }
        ]
        relationships = []

        generator = InsertionQueryGenerator()
        ordered_objects, queries = generator.generate(objects, relationships)

        assert "-- Insert Page: users" in queries[0]

    def test_multiple_objects_generate_multiple_queries(self):
        """Test generating queries for multiple objects."""
        objects = [
            {
                "name": "users",
                "type": "page",
                "table": "users",
                "columns": ["id"],
                "attributes": {},
            },
            {
                "name": "posts",
                "type": "page",
                "table": "posts",
                "columns": ["id", "title"],
                "attributes": {},
            },
        ]
        relationships = []

        generator = InsertionQueryGenerator()
        ordered_objects, queries = generator.generate(objects, relationships)

        assert len(queries) == 2


class TestForeignKeyPlaceholders:
    """Tests for foreign key placeholder generation."""

    def test_fk_column_gets_target_placeholder(self):
        """Test that FK columns get {target_id} placeholders."""
        objects = [
            {
                "name": "posts",
                "type": "page",
                "table": "posts",
                "columns": ["id", "author_id"],
                "attributes": {},
            },
            {
                "name": "users",
                "type": "page",
                "table": "users",
                "columns": ["id"],
                "attributes": {},
            },
        ]
        relationships = [
            {
                "source": "posts",
                "target": "users",
                "type": "foreign_key",
                "column": "author_id",
                "metadata": {},
            }
        ]

        generator = InsertionQueryGenerator()
        ordered_objects, queries = generator.generate(objects, relationships)

        # Find the posts query (not the users query)
        posts_query = next(q for q in queries if "posts" in q)
        assert "{users_id}" in posts_query or "{author_id}" in posts_query

    def test_multiple_fk_columns(self):
        """Test handling multiple foreign key columns."""
        objects = [
            {
                "name": "comments",
                "type": "page",
                "table": "comments",
                "columns": ["id", "post_id", "author_id"],
                "attributes": {},
            },
            {
                "name": "posts",
                "type": "page",
                "table": "posts",
                "columns": ["id"],
                "attributes": {},
            },
            {
                "name": "users",
                "type": "page",
                "table": "users",
                "columns": ["id"],
                "attributes": {},
            },
        ]
        relationships = [
            {
                "source": "comments",
                "target": "posts",
                "type": "foreign_key",
                "column": "post_id",
                "metadata": {},
            },
            {
                "source": "comments",
                "target": "users",
                "type": "foreign_key",
                "column": "author_id",
                "metadata": {},
            },
        ]

        generator = InsertionQueryGenerator()
        ordered_objects, queries = generator.generate(objects, relationships)

        comments_query = next(q for q in queries if "comments" in q)
        # Should have FK placeholders
        assert "{posts_id}" in comments_query or "{post_id}" in comments_query
        assert "{users_id}" in comments_query or "{author_id}" in comments_query


class TestDependencyOrdering:
    """Tests for topological sorting of objects by dependencies."""

    def test_dependent_objects_ordered_correctly(self):
        """Test that objects are ordered so dependencies come first."""
        objects = [
            {
                "name": "posts",
                "type": "page",
                "table": "posts",
                "columns": ["id", "author_id"],
                "attributes": {},
            },
            {
                "name": "users",
                "type": "page",
                "table": "users",
                "columns": ["id"],
                "attributes": {},
            },
        ]
        relationships = [
            {
                "source": "posts",
                "target": "users",
                "type": "foreign_key",
                "column": "author_id",
                "metadata": {},
            }
        ]

        generator = InsertionQueryGenerator()
        ordered_objects, queries = generator.generate(objects, relationships)

        # Users should be inserted before posts
        users_idx = next(i for i, q in enumerate(queries) if "users" in q)
        posts_idx = next(i for i, q in enumerate(queries) if "posts" in q)
        assert users_idx < posts_idx

    def test_no_circular_dependencies(self):
        """Test that circular dependencies don't cause infinite loops."""
        objects = [
            {
                "name": "a",
                "type": "page",
                "table": "a",
                "columns": ["id", "b_id"],
                "attributes": {},
            },
            {
                "name": "b",
                "type": "page",
                "table": "b",
                "columns": ["id", "a_id"],
                "attributes": {},
            },
        ]
        relationships = [
            {
                "source": "a",
                "target": "b",
                "type": "foreign_key",
                "column": "b_id",
                "metadata": {},
            },
            {
                "source": "b",
                "target": "a",
                "type": "foreign_key",
                "column": "a_id",
                "metadata": {},
            },
        ]

        generator = InsertionQueryGenerator()
        # Should not hang or raise an error
        queries = generator.generate(objects, relationships)
        assert len(queries) == 2

    def test_chain_dependencies(self):
        """Test ordering with chain of dependencies (A -> B -> C)."""
        objects = [
            {
                "name": "c",
                "type": "page",
                "table": "c",
                "columns": ["id"],
                "attributes": {},
            },
            {
                "name": "b",
                "type": "page",
                "table": "b",
                "columns": ["id", "c_id"],
                "attributes": {},
            },
            {
                "name": "a",
                "type": "page",
                "table": "a",
                "columns": ["id", "b_id"],
                "attributes": {},
            },
        ]
        relationships = [
            {
                "source": "b",
                "target": "c",
                "type": "foreign_key",
                "column": "c_id",
                "metadata": {},
            },
            {
                "source": "a",
                "target": "b",
                "type": "foreign_key",
                "column": "b_id",
                "metadata": {},
            },
        ]

        generator = InsertionQueryGenerator()
        ordered_objects, queries = generator.generate(objects, relationships)

        # Order should be c, b, a
        c_idx = next(i for i, q in enumerate(queries) if " c " in q or "table c" in q or "c (" in q)
        b_idx = next(i for i, q in enumerate(queries) if " b " in q or "table b" in q or "b (" in q)
        a_idx = next(i for i, q in enumerate(queries) if " a " in q or "table a" in q or "a (" in q)
        assert c_idx < b_idx < a_idx

    def test_independent_objects_can_be_any_order(self):
        """Test that independent objects can appear in any order."""
        objects = [
            {
                "name": "users",
                "type": "page",
                "table": "users",
                "columns": ["id"],
                "attributes": {},
            },
            {
                "name": "products",
                "type": "page",
                "table": "products",
                "columns": ["id"],
                "attributes": {},
            },
        ]
        relationships = []

        generator = InsertionQueryGenerator()
        ordered_objects, queries = generator.generate(objects, relationships)

        # Both objects should be present, order doesn't matter
        assert len(queries) == 2
        assert any("users" in q for q in queries)
        assert any("products" in q for q in queries)


class TestManyToManyRelationships:
    """Tests for handling many-to-many relationships."""

    def test_many_to_many_attribute_ordering(self):
        """Test that attributes depend on their sources in many-to-many."""
        objects = [
            {
                "name": "posts",
                "type": "page",
                "table": "posts",
                "columns": ["id"],
                "attributes": {},
            },
            {
                "name": "tags",
                "type": "attribute",
                "table": "tags",
                "columns": ["id"],
                "attributes": {},
            },
        ]
        relationships = [
            {
                "source": "posts",
                "target": "tags",
                "type": "many_to_many_attribute",
                "column": "post_id",
                "metadata": {},
            }
        ]

        generator = InsertionQueryGenerator()
        ordered_objects, queries = generator.generate(objects, relationships)

        # Tags should be inserted before posts (attribute dependency)
        tags_idx = next(i for i, q in enumerate(queries) if "tags" in q)
        posts_idx = next(i for i, q in enumerate(queries) if "posts" in q)
        assert tags_idx < posts_idx


class TestQueryFormat:
    """Tests for SQL query formatting."""

    def test_insert_statement_format(self):
        """Test that INSERT statements follow correct SQL format."""
        objects = [
            {
                "name": "users",
                "type": "page",
                "table": "users",
                "columns": ["id", "name"],
                "attributes": {},
            }
        ]
        relationships = []

        generator = InsertionQueryGenerator()
        ordered_objects, queries = generator.generate(objects, relationships)

        query = queries[0]
        # Should contain standard SQL INSERT INTO format
        assert "INSERT INTO" in query
        assert "(" in query
        assert ")" in query
        assert "VALUES" in query
        assert ";" in query

    def test_column_order_preserved(self):
        """Test that column order in INSERT matches definition."""
        objects = [
            {
                "name": "users",
                "type": "page",
                "table": "users",
                "columns": ["id", "email", "name"],
                "attributes": {},
            }
        ]
        relationships = []

        generator = InsertionQueryGenerator()
        ordered_objects, queries = generator.generate(objects, relationships)

        query = queries[0]
        # Should have columns in order
        assert "id, email, name" in query

    def test_placeholder_format(self):
        """Test that placeholders use {column_name} format."""
        objects = [
            {
                "name": "users",
                "type": "page",
                "table": "users",
                "columns": ["id", "email"],
                "attributes": {},
            }
        ]
        relationships = []

        generator = InsertionQueryGenerator()
        ordered_objects, queries = generator.generate(objects, relationships)

        query = queries[0]
        # Placeholders should be in {column} format
        assert "{id}" in query
        assert "{email}" in query


class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_empty_objects_list(self):
        """Test generating queries with empty objects list."""
        objects = []
        relationships = []

        generator = InsertionQueryGenerator()
        ordered_objects, queries = generator.generate(objects, relationships)

        assert queries == []

    def test_object_with_no_columns(self):
        """Test handling object with empty columns list."""
        objects = [
            {
                "name": "users",
                "type": "page",
                "table": "users",
                "columns": [],
                "attributes": {},
            }
        ]
        relationships = []

        generator = InsertionQueryGenerator()
        ordered_objects, queries = generator.generate(objects, relationships)

        # Should handle gracefully, might skip or generate empty insert
        assert isinstance(queries, list)

    def test_single_column_object(self):
        """Test object with only one column."""
        objects = [
            {
                "name": "users",
                "type": "page",
                "table": "users",
                "columns": ["id"],
                "attributes": {},
            }
        ]
        relationships = []

        generator = InsertionQueryGenerator()
        ordered_objects, queries = generator.generate(objects, relationships)

        assert len(queries) == 1
        assert "{id}" in queries[0]

    def test_object_type_in_comment(self):
        """Test that object type is properly capitalized in comment."""
        objects = [
            {
                "name": "users",
                "type": "page",
                "table": "users",
                "columns": ["id"],
                "attributes": {},
            },
            {
                "name": "tags",
                "type": "collection",
                "table": "tags",
                "columns": ["id"],
                "attributes": {},
            },
        ]
        relationships = []

        generator = InsertionQueryGenerator()
        ordered_objects, queries = generator.generate(objects, relationships)

        # Check proper capitalization in comments
        assert any("Page" in q for q in queries)
        assert any("Collection" in q for q in queries)

    def test_special_characters_in_column_names(self):
        """Test handling special characters in column names."""
        objects = [
            {
                "name": "users",
                "type": "page",
                "table": "users",
                "columns": ["id", "first_name", "last_name"],
                "attributes": {},
            }
        ]
        relationships = []

        generator = InsertionQueryGenerator()
        ordered_objects, queries = generator.generate(objects, relationships)

        assert len(queries) == 1
        assert "{first_name}" in queries[0]
        assert "{last_name}" in queries[0]

    def test_relationship_not_found_in_list(self):
        """Test handling when FK column not found in relationships list."""
        objects = [
            {
                "name": "posts",
                "type": "page",
                "table": "posts",
                "columns": ["id", "author_id"],
                "attributes": {},
            }
        ]
        # No relationships defined
        relationships = []

        generator = InsertionQueryGenerator()
        ordered_objects, queries = generator.generate(objects, relationships)

        # Should treat author_id as regular column, not FK
        assert "{author_id}" in queries[0]


class TestComplexScenarios:
    """Tests for complex real-world scenarios."""

    def test_blog_schema(self):
        """Test generating queries for a complete blog schema."""
        objects = [
            {
                "name": "users",
                "type": "page",
                "table": "users",
                "columns": ["id", "username", "email"],
                "attributes": {},
            },
            {
                "name": "posts",
                "type": "page",
                "table": "posts",
                "columns": ["id", "title", "content", "author_id"],
                "attributes": {},
            },
            {
                "name": "tags",
                "type": "attribute",
                "table": "tags",
                "columns": ["id", "name"],
                "attributes": {},
            },
            {
                "name": "post_tags",
                "type": "junction",
                "table": "post_tags",
                "columns": ["post_id", "tag_id"],
                "attributes": {},
            },
        ]
        relationships = [
            {
                "source": "posts",
                "target": "users",
                "type": "foreign_key",
                "column": "author_id",
                "metadata": {},
            },
            {
                "source": "posts",
                "target": "tags",
                "type": "many_to_many_attribute",
                "column": "post_id",
                "metadata": {},
            },
        ]

        generator = InsertionQueryGenerator()
        ordered_objects, queries = generator.generate(objects, relationships)

        assert len(queries) == 4
        # Verify all tables are present
        assert any("users" in q for q in queries)
        assert any("posts" in q for q in queries)
        assert any("tags" in q for q in queries)
        assert any("post_tags" in q for q in queries)

    def test_e_commerce_schema(self):
        """Test generating queries for e-commerce schema."""
        objects = [
            {
                "name": "categories",
                "type": "collection",
                "table": "categories",
                "columns": ["id", "name"],
                "attributes": {},
            },
            {
                "name": "products",
                "type": "page",
                "table": "products",
                "columns": ["id", "name", "category_id"],
                "attributes": {},
            },
            {
                "name": "orders",
                "type": "page",
                "table": "orders",
                "columns": ["id", "user_id", "order_date"],
                "attributes": {},
            },
            {
                "name": "order_items",
                "type": "junction",
                "table": "order_items",
                "columns": ["order_id", "product_id", "quantity"],
                "attributes": {},
            },
        ]
        relationships = [
            {
                "source": "products",
                "target": "categories",
                "type": "foreign_key",
                "column": "category_id",
                "metadata": {},
            }
        ]

        generator = InsertionQueryGenerator()
        ordered_objects, queries = generator.generate(objects, relationships)

        # Verify categories is before products
        cat_idx = next(i for i, q in enumerate(queries) if "categories" in q)
        prod_idx = next(i for i, q in enumerate(queries) if "products" in q)
        assert cat_idx < prod_idx


class TestIgnoredColumnsFiltering:
    """Tests for filtering out ignored columns from INSERT statements."""

    def test_ignored_columns_excluded_from_insert(self):
        """Test that ignored_columns are excluded from INSERT statements."""
        objects = [
            {
                "name": "posts",
                "type": "collection",
                "table": "posts",
                "columns": ["id", "title", "content"],
                "attributes": {
                    "ignored_columns": ["id"]
                },
            }
        ]
        relationships = []

        generator = InsertionQueryGenerator()
        ordered_objects, queries = generator.generate(objects, relationships)

        assert len(queries) == 1
        # Should have INSERT with title and content, but NOT id
        query = queries[0]
        assert "INSERT INTO posts" in query
        assert "title, content" in query or "content, title" in query
        assert "id" not in query.split("(")[1].split(")")[0]  # id should not be in column list

    def test_ignored_columns_with_multiple_columns(self):
        """Test ignored columns filtering with multiple ignored columns."""
        objects = [
            {
                "name": "users",
                "type": "page",
                "table": "users",
                "columns": ["id", "name", "email", "created_at", "updated_at"],
                "attributes": {
                    "ignored_columns": ["id", "created_at", "updated_at"]
                },
            }
        ]
        relationships = []

        generator = InsertionQueryGenerator()
        ordered_objects, queries = generator.generate(objects, relationships)

        query = queries[0]
        assert "INSERT INTO users" in query
        # Should only have name and email in the column list
        assert "name" in query
        assert "email" in query
        # Should NOT have id, created_at, or updated_at in column list
        column_part = query.split("(")[1].split(")")[0]
        assert "id" not in column_part
        assert "created_at" not in column_part
        assert "updated_at" not in column_part

    def test_no_ignored_columns_includes_all(self):
        """Test that without ignored_columns, all columns are included."""
        objects = [
            {
                "name": "posts",
                "type": "collection",
                "table": "posts",
                "columns": ["id", "title", "content"],
                "attributes": {},  # No ignored_columns
            }
        ]
        relationships = []

        generator = InsertionQueryGenerator()
        ordered_objects, queries = generator.generate(objects, relationships)

        query = queries[0]
        assert "INSERT INTO posts" in query
        # All columns should be present
        assert "id" in query
        assert "title" in query
        assert "content" in query

    def test_all_columns_ignored(self):
        """Test edge case where all columns are ignored."""
        objects = [
            {
                "name": "posts",
                "type": "collection",
                "table": "posts",
                "columns": ["id", "title", "content"],
                "attributes": {
                    "ignored_columns": ["id", "title", "content"]
                },
            }
        ]
        relationships = []

        generator = InsertionQueryGenerator()
        ordered_objects, queries = generator.generate(objects, relationships)

        # Should still generate a query (though it would be invalid SQL)
        # The important thing is it doesn't error
        assert len(queries) == 1


class TestAttributeExistenceHandling:
    """Tests for handling attributes that already exist in the database."""

    def test_attribute_on_conflict_with_unique_constraint(self):
        """Test that attributes with UNIQUE constraints generate ON CONFLICT clauses."""
        objects = [
            {
                "name": "tags",
                "type": "attribute",
                "table": "tags",
                "columns": ["id", "name"],
                "attributes": {
                    "unique_columns": ["name"]
                },
            }
        ]
        relationships = []

        generator = InsertionQueryGenerator()
        ordered_objects, queries = generator.generate(objects, relationships)

        # Should have ON CONFLICT for idempotent inserts
        assert len(queries) == 1
        query = queries[0]
        assert "ON CONFLICT (name) DO UPDATE SET" in query
        assert "RETURNING id" in query

    def test_junction_lookup_matches_incoming_data_field(self):
        """Test that junction table FK lookups use correct column names."""
        objects = [
            {
                "name": "tags",
                "type": "attribute",
                "table": "tags",
                "columns": ["id", "name"],
                "attributes": {
                    "unique_columns": ["name"]
                },
            },
            {
                "name": "posts",
                "type": "page",
                "table": "posts",
                "columns": ["id", "title", "slug"],
                "attributes": {
                    "unique_columns": ["slug"]
                },
            },
            {
                "name": "post_tags",
                "type": "junction",
                "table": "post_tags",
                "columns": ["post_id", "tag_id"],
                "attributes": {},
            },
        ]
        relationships = [
            {
                "source": "posts",
                "target": "tags",
                "type": "many_to_many_attribute",
                "column": "post_id",
                "metadata": {
                    "junction_table": "post_tags",
                    "source_fk_column": "post_id",
                    "target_fk_column": "tag_id",
                    "source_type": "page",
                    "target_type": "attribute"
                },
            }
        ]

        generator = InsertionQueryGenerator()
        ordered_objects, queries = generator.generate(objects, relationships)

        # Find the post_tags insertion query
        post_tags_query = next(q for q in queries if "post_tags" in q)

        # The lookup for tag_id should use 'name' since tags use name as unique identifier
        # The lookup should be: (SELECT id FROM tags WHERE name = {name})
        assert "(SELECT id FROM tags WHERE name = {name})" in post_tags_query
        # Verify post_id lookup uses slug since posts have slug as unique identifier
        assert "(SELECT id FROM posts WHERE slug = {slug})" in post_tags_query

    def test_repeated_tag_insertion_idempotent(self):
        """Test that inserting the same tag twice doesn't fail."""
        objects = [
            {
                "name": "tags",
                "type": "attribute",
                "table": "tags",
                "columns": ["id", "name"],
                "attributes": {
                    "unique_columns": ["name"]
                },
            }
        ]
        relationships = []

        generator = InsertionQueryGenerator()
        ordered_objects, queries = generator.generate(objects, relationships)

        query = queries[0]
        # ON CONFLICT clause enables idempotent inserts
        assert "ON CONFLICT (name)" in query
        assert "DO UPDATE SET" in query

    def test_attribute_without_unique_constraint_no_conflict(self):
        """Test that attributes without UNIQUE constraints don't get ON CONFLICT."""
        objects = [
            {
                "name": "categories",
                "type": "attribute",
                "table": "categories",
                "columns": ["id", "name"],
                "attributes": {},
            }
        ]
        relationships = []

        generator = InsertionQueryGenerator()
        ordered_objects, queries = generator.generate(objects, relationships)

        query = queries[0]
        # Without unique constraints, no ON CONFLICT
        assert "ON CONFLICT" not in query
        # But should still RETURN id for dependent queries
        assert "RETURNING id" in query

    def test_junction_with_existing_attribute_lookup(self):
        """Test junction insert uses correct lookup column for existing attributes."""
        objects = [
            {
                "name": "tags",
                "type": "attribute",
                "table": "tags",
                "columns": ["id", "slug", "name"],
                "attributes": {
                    "unique_columns": ["slug"]  # slug is the unique identifier
                },
            },
            {
                "name": "posts",
                "type": "page",
                "table": "posts",
                "columns": ["id", "title"],
                "attributes": {},
            },
            {
                "name": "post_tags",
                "type": "junction",
                "table": "post_tags",
                "columns": ["post_id", "tag_id"],
                "attributes": {},
            },
        ]
        relationships = [
            {
                "source": "posts",
                "target": "tags",
                "type": "many_to_many_attribute",
                "column": "post_id",
                "metadata": {
                    "junction_table": "post_tags",
                    "source_fk_column": "post_id",
                    "target_fk_column": "tag_id",
                    "source_type": "page",
                    "target_type": "attribute"
                },
            }
        ]

        generator = InsertionQueryGenerator()
        ordered_objects, queries = generator.generate(objects, relationships)

        post_tags_query = next(q for q in queries if "post_tags" in q)

        # Should use slug since it's the unique column for tags
        assert "(SELECT id FROM tags WHERE slug = {slug})" in post_tags_query
