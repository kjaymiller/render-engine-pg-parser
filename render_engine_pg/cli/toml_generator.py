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

        # Group queries by object name, removing comments and linebreaks
        insert_sql = {}

        for i, obj in enumerate(ordered_objects):
            if i < len(insert_queries):
                obj_name = obj["name"]
                # Remove comment lines (lines starting with --)
                query_lines = [
                    line for line in insert_queries[i].split('\n')
                    if not line.strip().startswith('--')
                ]
                # Join lines without linebreaks and clean up whitespace
                clean_query = ' '.join(line.strip() for line in query_lines if line.strip())
                insert_sql[obj_name] = clean_query

        # Process read queries if provided
        read_sql = {}
        if read_queries:
            read_sql = read_queries

        # Create TOML structure
        config = {
            "tool": {
                "render-engine": {
                    "pg": {
                        "insert_sql": insert_sql,
                    }
                }
            }
        }

        # Add read_sql if available
        if read_sql:
            config["tool"]["render-engine"]["pg"]["read_sql"] = read_sql

        # Generate TOML format
        return tomli_w.dumps(config)
