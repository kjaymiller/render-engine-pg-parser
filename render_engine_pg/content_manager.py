from psycopg.rows import class_row
from render_engine.content_managers import ContentManager
from typing import Generator, Iterable, Optional
from .connection import PostgresQuery
from .page import PGPage


class PostgresContentManager(ContentManager):
    """ContentManager for Collections - yields multiple Page objects"""

    def __init__(
        self,
        *,
        postgres_query: Optional[PostgresQuery] = None,
        collection,
        connection: Optional[object] = None,
        collection_name: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize content manager.

        Args:
            postgres_query: PostgresQuery with connection and SQL query (optional)
            collection: The collection object
            connection: Database connection (used with collection_name)
            collection_name: Collection name to look up read_sql from settings
        """
        # If postgres_query is provided, use it directly
        if postgres_query:
            self.postgres_query = postgres_query
        # If collection_name is provided, look up read_sql from settings
        elif collection_name and connection:
            from .re_settings_parser import PGSettings
            settings = PGSettings()
            query = settings.get_read_sql(collection_name)
            if query:
                self.postgres_query = PostgresQuery(connection=connection, query=query)
            else:
                raise ValueError(f"No read_sql found for collection '{collection_name}' in settings")
        else:
            raise ValueError("Either 'postgres_query' or both 'connection' and 'collection_name' must be provided")

        self._pages = None
        self.collection = collection

    def execute_query(self) -> Generator[PGPage, None, None]:
        """Execute query and yield Page objects (one per row)"""
        with self.postgres_query.connection.cursor(
            row_factory=class_row(PGPage)
        ) as cur:
            cur.execute(self.postgres_query.query)
            for row in cur:
                row.parser_extras = getattr(self.collection, "parser_extras", {})
                row.routes = self.collection.routes
                row.template = getattr(self.collection, "template", None)
                row.collection = self.collection.to_dict()
                yield row

    @property
    def pages(self) -> Iterable:
        if self._pages is None:
            self._pages = []
            for page in self.execute_query():
                page.content = self.collection.Parser.parse(page.content)
                self._pages.append(page)
        yield from self._pages

    def __iter__(self):
        yield from self.pages
