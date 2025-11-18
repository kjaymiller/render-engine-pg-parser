"""Tests for AutoClassifier - automatic table classification."""

import pytest

from render_engine_pg.cli.auto_classifier import (
    AutoClassifier,
    ObjectType,
)


class TestAutoClassifierJunctionDetection:
    """Tests for detecting junction tables."""

    def test_detect_junction_with_two_fk_columns(self):
        """Test detecting junction table with 2 FK columns."""
        classifier = AutoClassifier()
        obj = {
            "name": "post_tags",
            "type": "unmarked",
            "table": "post_tags",
            "columns": ["post_id", "tag_id"],
            "attributes": {},
        }
        relationships = [
            {"source": "post_tags", "target": "posts"},
            {"source": "post_tags", "target": "tags"},
        ]

        result = classifier.classify(obj, relationships)

        assert result.object_type == ObjectType.JUNCTION
        assert result.confidence >= 0.9

    def test_detect_junction_with_multiple_related_tables(self):
        """Test junction detection with multiple relationships."""
        classifier = AutoClassifier()
        obj = {
            "name": "blog_tags",
            "type": "unmarked",
            "table": "blog_tags",
            "columns": ["blog_id", "tag_id", "created_at"],
            "attributes": {},
        }
        relationships = [
            {"source": "blog_tags", "target": "blog"},
            {"source": "blog_tags", "target": "tags"},
        ]

        result = classifier.classify(obj, relationships)

        assert result.object_type == ObjectType.JUNCTION
        assert result.confidence >= 0.9

    def test_not_junction_too_many_columns(self):
        """Test that tables with many columns are not classified as junction."""
        classifier = AutoClassifier()
        obj = {
            "name": "post_tags",
            "type": "unmarked",
            "table": "post_tags",
            "columns": ["id", "post_id", "tag_id", "created_at", "updated_at", "deleted_at"],
            "attributes": {},
        }
        relationships = [
            {"source": "post_tags", "target": "posts"},
            {"source": "post_tags", "target": "tags"},
        ]

        result = classifier.classify(obj, relationships)

        # Should not be junction due to many columns
        assert result.object_type != ObjectType.JUNCTION

    def test_not_junction_single_fk(self):
        """Test that tables with single FK are not junction."""
        classifier = AutoClassifier()
        obj = {
            "name": "post_comments",
            "type": "unmarked",
            "table": "post_comments",
            "columns": ["id", "post_id", "content"],
            "attributes": {},
        }
        relationships = [
            {"source": "post_comments", "target": "posts"},
        ]

        result = classifier.classify(obj, relationships)

        # Should not be junction (only one FK)
        assert result.object_type != ObjectType.JUNCTION


class TestAutoClassifierAttributeDetection:
    """Tests for detecting attribute/lookup tables."""

    def test_detect_attribute_by_name_pattern(self):
        """Test detecting attribute table by name pattern."""
        classifier = AutoClassifier()
        obj = {
            "name": "tags",
            "type": "unmarked",
            "table": "tags",
            "columns": ["id", "name"],
            "attributes": {},
        }
        relationships = []

        result = classifier.classify(obj, relationships)

        assert result.object_type == ObjectType.ATTRIBUTE
        assert result.confidence >= 0.8

    def test_detect_attribute_categories(self):
        """Test detecting categories as attribute table."""
        classifier = AutoClassifier()
        obj = {
            "name": "categories",
            "type": "unmarked",
            "table": "categories",
            "columns": ["id", "name", "slug"],
            "attributes": {},
        }
        relationships = []

        result = classifier.classify(obj, relationships)

        assert result.object_type == ObjectType.ATTRIBUTE
        assert result.confidence >= 0.8

    def test_detect_attribute_by_referenced_count(self):
        """Test detecting attribute table by how many tables reference it."""
        classifier = AutoClassifier()
        obj = {
            "name": "priorities",
            "type": "unmarked",
            "table": "priorities",
            "columns": ["id", "name"],
            "attributes": {},
        }
        # Referenced by multiple tables
        relationships = [
            {"source": "tasks", "target": "priorities"},
            {"source": "issues", "target": "priorities"},
            {"source": "bugs", "target": "priorities"},
        ]

        result = classifier.classify(obj, relationships)

        assert result.object_type == ObjectType.ATTRIBUTE
        assert result.confidence >= 0.8

    def test_not_attribute_many_columns(self):
        """Test that tables with many columns are not classified as attribute."""
        classifier = AutoClassifier()
        obj = {
            "name": "tags",
            "type": "unmarked",
            "table": "tags",
            "columns": ["id", "name", "description", "created_at", "updated_at", "deleted_at"],
            "attributes": {},
        }
        relationships = []

        result = classifier.classify(obj, relationships)

        # Should not be attribute due to many columns
        assert result.object_type != ObjectType.ATTRIBUTE


class TestAutoClassifierContentDetection:
    """Tests for detecting content tables (collections/pages)."""

    def test_detect_collection_with_content_columns(self):
        """Test detecting collection by content columns."""
        classifier = AutoClassifier()
        obj = {
            "name": "blog",
            "type": "unmarked",
            "table": "blog",
            "columns": ["id", "title", "content", "slug", "date"],
            "attributes": {},
        }
        relationships = []

        result = classifier.classify(obj, relationships)

        assert result.object_type == ObjectType.COLLECTION
        assert result.confidence >= 0.7

    def test_detect_collection_with_title_and_description(self):
        """Test detecting collection with title and description."""
        classifier = AutoClassifier()
        obj = {
            "name": "posts",
            "type": "unmarked",
            "table": "posts",
            "columns": ["id", "title", "description", "slug", "author_id"],
            "attributes": {},
        }
        relationships = []

        result = classifier.classify(obj, relationships)

        assert result.object_type == ObjectType.COLLECTION
        assert result.confidence >= 0.6

    def test_detect_page_with_fk_to_content(self):
        """Test detecting page (content table with FK to another table)."""
        classifier = AutoClassifier()
        obj = {
            "name": "posts",
            "type": "unmarked",
            "table": "posts",
            "columns": ["id", "blog_id", "title", "content", "slug"],
            "attributes": {},
        }
        relationships = [
            {"source": "posts", "target": "blog", "type": "foreign_key"},
        ]

        result = classifier.classify(obj, relationships)

        assert result.object_type == ObjectType.PAGE
        assert result.confidence >= 0.7

    def test_not_content_single_content_column(self):
        """Test that table with single content column defaults to low-confidence classification."""
        classifier = AutoClassifier()
        obj = {
            "name": "comments",
            "type": "unmarked",
            "table": "comments",
            "columns": ["id", "post_id", "content"],
            "attributes": {},
        }
        relationships = [
            {"source": "comments", "target": "posts", "type": "foreign_key"},
        ]

        result = classifier.classify(obj, relationships)

        # Single content column is not enough for high-confidence content classification
        # Should default to collection with low confidence
        assert result.object_type == ObjectType.COLLECTION
        assert result.confidence < 0.5


class TestAutoClassifierEdgeCases:
    """Tests for edge cases and default behavior."""

    def test_unclassifiable_table_defaults_to_collection(self):
        """Test that tables with no clear signals default to collection with low confidence."""
        classifier = AutoClassifier()
        obj = {
            "name": "misc",
            "type": "unmarked",
            "table": "misc",
            "columns": ["id", "data"],
            "attributes": {},
        }
        relationships = []

        result = classifier.classify(obj, relationships)

        assert result.object_type == ObjectType.COLLECTION
        assert result.confidence < 0.5

    def test_classify_with_verbose_reasoning(self):
        """Test that verbose mode includes reasoning."""
        classifier = AutoClassifier()
        obj = {
            "name": "blog",
            "type": "unmarked",
            "table": "blog",
            "columns": ["id", "title", "content"],
            "attributes": {},
        }
        relationships = []

        result = classifier.classify(obj, relationships, verbose=True)

        assert result.reasoning != ""
        assert "content" in result.reasoning.lower()

    def test_classify_without_verbose_no_reasoning(self):
        """Test that non-verbose mode excludes reasoning."""
        classifier = AutoClassifier()
        obj = {
            "name": "blog",
            "type": "unmarked",
            "table": "blog",
            "columns": ["id", "title", "content"],
            "attributes": {},
        }
        relationships = []

        result = classifier.classify(obj, relationships, verbose=False)

        assert result.reasoning == ""


class TestAutoClassifierMultipleTables:
    """Tests for classifying multiple tables in a schema."""

    def test_classify_mixed_schema(self):
        """Test classifying a mixed schema with different table types."""
        classifier = AutoClassifier()

        # Collection table
        blog_obj = {
            "name": "blog",
            "type": "unmarked",
            "table": "blog",
            "columns": ["id", "title", "content"],
            "attributes": {},
        }

        # Attribute table
        tags_obj = {
            "name": "tags",
            "type": "unmarked",
            "table": "tags",
            "columns": ["id", "name"],
            "attributes": {},
        }

        # Junction table
        blog_tags_obj = {
            "name": "blog_tags",
            "type": "unmarked",
            "table": "blog_tags",
            "columns": ["blog_id", "tag_id"],
            "attributes": {},
        }

        relationships = [
            {"source": "blog_tags", "target": "blog"},
            {"source": "blog_tags", "target": "tags"},
        ]

        # Classify each
        blog_result = classifier.classify(blog_obj, relationships)
        tags_result = classifier.classify(tags_obj, relationships)
        blog_tags_result = classifier.classify(blog_tags_obj, relationships)

        assert blog_result.object_type == ObjectType.COLLECTION
        assert tags_result.object_type == ObjectType.ATTRIBUTE
        assert blog_tags_result.object_type == ObjectType.JUNCTION
