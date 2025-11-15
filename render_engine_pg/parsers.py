import frontmatter
import re
from datetime import datetime
from typing import Any
from psycopg.rows import dict_row
from render_engine_parser import BasePageParser
from render_engine_markdown import MarkdownPageParser
from render_engine_pg import PostgresQuery
from render_engine_pg.re_settings_parser import PGSettings
from psycopg import sql


class PGPageParser(BasePageParser):
    """Parser for individual Page objects querying the database

    Supports two modes of operation:
    1. Explicit query via PostgresQuery(connection=db, query="SELECT ...")
    2. Collection-based via PostgresQuery(connection=db, collection_name="blog")
       where the query is loaded from pyproject.toml settings
    """

    @staticmethod
    def parse_content_path(content_path: PostgresQuery) -> tuple:
        """
        Parse a single row or multiple rows from a database query.

        Args:
            content_path: PostgresQuery NamedTuple with:
                - connection: psycopg Connection object
                - query: Optional SQL query string (takes precedence)
                - collection_name: Optional name to load query from settings

        Returns:
            Tuple of (attrs dict, None):
            - Single result: attrs are the row columns as page attributes
            - Multiple results: attrs include keys with lists, page.data has all rows
            - Empty result: returns ({}, None)

        Raises:
            ValueError: If neither query nor valid collection_name provided
        """
        # Resolve query: explicit query takes precedence, fallback to settings
        query = content_path.query
        if not query and content_path.collection_name:
            settings = PGSettings()
            query = settings.get_read_sql(content_path.collection_name)

        if not query:
            collection_ref = (
                f"for collection '{content_path.collection_name}'"
                if content_path.collection_name
                else ""
            )
            raise ValueError(
                f"No query found {collection_ref}. "
                "Provide explicit query via PostgresQuery(query=...) "
                "or configure read_sql in pyproject.toml"
            )

        # Execute query
        with content_path.connection.cursor(row_factory=dict_row) as cur:
            cur.execute(query)
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
    def parse(content: str, extras: dict[str, Any] | None = None) -> str:
        """
        Parse markdown content with default extras enabled.
        Ensures fenced code blocks and other common markdown features are available.
        """
        # Default markdown extras to enable fenced code blocks and other features
        default_extras = ["fenced-code-blocks", "tables", "footnotes"]

        # If extras dict is provided, use its markdown_extras; otherwise use defaults
        if extras and "markdown_extras" in extras:
            markdown_extras = extras["markdown_extras"]
        else:
            markdown_extras = default_extras

        # Call parent class parse with the extras dict
        result = MarkdownPageParser.parse(
            content,
            extras={"markdown_extras": markdown_extras}
        )
        return str(result)

    @staticmethod
    def create_entry(*, content: str = "Hello World", **kwargs: Any) -> str:
        """
        Creates a new entry: inserts markdown content to database and executes template queries.

        Supports t-string-style templates in insert_sql with {variable} placeholders that are
        safely interpolated from frontmatter attributes using Python string formatting.
        Templates are defined in pyproject.toml and filled using .format(**data) for Python 3.14+ compatibility.

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
        connection: Any = kwargs.get("connection")
        collection_name: Any = kwargs.get("collection_name")

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

        # Generate slug from filename if not present (extract from content_path kwarg if provided)
        # This allows markdown files without explicit slug frontmatter to still be inserted
        if "slug" not in frontmatter_data:
            # Try to get filename from kwargs or generate a sensible default
            # Note: In populate_db context, slug would typically be filename-based
            # We leave this for populate_db/calling code to handle since we don't have filename here
            pass

        # Execute pre-configured insert SQL templates from settings if collection_name is provided
        # Templates have access to FULL frontmatter data (including tags, categories, etc.)
        if collection_name:
            settings = PGSettings()
            insert_sql_list = settings.get_insert_sql(collection_name)

            if insert_sql_list and connection:
                # Generate missing timestamp fields only
                # These are generally safe to auto-generate and don't break schema constraints
                if "created_at" not in frontmatter_data:
                    frontmatter_data["created_at"] = datetime.now().isoformat()

                if "updated_at" not in frontmatter_data:
                    frontmatter_data["updated_at"] = datetime.now().isoformat()

                with connection.cursor() as cur:
                    for insert_sql_template in insert_sql_list:
                        # Use safe string formatting with format_map to handle missing placeholders
                        # Skip templates with missing required fields - they will be handled elsewhere
                        try:
                            formatted_query = insert_sql_template.format_map(frontmatter_data)
                            cur.execute(formatted_query)
                        except KeyError as e:
                            # Skip this template if required fields are missing
                            # This allows markdown files with partial frontmatter to still work
                            missing_field = e.args[0]
                            # Silently skip - log if needed for debugging
                            pass
                connection.commit()

        # Extract allowed columns from read_sql configuration for the main content INSERT
        # Only filter columns for the final main table INSERT, not for templates
        allowed_columns = None
        if collection_name:
            settings = PGSettings()
            read_sql = settings.get_read_sql(collection_name)
            if read_sql and isinstance(read_sql, str):
                # Parse the SELECT statement to extract column names
                # Look for columns between SELECT and FROM
                select_match = re.search(r'SELECT\s+(?:DISTINCT\s+ON\s+\([^)]+\)\s+)?(.+?)\s+FROM', read_sql, re.IGNORECASE)
                if select_match:
                    select_clause = select_match.group(1)
                    # Split by comma and extract column names (handle table.column format)
                    col_names = []
                    for col in select_clause.split(','):
                        col = col.strip()
                        # Remove aliases and table prefixes
                        if ' as ' in col.lower():
                            col = col.split(' as ')[-1].strip()
                        if '.' in col:
                            col = col.split('.')[-1].strip()
                        col_names.append(col)
                    allowed_columns = set(col_names)

        # Build SQL INSERT query for main content entry
        # Only include columns that exist in the main table (from read_sql)
        if allowed_columns:
            # Only include columns that are in the allowed set
            filtered_data = {k: v for k, v in frontmatter_data.items() if k in allowed_columns}
        else:
            filtered_data = frontmatter_data

        columns = list(filtered_data.keys())
        values = list(filtered_data.values())

        # Use psycopg's sql module for safe parameterization
        table_name: Any = kwargs.get("table")
        insert_query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            sql.Identifier(str(table_name.casefold())),
            sql.SQL(", ").join(map(sql.Identifier, columns)),
            sql.SQL(", ").join(sql.Placeholder() * len(values)),
        )

        # Execute the query
        if connection:
            with connection.cursor() as cur:
                cur.execute(insert_query, values)
                connection.commit()

            result = insert_query.as_string(connection)
            return str(result)

        return str(insert_query)
