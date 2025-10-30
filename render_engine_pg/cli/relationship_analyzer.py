"""
Relationship analyzer for render-engine objects
"""

from typing import List, Dict, Any, Set
from dataclasses import dataclass


@dataclass
class Relationship:
    """Represents a relationship between objects"""

    source: str  # Object name
    target: str  # Object name
    type: str  # 'foreign_key', 'contains', 'references'
    column: str  # Column involved in relationship


class RelationshipAnalyzer:
    """Analyzes relationships between render-engine objects"""

    # Common foreign key patterns
    FK_PATTERNS = [
        r"_id$",  # Ends with _id
        r"fk_\w+",  # Starts with fk_
        r".*_ref$",  # Ends with _ref
    ]

    def analyze(self, objects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Analyze relationships between objects.

        Args:
            objects: List of parsed objects from SQLParser

        Returns:
            List of relationships with structure:
            {
                'source': str,
                'target': str,
                'type': str,
                'column': str,
                'metadata': {...}
            }
        """
        relationships = []
        table_names = {obj["table"]: obj["name"] for obj in objects}
        object_types = {obj["name"]: obj["type"] for obj in objects}

        for obj in objects:
            # Handle junction tables (many-to-many relationships)
            if obj["type"].lower() == "junction":
                relationships.extend(
                    self._analyze_junction_table(obj, objects, table_names, object_types)
                )
            else:
                # Look for foreign key columns
                for column in obj["columns"]:
                    fk_target = self._infer_fk_target(column, table_names)
                    if fk_target:
                        relationships.append(
                            {
                                "source": obj["name"],
                                "target": fk_target,
                                "type": "foreign_key",
                                "column": column,
                                "metadata": {
                                    "source_table": obj["table"],
                                    "inferred": True,
                                },
                            }
                        )

                # For collections, add relationship to items they contain
                if obj["type"].lower() == "collection":
                    # Look for columns that might reference pages
                    for column in obj["columns"]:
                        if column.startswith("item_") or column.endswith("_item"):
                            for candidate in objects:
                                if (
                                    candidate["type"].lower() == "page"
                                    and candidate["name"].lower()
                                    in column.lower()
                                ):
                                    relationships.append(
                                        {
                                            "source": obj["name"],
                                            "target": candidate["name"],
                                            "type": "contains",
                                            "column": column,
                                            "metadata": {"inferred": True},
                                        }
                                    )

        return relationships

    def _analyze_junction_table(
        self,
        junction_obj: Dict[str, Any],
        objects: List[Dict[str, Any]],
        table_names: Dict[str, str],
        object_types: Dict[str, str],
    ) -> List[Dict[str, Any]]:
        """
        Analyze a junction table to extract many-to-many relationships.

        Args:
            junction_obj: The junction table object
            objects: All parsed objects
            table_names: Mapping of table names to object names
            object_types: Mapping of object names to their types

        Returns:
            List of many-to-many relationship entries
        """
        relationships = []

        # Find foreign key columns in the junction table
        fk_columns = []
        for column in junction_obj["columns"]:
            fk_target = self._infer_fk_target(column, table_names)
            if fk_target:
                fk_columns.append({"column": column, "target": fk_target})

        # For junction tables with 2+ foreign keys, create many-to-many relationships
        if len(fk_columns) >= 2:
            # Create relationships between each pair of targets
            for i, fk1 in enumerate(fk_columns):
                for fk2 in fk_columns[i + 1 :]:
                    # Determine relationship types based on target object types
                    source_type = object_types.get(fk1["target"], "unknown")
                    target_type = object_types.get(fk2["target"], "unknown")

                    # Use different relationship types based on what we're connecting
                    rel_type = self._determine_junction_rel_type(source_type, target_type)

                    # Relationship from first target to second target through junction
                    relationships.append(
                        {
                            "source": fk1["target"],
                            "target": fk2["target"],
                            "type": rel_type,
                            "column": fk1["column"],
                            "metadata": {
                                "junction_table": junction_obj["name"],
                                "source_fk_column": fk1["column"],
                                "target_fk_column": fk2["column"],
                                "source_type": source_type,
                                "target_type": target_type,
                                "inferred": True,
                            },
                        }
                    )
                    # Reverse relationship (second to first)
                    relationships.append(
                        {
                            "source": fk2["target"],
                            "target": fk1["target"],
                            "type": rel_type,
                            "column": fk2["column"],
                            "metadata": {
                                "junction_table": junction_obj["name"],
                                "source_fk_column": fk2["column"],
                                "target_fk_column": fk1["column"],
                                "source_type": target_type,
                                "target_type": source_type,
                                "inferred": True,
                            },
                        }
                    )
        # If junction table has only 1 FK, treat it as a regular foreign key from the junction table
        elif len(fk_columns) == 1:
            relationships.append(
                {
                    "source": junction_obj["name"],
                    "target": fk_columns[0]["target"],
                    "type": "foreign_key",
                    "column": fk_columns[0]["column"],
                    "metadata": {
                        "source_table": junction_obj["table"],
                        "inferred": True,
                    },
                }
            )

        return relationships

    def _determine_junction_rel_type(self, source_type: str, target_type: str) -> str:
        """
        Determine the relationship type based on the types of objects being connected.

        Args:
            source_type: Type of source object (page, collection, attribute, unmarked)
            target_type: Type of target object (page, collection, attribute, unmarked)

        Returns:
            Relationship type string
        """
        # If either is an attribute or unmarked (inferred as attribute), use many_to_many_attribute
        if source_type in ("attribute", "unmarked") or target_type in ("attribute", "unmarked"):
            return "many_to_many_attribute"
        # If both are pages/collections, use many_to_many
        return "many_to_many"

    def _infer_fk_target(
        self, column: str, table_mapping: Dict[str, str]
    ) -> str | None:
        """
        Infer a foreign key target from column name and table mapping.

        Args:
            column: Column name
            table_mapping: Mapping of table names to object names

        Returns:
            Target object name or None
        """
        import re

        # Remove common suffixes
        base_name = re.sub(r"(_id|_ref|_fk)$", "", column, flags=re.IGNORECASE)

        # Check if base name matches any table exactly
        for table, obj_name in table_mapping.items():
            if table.lower() == base_name.lower():
                return obj_name
            if obj_name.lower() == base_name.lower():
                return obj_name

        # Try partial matching, but prefer shorter matches (more specific)
        # This avoids matching "posts_tags" when looking for "tag"
        base_name_lower = base_name.lower()
        candidates = []

        for table, obj_name in table_mapping.items():
            table_lower = table.lower()
            obj_lower = obj_name.lower()

            # Check for substring match (exact containment)
            if base_name_lower in table_lower or base_name_lower in obj_lower:
                candidates.append((len(obj_name), obj_name))
            # Also check for pluralized version (base_name + 's')
            elif base_name_lower + 's' in table_lower or base_name_lower + 's' in obj_lower:
                candidates.append((len(obj_name), obj_name))
            # Check for common plural endings like category -> categories
            elif base_name_lower.endswith('y') and base_name_lower[:-1] + 'ies' in obj_lower:
                candidates.append((len(obj_name), obj_name))
            # Check if table starts with base_name (e.g., author_id -> authors table)
            elif table_lower.startswith(base_name_lower) or obj_lower.startswith(base_name_lower):
                candidates.append((len(obj_name), obj_name))

        if candidates:
            # Return the candidate with the shortest name (most specific match)
            candidates.sort(key=lambda x: x[0])
            return candidates[0][1]

        return None
