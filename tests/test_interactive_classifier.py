"""Tests for InteractiveClassifier - guides user through table classification."""

import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from render_engine_pg.cli.interactive_classifier import InteractiveClassifier
from render_engine_pg.cli.types import ObjectType, Classification


class TestInteractiveClassifierBasics:
    """Tests for basic classification functionality."""

    def test_classifier_initialization(self):
        """Test that classifier initializes correctly."""
        classifier = InteractiveClassifier(verbose=False)
        assert classifier.verbose is False
        assert classifier.relationships == []

    def test_classifier_initialization_verbose(self):
        """Test classifier initialization with verbose flag."""
        classifier = InteractiveClassifier(verbose=True)
        assert classifier.verbose is True

    def test_shortcut_mapping(self):
        """Test that shortcut keys are correctly mapped to ObjectType."""
        classifier = InteractiveClassifier()
        assert classifier.SHORTCUT_TO_TYPE["p"] == ObjectType.PAGE
        assert classifier.SHORTCUT_TO_TYPE["c"] == ObjectType.COLLECTION
        assert classifier.SHORTCUT_TO_TYPE["a"] == ObjectType.ATTRIBUTE
        assert classifier.SHORTCUT_TO_TYPE["j"] == ObjectType.JUNCTION
        assert classifier.SHORTCUT_TO_TYPE["s"] is None  # skip


class TestClassifyTables:
    """Tests for the main classify_tables method."""

    def test_classify_single_unmarked_table(self):
        """Test classifying a single unmarked table."""
        objects = [
            {
                "name": "blog",
                "type": "unmarked",
                "table": "blog",
                "columns": ["id", "title", "content"],
                "attributes": {},
            }
        ]

        classifier = InteractiveClassifier()
        with patch("click.prompt", return_value="c"):
            result_objects, classified_count = classifier.classify_tables(objects)

        assert classified_count == 1
        assert result_objects[0]["type"] == "collection"
        assert result_objects[0]["attributes"]["collection_name"] == "blog"

    def test_classify_multiple_tables(self):
        """Test classifying multiple tables."""
        objects = [
            {
                "name": "blog",
                "type": "unmarked",
                "table": "blog",
                "columns": ["id", "title", "content"],
                "attributes": {},
            },
            {
                "name": "tags",
                "type": "unmarked",
                "table": "tags",
                "columns": ["id", "name"],
                "attributes": {},
            },
        ]

        classifier = InteractiveClassifier()
        # Simulate user input: 'c' for blog, 'a' for tags
        with patch("click.prompt", side_effect=["c", "", "a", ""]):
            result_objects, classified_count = classifier.classify_tables(objects)

        assert classified_count == 2
        assert result_objects[0]["type"] == ObjectType.COLLECTION.value
        assert result_objects[1]["type"] == ObjectType.ATTRIBUTE.value

    def test_skip_annotated_tables(self):
        """Test that annotated tables are skipped by default."""
        objects = [
            {
                "name": "blog",
                "type": "collection",
                "table": "blog",
                "columns": ["id", "title"],
                "attributes": {"collection_name": "blog"},
            },
            {
                "name": "tags",
                "type": "unmarked",
                "table": "tags",
                "columns": ["id", "name"],
                "attributes": {},
            },
        ]

        classifier = InteractiveClassifier()
        with patch("click.prompt", return_value="a"):
            result_objects, classified_count = classifier.classify_tables(
                objects, skip_annotated=True
            )

        # Only tags should be classified
        assert classified_count == 1
        assert result_objects[0]["type"] == "collection"  # unchanged
        assert result_objects[1]["type"] == ObjectType.ATTRIBUTE.value

    def test_skip_table_during_classification(self):
        """Test skipping a table during interactive classification."""
        objects = [
            {
                "name": "blog",
                "type": "unmarked",
                "table": "blog",
                "columns": ["id", "title"],
                "attributes": {},
            }
        ]

        classifier = InteractiveClassifier()
        with patch("click.prompt", return_value="s"):
            result_objects, classified_count = classifier.classify_tables(objects)

        assert classified_count == 0
        assert result_objects[0]["type"] == "unmarked"  # unchanged

    def test_no_unmarked_tables(self):
        """Test when there are no unmarked tables to classify."""
        objects = [
            {
                "name": "blog",
                "type": "collection",
                "table": "blog",
                "columns": ["id", "title"],
                "attributes": {"collection_name": "blog"},
            }
        ]

        classifier = InteractiveClassifier()
        result_objects, classified_count = classifier.classify_tables(objects)

        assert classified_count == 0
        assert result_objects == objects


class TestDisplayTableInfo:
    """Tests for table information display."""

    def test_display_table_info_with_columns(self):
        """Test that table info is displayed correctly."""
        obj = {
            "name": "blog",
            "type": "unmarked",
            "table": "blog",
            "columns": ["id", "title", "content"],
            "attributes": {},
        }

        classifier = InteractiveClassifier()
        # Should not raise
        classifier._display_table_info(obj)

    def test_display_table_info_with_primary_key(self):
        """Test that primary key is detected in display."""
        obj = {
            "name": "blog",
            "type": "unmarked",
            "table": "blog",
            "columns": ["id", "title", "content"],
            "attributes": {},
        }

        classifier = InteractiveClassifier()
        # Capture output to verify PK is displayed
        with patch("click.echo") as mock_echo:
            classifier._display_table_info(obj)
            # Check that "Primary Key" appears in output
            calls_str = "\n".join(str(call) for call in mock_echo.call_args_list)
            assert "Primary Key" in calls_str or "id" in calls_str


class TestPromptClassification:
    """Tests for user classification prompts."""

    def test_prompt_accepts_shortcut_p(self):
        """Test that 'p' shortcut returns PAGE ObjectType."""
        obj = {
            "name": "blog",
            "type": "unmarked",
            "table": "blog",
            "columns": ["id"],
            "attributes": {},
        }

        classifier = InteractiveClassifier()
        with patch("click.prompt", side_effect=["p", ""]):
            classification = classifier._prompt_classification(obj)

        assert classification.object_type == ObjectType.PAGE
        assert classification.parent_collection is None

    def test_prompt_accepts_shortcut_c(self):
        """Test that 'c' shortcut returns COLLECTION ObjectType."""
        obj = {
            "name": "blog",
            "type": "unmarked",
            "table": "blog",
            "columns": ["id"],
            "attributes": {},
        }

        classifier = InteractiveClassifier()
        with patch("click.prompt", side_effect=["c", ""]):
            classification = classifier._prompt_classification(obj)

        assert classification.object_type == ObjectType.COLLECTION
        assert classification.parent_collection is None

    def test_prompt_accepts_shortcut_a(self):
        """Test that 'a' shortcut returns ATTRIBUTE ObjectType."""
        obj = {
            "name": "tags",
            "type": "unmarked",
            "table": "tags",
            "columns": ["id", "name"],
            "attributes": {},
        }

        classifier = InteractiveClassifier()
        with patch("click.prompt", side_effect=["a", ""]):
            classification = classifier._prompt_classification(obj)

        assert classification.object_type == ObjectType.ATTRIBUTE
        assert classification.parent_collection is None

    def test_prompt_accepts_shortcut_j(self):
        """Test that 'j' shortcut returns JUNCTION ObjectType."""
        obj = {
            "name": "blog_tags",
            "type": "unmarked",
            "table": "blog_tags",
            "columns": ["blog_id", "tag_id"],
            "attributes": {},
        }

        classifier = InteractiveClassifier()
        with patch("click.prompt", side_effect=["j", ""]):
            classification = classifier._prompt_classification(obj)

        assert classification.object_type == ObjectType.JUNCTION
        assert classification.parent_collection is None

    def test_prompt_accepts_full_type_names(self):
        """Test that full ObjectType names are accepted."""
        obj = {
            "name": "blog",
            "type": "unmarked",
            "table": "blog",
            "columns": ["id"],
            "attributes": {},
        }

        classifier = InteractiveClassifier()
        with patch("click.prompt", side_effect=["page", ""]):
            classification = classifier._prompt_classification(obj)

        assert classification.object_type == ObjectType.PAGE

    def test_prompt_rejects_invalid_input(self):
        """Test that invalid input is rejected and re-prompted."""
        obj = {
            "name": "blog",
            "type": "unmarked",
            "table": "blog",
            "columns": ["id"],
            "attributes": {},
        }

        classifier = InteractiveClassifier()
        # First 'x' is invalid, then 'c' is valid
        with patch("click.prompt", side_effect=["x", "c", ""]):
            with patch("click.echo") as mock_echo:
                classification = classifier._prompt_classification(obj)

            assert classification.object_type == ObjectType.COLLECTION
            # Verify invalid choice message was shown
            calls_str = "\n".join(str(call) for call in mock_echo.call_args_list)
            assert "Invalid choice" in calls_str

    def test_prompt_with_parent_collection(self):
        """Test prompting for parent collection."""
        obj = {
            "name": "posts",
            "type": "unmarked",
            "table": "posts",
            "columns": ["id", "title"],
            "attributes": {},
        }

        classifier = InteractiveClassifier()
        with patch("click.prompt", side_effect=["p", "blog"]):
            classification = classifier._prompt_classification(obj)

        assert classification.object_type == ObjectType.PAGE
        assert classification.parent_collection == "blog"

    def test_prompt_parent_optional(self):
        """Test that parent collection is optional."""
        obj = {
            "name": "posts",
            "type": "unmarked",
            "table": "posts",
            "columns": ["id", "title"],
            "attributes": {},
        }

        classifier = InteractiveClassifier()
        with patch("click.prompt", side_effect=["p", ""]):
            classification = classifier._prompt_classification(obj)

        assert classification.object_type == ObjectType.PAGE
        assert classification.parent_collection is None

    def test_prompt_skip_returns_none(self):
        """Test that 's' returns None (skip) without prompting for parent."""
        obj = {
            "name": "blog",
            "type": "unmarked",
            "table": "blog",
            "columns": ["id"],
            "attributes": {},
        }

        classifier = InteractiveClassifier()
        with patch("click.prompt", side_effect=["s"]):
            classification = classifier._prompt_classification(obj)

        assert classification is None


class TestSuggestClassification:
    """Tests for classification suggestions."""

    def test_suggest_junction_table(self):
        """Test that junction tables are recognized."""
        objects = [
            {
                "name": "blog",
                "type": "collection",
                "table": "blog",
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
                "name": "blog_tags",
                "type": "unmarked",
                "table": "blog_tags",
                "columns": ["blog_id", "tag_id"],
                "attributes": {},
            },
        ]

        classifier = InteractiveClassifier()
        classifier.relationships = classifier.analyzer.analyze(objects)
        suggestion = classifier._suggest_classification(objects[2])

        assert suggestion is not None
        assert "junction" in suggestion.lower()

    def test_suggest_attribute_table(self):
        """Test that attribute tables are recognized."""
        obj = {
            "name": "tags",
            "type": "unmarked",
            "table": "tags",
            "columns": ["id", "name"],
            "attributes": {},
        }

        classifier = InteractiveClassifier()
        suggestion = classifier._suggest_classification(obj)

        assert suggestion is not None
        assert "attribute" in suggestion.lower() or "lookup" in suggestion.lower()

    def test_suggest_content_table(self):
        """Test that content tables are recognized."""
        obj = {
            "name": "blog",
            "type": "unmarked",
            "table": "blog",
            "columns": ["id", "title", "content", "description"],
            "attributes": {},
        }

        classifier = InteractiveClassifier()
        suggestion = classifier._suggest_classification(obj)

        assert suggestion is not None
        assert "content" in suggestion.lower()


class TestGetRelatedTables:
    """Tests for detecting related tables."""

    def test_get_related_tables_with_fk(self):
        """Test finding related tables through foreign keys."""
        objects = [
            {
                "name": "blog",
                "type": "collection",
                "table": "blog",
                "columns": ["id"],
                "attributes": {},
            },
            {
                "name": "posts",
                "type": "unmarked",
                "table": "posts",
                "columns": ["id", "blog_id"],
                "attributes": {},
            },
        ]

        classifier = InteractiveClassifier()
        classifier.relationships = classifier.analyzer.analyze(objects)
        related = classifier._get_related_tables("posts")

        assert "blog" in related

    def test_get_related_tables_no_relations(self):
        """Test when there are no related tables."""
        objects = [
            {
                "name": "blog",
                "type": "unmarked",
                "table": "blog",
                "columns": ["id", "title"],
                "attributes": {},
            }
        ]

        classifier = InteractiveClassifier()
        classifier.relationships = classifier.analyzer.analyze(objects)
        related = classifier._get_related_tables("blog")

        assert related == []


class TestIntegrationWithSchema:
    """Integration tests with realistic schemas."""

    def test_classify_kjaymiller_schema(self):
        """Test classifying the kjaymiller.com schema."""
        # Simulate the objects that SQLParser would extract
        objects = [
            {
                "name": "blog",
                "type": "unmarked",
                "table": "blog",
                "columns": ["id", "slug", "title", "content", "description", "date"],
                "attributes": {},
            },
            {
                "name": "notes",
                "type": "unmarked",
                "table": "notes",
                "columns": ["id", "slug", "title", "content", "description", "date"],
                "attributes": {},
            },
            {
                "name": "tags",
                "type": "unmarked",
                "table": "tags",
                "columns": ["id", "name"],
                "attributes": {},
            },
            {
                "name": "blog_tags",
                "type": "unmarked",
                "table": "blog_tags",
                "columns": ["blog_id", "tag_id"],
                "attributes": {},
            },
        ]

        classifier = InteractiveClassifier()
        # Simulate: blog=c, "", notes=c, "", tags=a, "", blog_tags=j, ""
        with patch("click.prompt", side_effect=["c", "", "c", "", "a", "", "j", ""]):
            result_objects, classified_count = classifier.classify_tables(objects)

        assert classified_count == 4
        assert result_objects[0]["type"] == ObjectType.COLLECTION.value
        assert result_objects[1]["type"] == ObjectType.COLLECTION.value
        assert result_objects[2]["type"] == ObjectType.ATTRIBUTE.value
        assert result_objects[3]["type"] == ObjectType.JUNCTION.value


class TestClassificationDataclass:
    """Tests for the Classification dataclass."""

    def test_classification_creation(self):
        """Test creating a Classification instance."""
        classification = Classification(
            object_type=ObjectType.COLLECTION, parent_collection="blog"
        )

        assert classification.object_type == ObjectType.COLLECTION
        assert classification.parent_collection == "blog"

    def test_classification_to_dict(self):
        """Test converting Classification to dictionary."""
        classification = Classification(
            object_type=ObjectType.COLLECTION, parent_collection="blog"
        )
        result = classification.to_dict()

        assert result["type"] == "collection"
        assert result["parent_collection"] == "blog"

    def test_classification_without_parent(self):
        """Test Classification without parent collection."""
        classification = Classification(object_type=ObjectType.PAGE)

        assert classification.object_type == ObjectType.PAGE
        assert classification.parent_collection is None


class TestObjectTypeEnum:
    """Tests for the ObjectType enum."""

    def test_object_type_values(self):
        """Test that ObjectType has correct values."""
        assert ObjectType.PAGE.value == "page"
        assert ObjectType.COLLECTION.value == "collection"
        assert ObjectType.ATTRIBUTE.value == "attribute"
        assert ObjectType.JUNCTION.value == "junction"
        assert ObjectType.UNMARKED.value == "unmarked"

    def test_object_type_string_conversion(self):
        """Test converting ObjectType to string."""
        assert str(ObjectType.PAGE) == "page"
        assert str(ObjectType.COLLECTION) == "collection"

    def test_is_marked(self):
        """Test the is_marked() method."""
        assert ObjectType.PAGE.is_marked() is True
        assert ObjectType.COLLECTION.is_marked() is True
        assert ObjectType.ATTRIBUTE.is_marked() is True
        assert ObjectType.JUNCTION.is_marked() is True
        assert ObjectType.UNMARKED.is_marked() is False
