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
    ) -> str:
        """
        Generate TOML configuration with insert_sql and read_sql statements.
        Groups all queries by the main collection/page, with supporting queries in order.

        Args:
            ordered_objects: List of parsed objects in dependency order
            insert_queries: List of SQL insertion queries (matching ordered_objects)
            read_queries: Dictionary mapping object names to read queries

        Returns:
            TOML configuration string
        """
        if tomli_w is None:
            raise ImportError(
                "tomli_w is required for TOML generation. "
                "Install it with: pip install tomli_w"
            )

        # Find the main object (page or collection, prioritize collection)
        main_obj = None
        main_obj_idx = None

        for i, obj in enumerate(ordered_objects):
            obj_type = obj["type"].lower()
            if obj_type in ("page", "collection"):
                main_obj = obj
                main_obj_idx = i
                if obj_type == "collection":
                    break  # Prefer collection

        if not main_obj:
            # Fallback to first object if no page/collection found
            main_obj = ordered_objects[0]
            main_obj_idx = 0

        # Collect all insert queries in dependency order
        all_insert_queries = []
        for i, obj in enumerate(ordered_objects):
            if i < len(insert_queries):
                # Remove comment lines (lines starting with --)
                query_lines = [
                    line for line in insert_queries[i].split('\n')
                    if not line.strip().startswith('--')
                ]
                # Join lines without linebreaks and clean up whitespace
                clean_query = ' '.join(line.strip() for line in query_lines if line.strip())
                all_insert_queries.append(clean_query)

        # Create TOML structure with main object as key
        main_obj_name = main_obj["name"]

        # Build the main object config
        pg_config = {
            "insert_sql": all_insert_queries,
        }

        # Add read query for main object if available
        if read_queries and main_obj_name in read_queries:
            pg_config["read_sql"] = read_queries[main_obj_name]

        config = {
            "tool": {
                "render-engine": {
                    "pg": {
                        main_obj_name: pg_config
                    }
                }
            }
        }

        # Generate TOML format
        return tomli_w.dumps(config)
