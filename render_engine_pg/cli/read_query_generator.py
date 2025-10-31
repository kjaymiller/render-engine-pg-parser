"""
SQL read query generator for render-engine objects with JOIN support
"""

from typing import List, Dict, Any


class ReadQueryGenerator:
    """Generates SQL SELECT queries with JOINs based on objects and relationships"""

    def generate(
        self,
        objects: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
    ) -> Dict[str, str]:
        """
        Generate read queries for objects with appropriate JOINs.

        Args:
            objects: List of parsed objects
            relationships: List of relationships between objects

        Returns:
            Dictionary mapping object names to SELECT query strings
        """
        queries = {}

        for obj in objects:
            query = self._generate_object_query(obj, objects, relationships)
            if query:
                queries[obj["name"]] = query

        return queries

    def _generate_object_query(
        self,
        obj: Dict[str, Any],
        all_objects: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
    ) -> str:
        """
        Generate a SELECT query for an object with JOINs.

        For collections: Returns all rows (no WHERE clause)
        For pages: Returns single row (WHERE id = {id})
        For attributes/junctions: Returns all rows

        Args:
            obj: Object to generate query for
            all_objects: All objects for reference
            relationships: List of all relationships

        Returns:
            SQL SELECT query string with JOINs
        """
        table = obj["table"]
        obj_name = obj["name"]
        obj_type = obj["type"].lower()

        # Handle junction tables specially
        if obj_type == "junction":
            return self._generate_junction_query(obj, all_objects, relationships)

        # Find related tables through foreign keys
        foreign_keys = [
            rel for rel in relationships
            if rel["source"] == obj_name and rel["type"] == "foreign_key"
        ]

        # Find many-to-many relationships (where this object is the source)
        many_to_many = [
            rel for rel in relationships
            if rel["source"] == obj_name and rel["type"] == "many_to_many_attribute"
        ]

        # Build the SELECT clause
        select_cols = [f"{table}.{col}" for col in obj["columns"]]

        # Start query with basic SELECT
        query_parts = [f"SELECT {', '.join(select_cols)}"]

        # Add FROM clause
        query_parts.append(f"FROM {table}")

        # Add JOINs for foreign keys
        for fk in foreign_keys:
            target_table = next(
                (o["table"] for o in all_objects if o["name"] == fk["target"]),
                fk["target"]
            )
            join_clause = f"LEFT JOIN {target_table} ON {table}.{fk['column']} = {target_table}.id"
            query_parts.append(join_clause)

        # Add JOINs for many-to-many relationships
        for m2m in many_to_many:
            target_name = m2m["target"]
            target_table = next(
                (o["table"] for o in all_objects if o["name"] == target_name),
                target_name
            )

            # Get junction table info from metadata
            metadata = m2m.get("metadata", {})
            junction_table = metadata.get("junction_table", f"{table}_{target_table}")
            source_fk_col = metadata.get("source_fk_column", f"{table.rstrip('s')}_id")
            target_fk_col = metadata.get("target_fk_column", f"{target_table.rstrip('s')}_id")

            # Add joins through junction table
            join_clause = f"LEFT JOIN {junction_table} ON {table}.id = {junction_table}.{source_fk_col}"
            query_parts.append(join_clause)

            join_clause2 = f"LEFT JOIN {target_table} ON {junction_table}.{target_fk_col} = {target_table}.id"
            query_parts.append(join_clause2)

        # Add WHERE clause based on object type
        # Pages: Single item lookup by ID
        # Collections/Attributes: All items (no WHERE clause)
        if obj_type == "page":
            query_parts.append(f"WHERE {table}.id = {{id}};")
        else:
            # Collections and attributes - fetch all items
            # Add ORDER BY for better defaults (by id, or by date if available)
            if "date" in obj["columns"]:
                query_parts.append(f"ORDER BY {table}.date DESC;")
            else:
                query_parts.append(";")

        return " ".join(query_parts)

    def _generate_junction_query(
        self,
        obj: Dict[str, Any],
        all_objects: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
    ) -> str:
        """
        Generate a SELECT query for junction tables.

        Args:
            obj: Junction table object
            all_objects: All objects for reference
            relationships: List of all relationships

        Returns:
            SQL SELECT query string
        """
        table = obj["table"]
        columns = obj["columns"]

        # Build column list
        col_str = ", ".join([f"{table}.{col}" for col in columns])

        # Junction tables typically have foreign keys to both sides
        query = f"SELECT {col_str} FROM {table};"

        return query
