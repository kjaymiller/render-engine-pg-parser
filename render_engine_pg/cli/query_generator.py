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
        dependencies = {obj["name"]: set() for obj in objects}

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

        # Generate comment
        query_parts = [f"-- Insert {obj['type'].capitalize()}: {obj['name']}"]

        # Build column list and placeholder values
        col_str = ", ".join(columns)

        # Generate example values using {key} placeholders
        values = []
        for col in columns:
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
                # Use {key} placeholder
                values.append(f"{{{col}}}")

        values_str = ", ".join(values)

        # Build INSERT statement
        insert_stmt = f"INSERT INTO {table} ({col_str})\nVALUES ({values_str});"

        query_parts.append(insert_stmt)

        return "\n".join(query_parts)
