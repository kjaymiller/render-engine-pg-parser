"""
Type definitions and enums for render-engine-pg CLI.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class ObjectType(Enum):
    """Classification types for database objects."""

    PAGE = "page"
    COLLECTION = "collection"
    ATTRIBUTE = "attribute"
    JUNCTION = "junction"
    UNMARKED = "unmarked"

    def __str__(self) -> str:
        """Return the string value of the enum."""
        return self.value

    def is_marked(self) -> bool:
        """Check if this type is explicitly marked (not unmarked)."""
        return self != ObjectType.UNMARKED


@dataclass
class Classification:
    """Result of classifying a single table."""

    object_type: ObjectType
    parent_collection: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary format compatible with existing pipeline."""
        return {
            "type": self.object_type.value,
            "parent_collection": self.parent_collection,
        }
