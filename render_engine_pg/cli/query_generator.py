"""
SQL insertion query generator for render-engine objects
"""

from typing import List, Dict, Any
import json


class InsertionQueryGenerator:
    """Generates SQL insertion queries based on objects and relationships"""

    def generate(
        self,
        objects: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
    ) -> tuple:
        """
        Generate insertion queries for objects considering relationships.

        Args:
            objects: List of parsed objects
            relationships: List of relationships between objects

        Returns:
            Tuple of (ordered_objects, queries) - both in proper dependency order
        """
        queries = []

        # Sort objects by dependency order (foreign keys should be inserted after their targets)
        ordered_objects = self._order_by_dependencies(objects, relationships)

        for obj in ordered_objects:
            query = self._generate_object_query(obj, relationships)
            if query:
                queries.append(query)

        return ordered_objects, queries

    def _order_by_dependencies(
        self,
        objects: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Order objects so that dependencies are inserted first.

        Args:
            objects: List of objects
            relationships: List of relationships

        Returns:
            Ordered list of objects
        """
        # Build dependency graph
        dependencies: Dict[str, set[str]] = {obj["name"]: set() for obj in objects}

        for rel in relationships:
            if rel["type"] == "foreign_key":
                dependencies[rel["source"]].add(rel["target"])
            elif rel["type"] == "many_to_many_attribute":
                # Junction tables depend on attribute tables being inserted first
                dependencies[rel["source"]].add(rel["target"])

        # Topological sort
        visited = set()
        ordered = []

        def visit(obj_name):
            if obj_name in visited:
                return
            visited.add(obj_name)

            for dep in dependencies.get(obj_name, set()):
                visit(dep)

            for obj in objects:
                if obj["name"] == obj_name:
                    ordered.append(obj)
                    return

        for obj in objects:
            visit(obj["name"])

        return ordered

    def _generate_object_query(
        self,
        obj: Dict[str, Any],
        relationships: List[Dict[str, Any]],
    ) -> str:
        """
        Generate an insertion query for a single object.

        Args:
            obj: Object to generate query for
            relationships: List of all relationships

        Returns:
            SQL insertion query string
        """
        table = obj["table"]
        columns = obj["columns"]
        ignored_columns = obj.get("attributes", {}).get("ignored_columns", [])
        unique_columns = obj.get("attributes", {}).get("unique_columns", [])
        obj_type = obj.get("type", "").lower()

        # Filter out ignored columns
        columns_to_insert = [col for col in columns if col not in ignored_columns]

        # Generate comment
        query_parts = [f"-- Insert {obj['type'].capitalize()}: {obj['name']}"]

        # Special handling for junction tables: map FK columns to referenced object IDs
        if obj_type == "junction":
            # Build FK column mappings by finding relationships where this junction is referenced
            fk_mappings = {}

            for rel in relationships:
                metadata = rel.get("metadata", {})
                if metadata.get("junction_table") == obj["name"]:
                    # This relationship involves our junction table
                    source_fk = metadata.get("source_fk_column")
                    source_obj = rel.get("source")

                    if source_fk and source_obj:
                        fk_mappings[source_fk] = source_obj

            col_str = ", ".join(columns_to_insert)
            values = []
            for col in columns_to_insert:
                if col in fk_mappings:
                    # This is a FK column - use the object ID placeholder
                    values.append(f"{{{fk_mappings[col]}_id}}")
                else:
                    # Regular column (like created_at) - use column name placeholder
                    values.append(f"{{{col}}}")
            values_str = ", ".join(values)
        else:
            # Non-junction handling: check for regular foreign keys
            col_str = ", ".join(columns_to_insert)

            # Generate values using {key} placeholders for t-string interpolation (Python 3.14+)
            values = []
            for col in columns_to_insert:
                # Check if this column is a foreign key
                is_fk = any(
                    rel["column"] == col and rel["source"] == obj["name"]
                    for rel in relationships
                )

                if is_fk:
                    # Use {key} reference placeholder for FK
                    rel = next(
                        r
                        for r in relationships
                        if r["column"] == col and r["source"] == obj["name"]
                    )
                    values.append(f"{{{rel['target']}_id}}")
                else:
                    # Use {key} placeholder for t-string interpolation
                    values.append(f"{{{col}}}")

            values_str = ", ".join(values)

        # Build INSERT statement
        insert_stmt = f"INSERT INTO {table} ({col_str})\nVALUES ({values_str})"

        # Add RETURNING clauses for ID retrieval in dependent queries
        should_return_id = False

        if obj_type == "junction" and "id" in columns:
            # Junctions with an id column should RETURNING id
            should_return_id = True
        elif obj_type == "attribute" and unique_columns:
            # Attributes with unique columns use ON CONFLICT ... RETURNING id
            unique_col = unique_columns[0]
            insert_stmt = insert_stmt.replace("\n", " ")  # Flatten before inserting conflict clause
            insert_stmt += f" ON CONFLICT ({unique_col}) DO UPDATE SET {unique_col} = EXCLUDED.{unique_col} RETURNING id"
            insert_stmt = insert_stmt.replace("INSERT INTO", "\nINSERT INTO")  # Re-format
        elif "id" in columns_to_insert:
            # Any table with an id column being inserted should return it (for junction references and dependent queries)
            # This includes pages, collections, attributes, and unmarked tables
            should_return_id = True

        if should_return_id and obj_type != "attribute":  # Don't double-add for attributes
            insert_stmt += " RETURNING id"

        insert_stmt += ";"

        query_parts.append(insert_stmt)

        return "\n".join(query_parts)
