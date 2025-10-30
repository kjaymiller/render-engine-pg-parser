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
        objects: List[Dict[str, Any]],
        queries: List[str],
    ) -> str:
        """
        Generate TOML configuration with insert_sql statements.

        Args:
            objects: List of parsed objects (to get collection names)
            queries: List of SQL insertion queries

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

        for i, obj in enumerate(objects):
            if i < len(queries):
                obj_name = obj["name"]
                # Remove comment lines (lines starting with --)
                query_lines = [
                    line for line in queries[i].split('\n')
                    if not line.strip().startswith('--')
                ]
                # Join lines without linebreaks and clean up whitespace
                clean_query = ' '.join(line.strip() for line in query_lines if line.strip())
                insert_sql[obj_name] = clean_query

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

        # Generate TOML format
        return tomli_w.dumps(config)
