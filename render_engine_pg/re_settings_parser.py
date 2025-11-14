"""Settings parser for render-engine PostgreSQL plugin."""

import logging
import tomllib
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class PGSettings:
    """
    Manages render-engine PostgreSQL plugin settings from pyproject.toml.

    Looks for configuration under [tool.render-engine.pg] in pyproject.toml
    """

    DEFAULT_SETTINGS: dict[str, Any] = {
        "read_sql": {},
        "insert_sql": {},
        "default_table": None,
        "auto_commit": True,
    }

    def __init__(self, config_path: Path | str | None = None):
        """
        Initialize settings parser.

        Args:
            config_path: Path to pyproject.toml. If None, searches for it starting
                        from current directory and moving up.
        """
        self.config_path = config_path or self._find_pyproject_toml()
        self.settings = self._load_settings()

    @staticmethod
    def _find_pyproject_toml(start_path: Path | None = None) -> Path | None:
        """Find pyproject.toml by searching up from start_path or current directory."""
        current = Path(start_path or ".").resolve()

        # Search up the directory tree
        for _ in range(10):  # Limit search depth
            pyproject = current / "pyproject.toml"
            if pyproject.exists():
                logger.debug(f"Found pyproject.toml at {pyproject}")
                return pyproject
            if current.parent == current:  # Reached root
                break
            current = current.parent

        logger.warning("Could not find pyproject.toml")
        return None

    def _load_settings(self) -> dict[str, Any]:
        """Load settings from pyproject.toml."""
        if self.config_path is None or (isinstance(self.config_path, (str, Path)) and not Path(self.config_path).exists()):
            logger.warning(
                f"pyproject.toml not found at {self.config_path}, using defaults"
            )
            return self.DEFAULT_SETTINGS.copy()

        try:
            with open(self.config_path, "rb") as f:
                data = tomllib.load(f)
        except Exception as e:
            logger.error(f"Error reading pyproject.toml: {e}")
            return self.DEFAULT_SETTINGS.copy()

        # Get [tool.render-engine.pg] section
        pg_settings = (
            data.get("tool", {})
            .get("render-engine", {})
            .get("pg", {})
        )

        # Merge with defaults
        merged = self.DEFAULT_SETTINGS.copy()
        merged.update(pg_settings)

        logger.debug(f"Loaded PG settings: {merged}")
        return merged

    def get_read_sql(self, collection_name: str) -> str | None:
        """
        Get SQL query for reading a collection.

        Args:
            collection_name: Name of the collection

        Returns:
            SQL query string for this collection, or None if not configured
        """
        read_sql = self.settings.get("read_sql", {})

        if not isinstance(read_sql, dict):
            logger.warning(f"read_sql is not a dict: {type(read_sql)}")
            return None

        query = read_sql.get(collection_name)

        if isinstance(query, str):
            return query.strip() if query.strip() else None

        return None

    def get_insert_sql(self, collection_name: str) -> list[str]:
        """
        Get SQL insert statements for a collection.

        Args:
            collection_name: Name of the collection

        Returns:
            List of SQL queries to execute for this collection
        """
        insert_sql = self.settings.get("insert_sql", {})

        if not isinstance(insert_sql, dict):
            logger.warning(f"insert_sql is not a dict: {type(insert_sql)}")
            return []

        queries = insert_sql.get(collection_name, "")

        if isinstance(queries, str):
            # Split by semicolon and filter empty queries
            return [q.strip() for q in queries.split(";") if q.strip()]

        if isinstance(queries, list):
            return queries

        return []

    def __repr__(self) -> str:
        return f"PGSettings(config_path={self.config_path}, settings={self.settings})"
