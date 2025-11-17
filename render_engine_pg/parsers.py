import frontmatter
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Any
from psycopg.rows import dict_row
from render_engine_parser import BasePageParser
from render_engine_markdown import MarkdownPageParser
from render_engine_pg import PostgresQuery
from render_engine_pg.re_settings_parser import PGSettings
from psycopg import sql

logger = logging.getLogger(__name__)


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
    def _try_execute_with_list_iteration(
        cursor: Any,
        template: str,
        frontmatter_data: dict[str, Any],
        missing_field: str,
    ) -> bool:
        """
        Attempt to execute a template by iterating through a list field.

        When a template references a missing field (e.g., {name}), this method:
        1. Searches for any list fields in frontmatter
        2. For each list field, checks if using its items for the missing field makes the template work
        3. If found, executes the template once for each item in the list

        Args:
            cursor: Database cursor to execute queries
            template: SQL template string with {placeholders}
            frontmatter_data: Dictionary of frontmatter data
            missing_field: The field name that's missing from frontmatter_data

        Returns:
            True if a list field was found and template was executed, False otherwise

        Example:
            frontmatter_data = {id: 1, tags: ['python', 'postgresql']}
            template = "INSERT INTO tags (name) VALUES ({name})"
            missing_field = "name"

            This method will:
            1. Find that "tags" is a list
            2. Execute template twice:
               - INSERT INTO tags (name) VALUES ('python')
               - INSERT INTO tags (name) VALUES ('postgresql')
        """
        # Find all list fields in frontmatter
        list_fields = {k: v for k, v in frontmatter_data.items() if isinstance(v, list)}

        if not list_fields:
            # No lists available for iteration
            return False

        # Try each list field to see if it can satisfy the missing field
        for list_field_name, list_items in list_fields.items():
            # Create test data with first item to see if template works
            if not list_items:
                # Empty list - skip
                continue

            # Create a mapping where the missing field uses the list field's name
            # For example: tags list -> use items as {name} values
            for item in list_items:
                # Create a copy of frontmatter data with the missing field filled from list item
                test_data = {**frontmatter_data, missing_field: item}

                try:
                    # Test if this mapping works
                    formatted_query = template.format_map(test_data)
                    logger.debug(
                        f"Executing insert_sql template with list iteration (field='{list_field_name}', item='{item}'): {formatted_query}"
                    )
                    cursor.execute(formatted_query)
                except KeyError:
                    # This list field doesn't help - try the next one
                    continue

            # If we got here, we successfully executed for all items in this list
            return True

        # No list field could satisfy the template
        return False

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
                        # Try to execute template with current frontmatter data
                        try:
                            formatted_query = insert_sql_template.format_map(frontmatter_data)
                            logger.debug(f"Executing insert_sql template: {formatted_query}")
                            cur.execute(formatted_query)
                        except KeyError as e:
                            # Template has missing field - check if we can iterate through a list
                            missing_field = e.args[0]
                            list_field_used = PGMarkdownCollectionParser._try_execute_with_list_iteration(
                                cur, insert_sql_template, frontmatter_data, missing_field
                            )

                            if not list_field_used:
                                # No list available for iteration - skip this template
                                logger.debug(
                                    f"Skipping insert_sql template due to missing field '{missing_field}': {insert_sql_template}"
                                )
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


class PGFilePopulationParser(PGMarkdownCollectionParser):
    """
    Internal parser for populating database from markdown files.

    Not exposed as public API. Used by CLI for batch file-based database population.
    Handles filepath-based metadata extraction (slug from filename) and calls
    create_entry() for database insertion.
    """

    @staticmethod
    def populate_from_file(
        file_path: str | Path,
        connection: Any,
        collection_name: str,
        table: str,
        extract_slug_from_filename: bool = True,
        **extra_metadata: Any
    ) -> str:
        """
        Read a markdown file, extract metadata, and populate database.

        Args:
            file_path: Path to markdown file
            connection: PostgreSQL connection object
            collection_name: Collection name (for loading insert_sql templates)
            table: Database table name for main INSERT
            extract_slug_from_filename: If True, derives slug from filename (stem)
            **extra_metadata: Additional metadata to merge with frontmatter

        Returns:
            SQL query string that was executed
        """
        file_path = Path(file_path)

        # Read file content
        content = file_path.read_text()

        # Parse frontmatter to get existing metadata
        post = frontmatter.loads(content)

        # Extract slug from filename if needed and not already in frontmatter
        if extract_slug_from_filename and "slug" not in post.metadata:
            # Use file stem (filename without extension) as slug
            slug = file_path.stem

            # Clean up common date prefixes (e.g., "2020-01-15-my-post" -> "my-post")
            # This pattern matches YYYY-MM-DD- or YYYY-MM- prefixes
            slug = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', slug)
            slug = re.sub(r'^\d{4}-\d{2}-', '', slug)

            post.metadata["slug"] = slug

        # Merge any additional metadata passed as kwargs
        for key, value in extra_metadata.items():
            if key not in post.metadata:
                post.metadata[key] = value

        # Reconstruct content with updated frontmatter
        updated_content = frontmatter.dumps(post)

        # Call parent's create_entry with enriched metadata
        return PGMarkdownCollectionParser.create_entry(
            content=updated_content,
            connection=connection,
            collection_name=collection_name,
            table=table
        )

    @staticmethod
    def populate_from_directory(
        directory: str | Path,
        connection: Any,
        collection_name: str,
        table: str,
        pattern: str = "*.md",
        extract_slug_from_filename: bool = True,
        **shared_metadata: Any
    ) -> list[str]:
        """
        Populate database from all markdown files in a directory.

        Args:
            directory: Path to directory containing markdown files
            connection: PostgreSQL connection object
            collection_name: Collection name (for loading insert_sql templates)
            table: Database table name
            pattern: Glob pattern for matching files (default: "*.md")
            extract_slug_from_filename: If True, derives slug from filename
            **shared_metadata: Metadata to apply to all files

        Returns:
            List of SQL query strings that were executed
        """
        directory = Path(directory)
        results = []

        for file_path in sorted(directory.glob(pattern)):
            if file_path.is_file():
                result = PGFilePopulationParser.populate_from_file(
                    file_path=file_path,
                    connection=connection,
                    collection_name=collection_name,
                    table=table,
                    extract_slug_from_filename=extract_slug_from_filename,
                    **shared_metadata
                )
                results.append(result)

        return results
