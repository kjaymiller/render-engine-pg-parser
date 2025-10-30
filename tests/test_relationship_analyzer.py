"""Tests for RelationshipAnalyzer - detects relationships between objects."""

import pytest

from render_engine_pg.cli.relationship_analyzer import RelationshipAnalyzer


class TestForeignKeyDetection:
    """Tests for detecting foreign key relationships."""

    def test_detect_fk_with_id_suffix(self):
        """Test detecting foreign keys with _id suffix."""
        objects = [
            {
                "name": "posts",
                "type": "page",
                "table": "posts",
                "columns": ["id", "author_id"],
                "attributes": {},
            },
            {
                "name": "authors",
                "type": "page",
                "table": "authors",
                "columns": ["id", "name"],
                "attributes": {},
            },
        ]
        analyzer = RelationshipAnalyzer()
        relationships = analyzer.analyze(objects)

        # Should detect author_id -> authors relationship (prefix matching)
        fk_rels = [r for r in relationships if r["type"] == "foreign_key"]
        assert len(fk_rels) == 1
        assert fk_rels[0]["source"] == "posts"
        assert fk_rels[0]["target"] == "authors"
        assert fk_rels[0]["column"] == "author_id"

    def test_detect_fk_with_ref_suffix(self):
        """Test detecting foreign keys with _ref suffix."""
        objects = [
            {
                "name": "posts",
                "type": "page",
                "table": "posts",
                "columns": ["id", "category_ref"],
                "attributes": {},
            },
            {
                "name": "categories",
                "type": "page",
                "table": "categories",
                "columns": ["id"],
                "attributes": {},
            },
        ]
        analyzer = RelationshipAnalyzer()
        relationships = analyzer.analyze(objects)

        fk_rels = [r for r in relationships if r["type"] == "foreign_key"]
        assert len(fk_rels) >= 1
        # Should detect category -> categories relationship
        assert any(
            r["source"] == "posts" and r["target"] == "categories"
            for r in fk_rels
        )

    def test_no_fk_without_pattern(self):
        """Test that columns without FK patterns are not detected as FKs."""
        objects = [
            {
                "name": "posts",
                "type": "page",
                "table": "posts",
                "columns": ["id", "title", "content"],
                "attributes": {},
            }
        ]
        analyzer = RelationshipAnalyzer()
        relationships = analyzer.analyze(objects)

        fk_rels = [r for r in relationships if r["type"] == "foreign_key"]
        assert len(fk_rels) == 0

    def test_multiple_foreign_keys_in_single_object(self):
        """Test detecting multiple foreign keys in a single object."""
        objects = [
            {
                "name": "posts",
                "type": "page",
                "table": "posts",
                "columns": ["id", "author_id", "category_id"],
                "attributes": {},
            },
            {
                "name": "authors",
                "type": "page",
                "table": "authors",
                "columns": ["id"],
                "attributes": {},
            },
            {
                "name": "categories",
                "type": "page",
                "table": "categories",
                "columns": ["id"],
                "attributes": {},
            },
        ]
        analyzer = RelationshipAnalyzer()
        relationships = analyzer.analyze(objects)

        fk_rels = [r for r in relationships if r["type"] == "foreign_key"]
        assert len(fk_rels) == 2


class TestJunctionTableAnalysis:
    """Tests for analyzing junction tables."""

    def test_basic_many_to_many(self):
        """Test detecting many-to-many relationship from junction table."""
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
                "type": "page",
                "table": "tags",
                "columns": ["id"],
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
        analyzer = RelationshipAnalyzer()
        relationships = analyzer.analyze(objects)

        m2m_rels = [r for r in relationships if r["type"] == "many_to_many"]
        assert len(m2m_rels) == 2  # posts->tags and tags->posts
        assert any(r["source"] == "posts" and r["target"] == "tags" for r in m2m_rels)
        assert any(r["source"] == "tags" and r["target"] == "posts" for r in m2m_rels)

    def test_many_to_many_attribute(self):
        """Test detecting many-to-many-attribute when attribute is involved."""
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
            {
                "name": "post_tags",
                "type": "junction",
                "table": "post_tags",
                "columns": ["post_id", "tag_id"],
                "attributes": {},
            },
        ]
        analyzer = RelationshipAnalyzer()
        relationships = analyzer.analyze(objects)

        m2m_attr_rels = [r for r in relationships if r["type"] == "many_to_many_attribute"]
        assert len(m2m_attr_rels) >= 2
        assert any(
            r["source"] == "posts" and r["target"] == "tags"
            for r in m2m_attr_rels
        )

    def test_junction_with_single_fk(self):
        """Test junction table with only one foreign key."""
        objects = [
            {
                "name": "posts",
                "type": "page",
                "table": "posts",
                "columns": ["id"],
                "attributes": {},
            },
            {
                "name": "post_metadata",
                "type": "junction",
                "table": "post_metadata",
                "columns": ["post_id", "metadata_key"],
                "attributes": {},
            },
        ]
        analyzer = RelationshipAnalyzer()
        relationships = analyzer.analyze(objects)

        fk_rels = [r for r in relationships if r["type"] == "foreign_key"]
        # Junction with single FK should create foreign_key relationship
        assert any(
            r["source"] == "post_metadata" and r["target"] == "posts"
            for r in fk_rels
        )

    def test_junction_table_metadata(self):
        """Test that junction table metadata is correctly recorded."""
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
                "type": "page",
                "table": "tags",
                "columns": ["id"],
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
        analyzer = RelationshipAnalyzer()
        relationships = analyzer.analyze(objects)

        m2m_rels = [r for r in relationships if r["type"] == "many_to_many"]
        assert all("metadata" in r for r in m2m_rels)
        assert any(
            r["metadata"].get("junction_table") == "post_tags"
            for r in m2m_rels
        )


class TestContainsRelationships:
    """Tests for detecting contains relationships in collections."""

    def test_detect_collection_contains_page(self):
        """Test detecting that a collection contains a page."""
        objects = [
            {
                "name": "blog",
                "type": "collection",
                "table": "blog",
                "columns": ["item_posts"],
                "attributes": {},
            },
            {
                "name": "posts",
                "type": "page",
                "table": "posts",
                "columns": ["id"],
                "attributes": {},
            },
        ]
        analyzer = RelationshipAnalyzer()
        relationships = analyzer.analyze(objects)

        contains_rels = [r for r in relationships if r["type"] == "contains"]
        assert any(
            r["source"] == "blog" and r["target"] == "posts"
            for r in contains_rels
        )


class TestInferFKTarget:
    """Tests for FK target inference."""

    def test_exact_match_table_name(self):
        """Test matching column to exact table name."""
        analyzer = RelationshipAnalyzer()
        table_mapping = {"users": "users", "posts": "posts"}

        target = analyzer._infer_fk_target("user_id", table_mapping)
        assert target == "users"

    def test_exact_match_object_name(self):
        """Test matching column to object name (without table mapping)."""
        analyzer = RelationshipAnalyzer()
        table_mapping = {"users_table": "User"}

        target = analyzer._infer_fk_target("user_id", table_mapping)
        assert target == "User"

    def test_partial_match_with_suffix(self):
        """Test partial matching when removing suffix."""
        analyzer = RelationshipAnalyzer()
        table_mapping = {"categories": "Category"}

        target = analyzer._infer_fk_target("category_id", table_mapping)
        assert target == "Category"

    def test_pluralization_handling(self):
        """Test handling of pluralized names."""
        analyzer = RelationshipAnalyzer()
        table_mapping = {"tags": "tags"}

        target = analyzer._infer_fk_target("tag_id", table_mapping)
        assert target == "tags"

    def test_irregular_plural_handling(self):
        """Test handling of irregular plurals like category -> categories."""
        analyzer = RelationshipAnalyzer()
        table_mapping = {"categories": "categories"}

        target = analyzer._infer_fk_target("category_id", table_mapping)
        assert target == "categories"

    def test_no_match_returns_none(self):
        """Test that no match returns None."""
        analyzer = RelationshipAnalyzer()
        table_mapping = {"users": "users"}

        target = analyzer._infer_fk_target("unknown_id", table_mapping)
        assert target is None

    def test_shortest_match_preference(self):
        """Test that shortest matches are preferred (more specific)."""
        analyzer = RelationshipAnalyzer()
        # When looking for "tag_id", prefer "tags" over "posts_tags"
        table_mapping = {"tags": "tags", "post_tags": "post_tags"}

        target = analyzer._infer_fk_target("tag_id", table_mapping)
        assert target == "tags"


class TestDetermineJunctionRelType:
    """Tests for determining relationship type from object types."""

    def test_page_to_page_is_many_to_many(self):
        """Test that page-to-page is many_to_many."""
        analyzer = RelationshipAnalyzer()
        rel_type = analyzer._determine_junction_rel_type("page", "page")
        assert rel_type == "many_to_many"

    def test_page_to_attribute_is_many_to_many_attribute(self):
        """Test that page-to-attribute is many_to_many_attribute."""
        analyzer = RelationshipAnalyzer()
        rel_type = analyzer._determine_junction_rel_type("page", "attribute")
        assert rel_type == "many_to_many_attribute"

    def test_attribute_to_page_is_many_to_many_attribute(self):
        """Test that attribute-to-page is many_to_many_attribute."""
        analyzer = RelationshipAnalyzer()
        rel_type = analyzer._determine_junction_rel_type("attribute", "page")
        assert rel_type == "many_to_many_attribute"

    def test_unmarked_to_page_is_many_to_many_attribute(self):
        """Test that unmarked-to-page is many_to_many_attribute."""
        analyzer = RelationshipAnalyzer()
        rel_type = analyzer._determine_junction_rel_type("unmarked", "page")
        assert rel_type == "many_to_many_attribute"

    def test_collection_to_collection_is_many_to_many(self):
        """Test that collection-to-collection is many_to_many."""
        analyzer = RelationshipAnalyzer()
        rel_type = analyzer._determine_junction_rel_type("collection", "collection")
        assert rel_type == "many_to_many"


class TestAnalyzeComplexScenarios:
    """Tests for complex relationship scenarios."""

    def test_mixed_relationships(self):
        """Test analyzing mixed relationship types."""
        objects = [
            {
                "name": "posts",
                "type": "page",
                "table": "posts",
                "columns": ["id", "author_id"],
                "attributes": {},
            },
            {
                "name": "authors",
                "type": "page",
                "table": "authors",
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
            {
                "name": "post_tags",
                "type": "junction",
                "table": "post_tags",
                "columns": ["post_id", "tag_id"],
                "attributes": {},
            },
        ]
        analyzer = RelationshipAnalyzer()
        relationships = analyzer.analyze(objects)

        # Should detect:
        # 1. Foreign key: posts -> authors (author_id -> authors prefix match)
        # 2. Many-to-many-attribute: posts <-> tags
        assert len(relationships) > 0
        assert any(r["type"] == "foreign_key" for r in relationships)
        assert any(r["type"] == "many_to_many_attribute" for r in relationships)

    def test_self_referencing_table(self):
        """Test detecting self-referencing relationships."""
        objects = [
            {
                "name": "categories",
                "type": "page",
                "table": "categories",
                "columns": ["id", "categories_id"],
                "attributes": {},
            }
        ]
        analyzer = RelationshipAnalyzer()
        relationships = analyzer.analyze(objects)

        # Should detect categories_id -> categories relationship (substring match)
        fk_rels = [r for r in relationships if r["type"] == "foreign_key"]
        assert any(
            r["source"] == "categories" and r["target"] == "categories"
            for r in fk_rels
        )

    def test_empty_objects_list(self):
        """Test analyzing empty objects list."""
        analyzer = RelationshipAnalyzer()
        relationships = analyzer.analyze([])
        assert relationships == []

    def test_single_object_no_relationships(self):
        """Test that single object with no FKs produces no relationships."""
        objects = [
            {
                "name": "users",
                "type": "page",
                "table": "users",
                "columns": ["id", "name", "email"],
                "attributes": {},
            }
        ]
        analyzer = RelationshipAnalyzer()
        relationships = analyzer.analyze(objects)

        assert len(relationships) == 0

    def test_junction_with_three_foreign_keys(self):
        """Test junction table with multiple foreign key pairs."""
        objects = [
            {
                "name": "users",
                "type": "page",
                "table": "users",
                "columns": ["id"],
                "attributes": {},
            },
            {
                "name": "roles",
                "type": "page",
                "table": "roles",
                "columns": ["id"],
                "attributes": {},
            },
            {
                "name": "permissions",
                "type": "page",
                "table": "permissions",
                "columns": ["id"],
                "attributes": {},
            },
            {
                "name": "user_role_permissions",
                "type": "junction",
                "table": "user_role_permissions",
                "columns": ["user_id", "role_id", "permission_id"],
                "attributes": {},
            },
        ]
        analyzer = RelationshipAnalyzer()
        relationships = analyzer.analyze(objects)

        # Should create relationships for each pair
        m2m_rels = [r for r in relationships if r["type"] == "many_to_many"]
        assert len(m2m_rels) >= 3  # At least 3 pairs * 2 directions

    def test_relationship_metadata_complete(self):
        """Test that relationship metadata contains all required fields."""
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
        analyzer = RelationshipAnalyzer()
        relationships = analyzer.analyze(objects)

        assert all("source" in r for r in relationships)
        assert all("target" in r for r in relationships)
        assert all("type" in r for r in relationships)
        assert all("column" in r for r in relationships)
        assert all("metadata" in r for r in relationships)

    def test_case_insensitive_matching(self):
        """Test that FK target matching is case-insensitive."""
        objects = [
            {
                "name": "Posts",
                "type": "page",
                "table": "Posts",
                "columns": ["id", "Author_ID"],
                "attributes": {},
            },
            {
                "name": "Authors",
                "type": "page",
                "table": "Authors",
                "columns": ["id"],
                "attributes": {},
            },
        ]
        analyzer = RelationshipAnalyzer()
        relationships = analyzer.analyze(objects)

        fk_rels = [r for r in relationships if r["type"] == "foreign_key"]
        # Should detect relationship despite case differences (Author_ID starts with Author -> Authors)
        assert any(
            r["source"] == "Posts" and r["target"] == "Authors"
            for r in fk_rels
        )
