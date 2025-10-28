from psycopg.rows import class_row
from render_engine.content_managers import ContentManager
from typing import Generator, Iterable
from .connection import PostgresQuery
from .page import PGPage


class PostgresContentManager(ContentManager):
    """ContentManager for Collections - yields multiple Page objects"""

    def __init__(
        self,
        *,
        postgres_query: PostgresQuery,
        collection,
        **kwargs,
    ):
        self.postgres_query = postgres_query
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
            self._pages = list(self.execute_query())
        yield from self._pages
