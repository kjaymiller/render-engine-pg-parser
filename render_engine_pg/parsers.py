from psycopg.rows import dict_row
from render_engine_parser import BasePageParser
from render_engine_pg import PostgresQuery


class PGPageParser(BasePageParser):
    """Parser for individual Page objects querying the database"""

    @staticmethod
    def parse_content_path(content_path: PostgresQuery) -> tuple:
        """
        content_path is a PostgresQuery NamedTuple with:
        - connection: Connection object
        - query: SQL query string

        Returns:
        - Single result: attrs are the row columns as page attributes
        - Multiple results: attrs include keys with lists, page.data has all rows
        """
        with content_path.connection.cursor(row_factory=dict_row) as cur:
            cur.execute(content_path.query)
            rows = cur.fetchall()

        if not rows:
            return {}, None

        if len(rows) == 1:
            # Single result: columns become page attributes
            attrs = dict(rows[0])
            return attrs, None

        else:
            # Multiple results: raw data + pre-collected column lists
            attrs = {"data": rows}

            if rows:
                for key in rows[0].keys():
                    attrs[key] = [row[key] for row in rows]

            return attrs, None
