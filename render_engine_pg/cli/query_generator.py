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
            query = self._generate_object_query(obj, relationships, objects)
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
        all_objects: List[Dict[str, Any]] | None = None,
    ) -> str:
        """
        Generate an insertion query for a single object.

        Args:
            obj: Object to generate query for
            relationships: List of all relationships
            all_objects: List of all objects (for junction table lookup)

        Returns:
            SQL insertion query string
        """
        table = obj["table"]
        columns = obj["columns"]
        ignored_columns = obj.get("attributes", {}).get("ignored_columns", [])
        unique_columns = obj.get("attributes", {}).get("unique_columns", [])
        obj_type = obj.get("type", "").lower()

        # Detect if this is a junction table (explicit or implicit)
        is_junction = obj_type == "junction"
        if not is_junction and obj_type == "unmarked" and all_objects:
            fk_cols = []
            for col in columns:
                is_fk = any(rel["column"] == col and rel["source"] == obj["name"] for rel in relationships)
                if is_fk:
                    fk_cols.append(col)
            # If table has 2+ FK columns and mostly FK columns, treat as junction
            is_junction = len(fk_cols) >= 2 and len(fk_cols) >= len(columns) - 2

        # Filter out ignored columns, but PRESERVE foreign key columns in junction tables
        # because they're essential for maintaining relationships
        if is_junction:
            # For junction tables, never ignore FK columns even if they're PKs
            fk_columns = set()

            # Find FK columns from many_to_many_attribute relationships
            # These relationships have the FK column info in metadata
            for rel in relationships:
                metadata = rel.get("metadata", {})
                if metadata.get("junction_table") == obj["name"]:
                    # This relationship involves our junction table
                    source_fk = metadata.get("source_fk_column")
                    target_fk = metadata.get("target_fk_column")
                    if source_fk:
                        fk_columns.add(source_fk)
                    if target_fk:
                        fk_columns.add(target_fk)

            columns_to_insert = [
                col for col in columns
                if col not in ignored_columns or col in fk_columns
            ]
        else:
            # For non-junction tables, filter out ignored columns normally
            columns_to_insert = [col for col in columns if col not in ignored_columns]

        # Generate comment
        query_parts = [f"-- Insert {obj['type'].capitalize()}: {obj['name']}"]

        # Special handling for junction tables: use subqueries to look up FK IDs
        if is_junction and all_objects:
            # Build FK column mappings and find unique lookup columns
            fk_info = {}  # column -> {target_obj, lookup_column}

            # Handle both explicit junctions (with metadata) and implicit junctions (detected from structure)
            for rel in relationships:
                metadata = rel.get("metadata", {})

                # For explicit junctions (marked as @junction)
                if metadata.get("junction_table") == obj["name"]:
                    source_fk = metadata.get("source_fk_column")
                    source_obj = rel.get("source")
                    target_fk = metadata.get("target_fk_column")
                    target_obj = rel.get("target")

                    # Handle source FK lookup
                    if source_fk and source_obj:
                        # Find the object definition to get unique columns
                        obj_def = next((o for o in all_objects if o["name"] == source_obj), None)
                        if obj_def:
                            # Prefer slug for collections/pages, name for attributes/tags
                            unique_cols = obj_def.get("attributes", {}).get("unique_columns", [])
                            lookup_col = None
                            if "slug" in obj_def["columns"]:
                                lookup_col = "slug"
                            elif unique_cols and unique_cols[0] != "id":
                                lookup_col = unique_cols[0]
                            elif "name" in obj_def["columns"]:
                                lookup_col = "name"
                            elif unique_cols:
                                lookup_col = unique_cols[0]

                            if lookup_col:
                                fk_info[source_fk] = {
                                    "target_obj": source_obj,
                                    "lookup_col": lookup_col,
                                    "table": obj_def["table"],
                                }

                    # Handle target FK lookup (for many_to_many_attribute relationships)
                    if target_fk and target_obj:
                        # Find the object definition to get unique columns
                        obj_def = next((o for o in all_objects if o["name"] == target_obj), None)
                        if obj_def:
                            # For attributes, prefer unique columns, then name
                            unique_cols = obj_def.get("attributes", {}).get("unique_columns", [])
                            lookup_col = None
                            if unique_cols and unique_cols[0] != "id":
                                lookup_col = unique_cols[0]
                            elif "name" in obj_def["columns"]:
                                lookup_col = "name"
                            elif "slug" in obj_def["columns"]:
                                lookup_col = "slug"
                            elif unique_cols:
                                lookup_col = unique_cols[0]

                            if lookup_col:
                                fk_info[target_fk] = {
                                    "target_obj": target_obj,
                                    "lookup_col": lookup_col,
                                    "table": obj_def["table"],
                                }

                # For implicit junctions (unmarked tables with FK columns)
                elif rel["source"] == obj["name"] and rel["type"] == "foreign_key":
                    fk_col = rel["column"]
                    target_obj = rel["target"]

                    # Find the object definition
                    obj_def = next((o for o in all_objects if o["name"] == target_obj), None)
                    if obj_def:
                        # Prefer slug for collections/pages, name for attributes/tags
                        unique_cols = obj_def.get("attributes", {}).get("unique_columns", [])
                        lookup_col = None
                        if "slug" in obj_def["columns"]:
                            lookup_col = "slug"
                        elif unique_cols and unique_cols[0] != "id":
                            lookup_col = unique_cols[0]
                        elif "name" in obj_def["columns"]:
                            lookup_col = "name"
                        elif unique_cols:
                            lookup_col = unique_cols[0]

                        if lookup_col:
                            fk_info[fk_col] = {
                                "target_obj": target_obj,
                                "lookup_col": lookup_col,
                                "table": obj_def["table"],
                            }

            # Generate the junction insert using subqueries for FK lookups
            col_str = ", ".join(columns_to_insert)

            # Build SELECT clause with subqueries for FK columns
            select_parts = []
            for col in columns_to_insert:
                if col in fk_info:
                    info = fk_info[col]
                    target_table = info["table"]
                    lookup_col = info["lookup_col"]
                    # Use subquery to look up ID using the unique identifier
                    select_parts.append(f"(SELECT id FROM {target_table} WHERE {lookup_col} = {{{lookup_col}}})")
                else:
                    # Regular column (like created_at) - use placeholder
                    select_parts.append(f"{{{col}}}")

            select_str = ", ".join(select_parts)

            # Use INSERT INTO ... SELECT for flexibility with subqueries
            insert_stmt = f"INSERT INTO {table} ({col_str})\nSELECT {select_str}"

            # Add RETURNING id if junction has an id column
            if "id" in columns:
                insert_stmt += " RETURNING id"

            insert_stmt += ";"

            return "\n".join([f"-- Insert {obj['type'].capitalize()}: {obj['name']}", insert_stmt])
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
        elif obj_type == "attribute":
            # Attributes always need to RETURN id for dependent queries
            if unique_columns:
                # Attributes with unique columns use ON CONFLICT ... RETURNING id
                unique_col = unique_columns[0]
                insert_stmt = insert_stmt.replace("\n", " ")  # Flatten before inserting conflict clause
                insert_stmt += f" ON CONFLICT ({unique_col}) DO UPDATE SET {unique_col} = EXCLUDED.{unique_col} RETURNING id"
                insert_stmt = insert_stmt.replace("INSERT INTO", "\nINSERT INTO")  # Re-format
            elif "id" in columns_to_insert:
                # Attributes without unique constraints still need to RETURN id
                should_return_id = True
        elif "id" in columns_to_insert:
            # Any table with an id column being inserted should return it (for junction references and dependent queries)
            # This includes pages, collections, and unmarked tables
            should_return_id = True

        if should_return_id:
            insert_stmt += " RETURNING id"

        insert_stmt += ";"

        query_parts.append(insert_stmt)

        return "\n".join(query_parts)
