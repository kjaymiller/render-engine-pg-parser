import pdb
import frontmatter
import re
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
        Creates a new entry: inserts markdown content to database and executes template queries.

        Supports t-string-like templates in insert_sql for parameterized queries.
        Templates are defined in pyproject.toml with {variable} placeholders that are
        substituted from frontmatter attributes.

        Args:
            content: Markdown content with optional YAML frontmatter
            connection: PostgreSQL connection object
            table: Database table name to insert into
            collection_name: Optional collection name to load template inserts from settings
            **kwargs: Additional metadata to add to frontmatter

        Returns:
            The SQL INSERT query string that was executed

        Example:
            Template in pyproject.toml:
            [tool.render-engine.pg]
            insert_sql = { blog = "INSERT INTO post_stats (post_id) VALUES ({id})" }

            When creating a post:
            PGMarkdownCollectionParser.create_entry(
                content="---\nid: 42\ntitle: My Post\n---\n# Content",
                collection_name="blog",
                connection=db,
                table="posts"
            )

            Will:
            1. Execute: INSERT INTO post_stats (post_id) VALUES (42)
            2. Execute: INSERT INTO posts (id, title, content) VALUES (42, 'My Post', '# Content')
        """
        connection = kwargs.get("connection")
        collection_name = kwargs.get("collection_name")

        # Parse markdown with frontmatter first to get context for template substitution
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

        # Execute pre-configured insert SQL templates from settings if collection_name is provided
        if collection_name:
            settings = PGSettings()
            insert_sql_list = settings.get_insert_sql(collection_name)

            if insert_sql_list:
                with connection.cursor() as cur:
                    for insert_sql_template in insert_sql_list:
                        # Pass template with {variable} placeholders directly to psycopg
                        # psycopg handles safe parameterization
                        cur.execute(insert_sql_template, frontmatter_data)
                connection.commit()

        # Build SQL INSERT query for main content entry
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
