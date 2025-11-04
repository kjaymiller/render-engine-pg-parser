"""
TOML configuration generator for render-engine PostgreSQL plugin settings
"""

from typing import List, Dict, Any

try:
    import tomli_w
except ImportError:
    tomli_w = None


class TOMLConfigGenerator:
    """Generates TOML configuration for render-engine.pg settings"""

    def generate(
        self,
        ordered_objects: List[Dict[str, Any]],
        insert_queries: List[str],
        read_queries: Dict[str, str] = None,
        relationships: List[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate TOML configuration with insert_sql and read_sql statements.
        Groups queries by collection/page, with supporting queries in dependency order.

        Args:
            ordered_objects: List of parsed objects in dependency order
            insert_queries: List of SQL insertion queries (matching ordered_objects)
            read_queries: Dictionary mapping object names to read queries
            relationships: List of relationships between objects (for grouping)

        Returns:
            TOML configuration string
        """
        if tomli_w is None:
            raise ImportError(
                "tomli_w is required for TOML generation. "
                "Install it with: pip install tomli_w"
            )

        # Create a mapping of object name to index for quick lookup
        obj_name_to_index = {obj["name"]: i for i, obj in enumerate(ordered_objects)}

        # Find all collection/page objects (primary objects)
        primary_objects = [
            obj for obj in ordered_objects
            if obj["type"].lower() in ("page", "collection")
        ]

        if not primary_objects:
            # Fallback: treat first object as primary (if any objects exist)
            if ordered_objects:
                primary_objects = [ordered_objects[0]]
            else:
                # No objects to process, return empty config
                config = {
                    "tool": {
                        "render-engine": {
                            "pg": {
                                "insert_sql": {},
                            }
                        }
                    }
                }
                return tomli_w.dumps(config)

        # Build insert_sql dictionary with one entry per collection/page
        insert_sql_dict = {}

        for primary_obj in primary_objects:
            primary_name = primary_obj["name"]

            # Find all objects that belong to this primary
            belonging_objects = self._get_objects_for_primary(
                primary_name,
                ordered_objects,
                relationships or []
            )

            # Collect queries for belonging objects in dependency order
            primary_queries = []
            for obj_name in belonging_objects:
                if obj_name in obj_name_to_index:
                    idx = obj_name_to_index[obj_name]
                    if idx < len(insert_queries):
                        # Remove comment lines (lines starting with --)
                        query_lines = [
                            line for line in insert_queries[idx].split('\n')
                            if not line.strip().startswith('--')
                        ]
                        # Join lines without linebreaks and clean up whitespace
                        clean_query = ' '.join(
                            line.strip() for line in query_lines if line.strip()
                        )
                        primary_queries.append(clean_query)

            if primary_queries:
                insert_sql_dict[primary_name] = primary_queries

        # Build read_sql dictionary with entries for pages/collections
        read_sql_dict = {}
        if read_queries:
            for primary_obj in primary_objects:
                primary_name = primary_obj["name"]
                if primary_name in read_queries:
                    read_sql_dict[primary_name] = read_queries[primary_name]

        # Create TOML structure: tool.render-engine.pg with insert_sql and read_sql
        config = {
            "tool": {
                "render-engine": {
                    "pg": {
                        "insert_sql": insert_sql_dict,
                    }
                }
            }
        }

        # Add read_sql if available
        if read_sql_dict:
            config["tool"]["render-engine"]["pg"]["read_sql"] = read_sql_dict

        # Generate TOML format
        return tomli_w.dumps(config)

    def _get_objects_for_primary(
        self,
        primary_name: str,
        ordered_objects: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
    ) -> List[str]:
        """
        Get all objects that belong to a primary (collection/page).

        An object belongs to a primary if:
        1. It is the primary itself
        2. It has a foreign key to the primary
        3. It's a junction table that references the primary

        Args:
            primary_name: Name of the primary object
            ordered_objects: List of all objects in dependency order
            relationships: List of relationships

        Returns:
            List of object names in dependency order
        """
        belonging_names = {primary_name}  # Start with the primary itself

        # Find objects that reference this primary
        for rel in relationships:
            # If source has FK to primary, source belongs to primary
            if rel.get("type") == "foreign_key" and rel.get("target") == primary_name:
                belonging_names.add(rel["source"])
            # For many-to-many, if source or target is primary, include junctions
            elif rel.get("type") == "many_to_many_attribute":
                if rel.get("source") == primary_name or rel.get("target") == primary_name:
                    # Add the junction table (stored in metadata)
                    metadata = rel.get("metadata", {})
                    junction_table = metadata.get("junction_table")
                    if junction_table:
                        # Find the object name for this junction table
                        for obj in ordered_objects:
                            if obj["table"] == junction_table:
                                belonging_names.add(obj["name"])
                                break
                    # Also add the target/source that isn't the primary
                    if rel.get("source") == primary_name:
                        belonging_names.add(rel.get("target"))
                    else:
                        belonging_names.add(rel.get("source"))

        # Handle shared dependencies: include objects that don't FK to anything
        # These are typically attributes like 'tags' that collections use
        for obj in ordered_objects:
            if obj["name"] == primary_name:
                continue
            obj_type = obj["type"].lower()
            if obj_type in ("attribute",):
                # Attributes don't typically have FKs back to collections
                # Check if anything in our belonging set depends on this attribute
                depends_on_attribute = False
                for rel in relationships:
                    if rel.get("target") == obj["name"] and rel["source"] in belonging_names:
                        depends_on_attribute = True
                        break
                if depends_on_attribute:
                    belonging_names.add(obj["name"])

        # Return objects in the order they appear in ordered_objects
        result = []
        for obj in ordered_objects:
            if obj["name"] in belonging_names:
                result.append(obj["name"])

        return result
