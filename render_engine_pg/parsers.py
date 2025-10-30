import pdb
import frontmatter
from psycopg.rows import dict_row
from render_engine_parser import BasePageParser
from render_engine_markdown import MarkdownPageParser
from render_engine_pg import PostgresQuery
from render_engine_pg.re_settings_parser import PGSettings
from psycopg import sql


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


class PGMarkdownCollectionParser(MarkdownPageParser):
    @staticmethod
    def create_entry(*, content: str = "Hello World", **kwargs) -> str:
        """
        Converts markdown frontmatter to a SQL INSERT query and executes it.

        Optionally executes pre-configured insert SQL statements from pyproject.toml
        if collection_name is provided in kwargs.

        Args:
            content: Markdown content with optional YAML frontmatter
            connection: PostgreSQL connection object
            table: Database table name to insert into
            collection_name: Optional collection name to load pre-configured inserts from settings
            **kwargs: Additional metadata to add to frontmatter

        Returns:
            The SQL INSERT query string that was executed
        """
        connection = kwargs.get("connection")
        collection_name = kwargs.get("collection_name")

        # Execute pre-configured insert SQL from settings if collection_name is provided
        if collection_name:
            settings = PGSettings()
            insert_sql_list = settings.get_insert_sql(collection_name)

            if insert_sql_list:
                with connection.cursor() as cur:
                    for insert_sql in insert_sql_list:
                        cur.execute(insert_sql)
                connection.commit()

        # Parse markdown with frontmatter
        post = frontmatter.loads(content)

        # Add any additional kwargs to the frontmatter (excluding connection, table, and collection_name)
        for key, val in kwargs.items():
            if key not in ("connection", "table", "collection_name"):
                post[key] = val

        # Combine frontmatter and content
        frontmatter_data = post.metadata
        markdown_content = post.content

        # Add the markdown content to the data if not already present
        if "content" not in frontmatter_data:
            frontmatter_data["content"] = markdown_content

        # Build SQL INSERT query
        columns = list(frontmatter_data.keys())
        values = list(frontmatter_data.values())

        # Use psycopg's sql module for safe parameterization
        insert_query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            sql.Identifier(str(kwargs.get("table").casefold())),
            sql.SQL(", ").join(map(sql.Identifier, columns)),
            sql.SQL(", ").join(sql.Placeholder() * len(values)),
        )

        # Execute the query
        with connection.cursor() as cur:
            cur.execute(insert_query, values)
            connection.commit()

        return insert_query.as_string(connection)
