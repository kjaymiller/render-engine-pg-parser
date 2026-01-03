from render_engine.page import BasePageParser
from render_engine_pg.connection import PostgresQuery
from render_engine_pg.re_settings_parser import PGSettings
from psycopg.rows import dict_row


class PGPageParser(BasePageParser):
    @staticmethod
    def parse_content(data):
        return data, data.get("content")

    @staticmethod
    def parse_content_path(content_path):
        if isinstance(content_path, PostgresQuery):
            # Resolve query if collection_name is provided but query is missing
            query = content_path.query
            if not query and content_path.collection_name:
                settings = PGSettings()
                query = settings.get_read_sql(content_path.collection_name)

            if not query:
                raise ValueError(
                    "PostgresQuery must have a query or valid collection_name"
                )

            with content_path.connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(query)
                return PGPageParser.parse_content(cursor.fetchone())

        return BasePageParser.parse_content_path(content_path)
