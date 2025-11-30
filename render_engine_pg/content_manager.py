from pathlib import Path
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
                page._raw_content = page.content
                page.content = self.collection.Parser.parse(page.content)
                self._pages.append(page)
        yield from self._pages

    def create_entry(
        self,
        filepath: Optional[Path] = None,
        editor: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        content: Optional[str] = None,
        table: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """
        Create a new database entry.

        For PostgreSQL-based collections, this inserts content directly into the database
        rather than writing to a file. The method uses the collection's parser to handle
        pre-configured INSERT statements and main content insertion.

        Args:
            filepath: Not used for PostgreSQL collections (kept for API compatibility)
            editor: Not used for PostgreSQL collections (kept for API compatibility)
            metadata: Dictionary of metadata/frontmatter attributes to include
            content: Markdown content to insert
            table: Database table name (defaults to collection name if not provided)
            **kwargs: Additional arguments passed to parser's create_entry

        Returns:
            Success message with the SQL query that was executed

        Example:
            content_manager.create_entry(
                content="---\\ntitle: My Post\\n---\\n# Hello World",
                metadata={"author": "John"},
                table="posts"
            )
        """
        # Prepare metadata dict
        if metadata is None:
            metadata = {}

        # Get connection from postgres_query
        connection = self.postgres_query.connection

        # Determine collection_name (use from postgres_query or collection class name)
        collection_name = (
            self.postgres_query.collection_name
            or getattr(self.collection, "collection_name", None)
            or self.collection.__class__.__name__.lower()
        )

        # Determine table name (use provided table or collection_name)
        if table is None:
            table = collection_name

        # Call parser's create_entry to handle database insertion
        result = self.collection.Parser.create_entry(
            content=content or "",
            connection=connection,
            table=table,
            collection_name=collection_name,
            **metadata,
            **kwargs,
        )

        return f"New entry created in table '{table}': {result}"

    def __iter__(self):
        yield from self.pages
