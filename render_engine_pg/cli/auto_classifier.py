"""
Auto-classification of SQL tables based on heuristics and relationships.

Provides intelligent classification of database tables as pages, collections,
attributes, or junctions without requiring user interaction.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Any, Optional


class ObjectType(Enum):
    """Enumeration of render-engine object types."""

    PAGE = "page"
    COLLECTION = "collection"
    ATTRIBUTE = "attribute"
    JUNCTION = "junction"


@dataclass
class ClassificationResult:
    """Result of classifying an object."""

    object_type: ObjectType
    confidence: float  # 0.0 to 1.0
    suggested_parent: Optional[str] = None
    reasoning: str = ""


class AutoClassifier:
    """Automatically classify database objects based on schema analysis."""

    def __init__(self):
        """Initialize the classifier."""
        pass

    def classify(
        self,
        obj: Dict[str, Any],
        relationships: List[Dict[str, Any]],
        verbose: bool = False,
    ) -> ClassificationResult:
        """
        Automatically classify an object using heuristics.

        Args:
            obj: Object dict with name, type, table, columns, attributes
            relationships: List of relationship dicts from RelationshipAnalyzer
            verbose: If True, include detailed reasoning

        Returns:
            ClassificationResult with object_type, confidence, and reasoning
        """
        table_name = obj.get("name", "")
        columns = obj.get("columns", [])
        column_names = [col.lower() for col in columns]

        # Check for junction table characteristics
        if self._is_junction(table_name, columns, relationships):
            reasoning = (
                f"Junction table: has foreign key columns, connects multiple tables"
            )
            return ClassificationResult(
                object_type=ObjectType.JUNCTION,
                confidence=0.95,
                reasoning=reasoning if verbose else "",
            )

        # Check for attribute/lookup table characteristics
        if self._is_attribute(table_name, columns, relationships):
            reasoning = (
                f"Attribute/lookup table: few columns, referenced by multiple tables"
            )
            return ClassificationResult(
                object_type=ObjectType.ATTRIBUTE,
                confidence=0.85,
                reasoning=reasoning if verbose else "",
            )

        # Check for content table characteristics
        if self._has_content_columns(column_names):
            # Could be collection or page - check relationships
            has_fk_to_content = self._has_fk_to_content_table(
                table_name, relationships
            )
            if has_fk_to_content:
                reasoning = (
                    f"Page: has content columns and foreign key to another table"
                )
                obj_type = ObjectType.PAGE
                confidence = 0.75
            else:
                reasoning = f"Collection: has content columns, standalone"
                obj_type = ObjectType.COLLECTION
                confidence = 0.80
            return ClassificationResult(
                object_type=obj_type, confidence=confidence, reasoning=reasoning if verbose else ""
            )

        # Default: if no strong signals, classify as collection
        reasoning = f"Default classification: no strong signals detected"
        return ClassificationResult(
            object_type=ObjectType.COLLECTION,
            confidence=0.3,
            reasoning=reasoning if verbose else "",
        )

    def _is_junction(
        self,
        table_name: str,
        columns: List[str],
        relationships: List[Dict[str, Any]],
    ) -> bool:
        """
        Detect if table is a junction table (many-to-many relationship).

        Junction tables typically have:
        - 2+ foreign key columns
        - 2+ related tables
        - Few total columns (usually 2-4)
        """
        # Count FK columns (end with _id or _ref)
        fk_columns = [col for col in columns if col.endswith("_id") or col.endswith("_ref")]

        if len(fk_columns) < 2:
            return False

        if len(columns) > 4:
            return False

        # Check related tables
        related_tables = self._get_related_tables(table_name, relationships)
        if len(related_tables) >= 2:
            return True

        return False

    def _is_attribute(
        self,
        table_name: str,
        columns: List[str],
        relationships: List[Dict[str, Any]],
    ) -> bool:
        """
        Detect if table is an attribute/lookup table.

        Attribute tables typically have:
        - Few columns (usually 2-3: id + name/value)
        - Referenced by multiple other tables
        - Name contains patterns like: tag, category, status, type, role
        """
        # Check column count
        if len(columns) > 4:
            return False

        # Check if table is referenced multiple times (has many incoming relationships)
        referenced_count = sum(
            1 for rel in relationships if rel.get("target") == table_name
        )
        if referenced_count >= 2:
            return True

        # Check name patterns
        name_lower = table_name.lower()
        attribute_keywords = [
            "tag",
            "categor",
            "status",
            "type",
            "role",
            "state",
            "priority",
        ]
        if any(keyword in name_lower for keyword in attribute_keywords):
            return True

        return False

    def _has_content_columns(self, column_names: List[str]) -> bool:
        """Check if table has content/text columns."""
        content_keywords = [
            "content",
            "title",
            "description",
            "body",
            "text",
            "summary",
            "message",
        ]
        content_col_count = sum(
            1 for col in column_names if any(kw in col for kw in content_keywords)
        )
        return content_col_count >= 2

    def _has_fk_to_content_table(
        self,
        table_name: str,
        relationships: List[Dict[str, Any]],
    ) -> bool:
        """Check if table has foreign key to another content table."""
        for rel in relationships:
            if rel.get("source") == table_name and rel.get("type") == "foreign_key":
                return True
        return False

    def _get_related_tables(
        self,
        table_name: str,
        relationships: List[Dict[str, Any]],
    ) -> List[str]:
        """Get list of tables related to the given table."""
        related = set()
        for rel in relationships:
            if rel.get("source") == table_name:
                target = rel.get("target")
                if target:
                    related.add(target)
            elif rel.get("target") == table_name:
                source = rel.get("source")
                if source:
                    related.add(source)
        return sorted(list(related))
