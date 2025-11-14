from pathlib import Path
import subprocess
from psycopg.rows import class_row
from render_engine.content_managers import ContentManager
from typing import Generator, Iterable, Optional, Any
from .connection import PostgresQuery
from .page import PGPage


class PostgresContentManager(ContentManager):
    """ContentManager for Collections - yields multiple Page objects"""

    def __init__(
        self,
        collection: Any,
        *,
        postgres_query: Optional[PostgresQuery] = None,
        connection: Optional[Any] = None,
        collection_name: Optional[str] = None,
        **kwargs: object,
    ) -> None:
        """
        Initialize content manager.

        Args:
            collection: The collection object
            postgres_query: PostgresQuery with connection and SQL query (optional)
            connection: Database connection (used with collection_name)
            collection_name: Collection name to look up read_sql from settings
                           (defaults to collection class name if not provided)
        """
        # If postgres_query is provided, use it directly
        if postgres_query:
            self.postgres_query = postgres_query
        # If connection is provided, look up read_sql from settings
        elif connection:
            from .re_settings_parser import PGSettings

            # Use provided collection_name or default to collection class name (lowercase)
            lookup_name = collection_name or collection.__class__.__name__.lower()

            settings = PGSettings()
            query = settings.get_read_sql(lookup_name)
            if query:
                self.postgres_query = PostgresQuery(connection=connection, query=query)
            else:
                raise ValueError(
                    f"No read_sql found for collection '{lookup_name}' in settings"
                )
        else:
            raise ValueError("Either 'postgres_query' or 'connection' must be provided")

        self._pages: list[PGPage] | None = None
        self.collection = collection

    def execute_query(self) -> Generator[PGPage, None, None]:
        """Execute query and yield Page objects (one per row)"""
        with self.postgres_query.connection.cursor(
            row_factory=class_row(PGPage)
        ) as cur:
            if self.postgres_query.query is not None:
                cur.execute(self.postgres_query.query)
            for row in cur:
                row.parser_extras = getattr(self.collection, "parser_extras", {})
                row.routes = self.collection.routes
                row.template = getattr(self.collection, "template", None)
                setattr(row, "collection", self.collection.to_dict())
                yield row

    @property
    def pages(self) -> Iterable:
        if self._pages is None:
            self._pages = []
            for page in self.execute_query():
                page.content = self.collection.Parser.parse(page.content)
                self._pages.append(page)
        yield from self._pages

    def create_entry(
        self,
        filepath: Optional[Path] = None,
        editor: Optional[str] = None,
        metadata: Optional[dict] = None,
        content: Optional[str] = None,
    ) -> str:
        """Create a new entry"""

        if not filepath:
            raise ValueError("filepath needs to be specified.")

        parsed_content = self.collection.Parser.create_entry(
            content=content, **metadata
        )
        filepath.write_text(parsed_content)
        if editor:
            subprocess.run([editor, filepath])
        return f"New entry created at {filepath} ."

    def __iter__(self):
        yield from self.pages
