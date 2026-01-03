import frontmatter
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Generator, Iterable, Optional, Any
from psycopg import sql
from psycopg.rows import class_row
from render_engine.content_managers import ContentManager
from render_engine_markdown import MarkdownPageParser
from render_engine_pg.connection import PostgresQuery
from render_engine_pg.page import PGPage
from render_engine_pg.re_settings_parser import PGSettings

logger = logging.getLogger(__name__)


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
                row.Parser = MarkdownPageParser
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
                # Don't manually parse content here - let render-engine's Page._content property
                # handle parsing via Parser.parse() when the content is accessed for rendering.
                # This prevents double-parsing (once here, once in Page._content property).
                self._pages.append(page)
        yield from self._pages

    def __iter__(self):
        yield from self.pages

    @staticmethod
    def _convert_template_to_parameterized(
        template: str,
        data: dict[str, Any],
    ) -> tuple[str, list[Any]]:
        """
        Convert a {placeholder} template to a parameterized query with %s placeholders.
        """
        import string

        formatter = string.Formatter()
        field_names = [
            field_name
            for _, field_name, _, _ in formatter.parse(template)
            if field_name
        ]

        # Check if all required fields are available
        for field in field_names:
            if field not in data:
                raise KeyError(field)

        # Build parameterized query by replacing {key} with %s
        # and collecting values in order of appearance
        param_query = template
        values = []
        for _, field_name, _, _ in formatter.parse(template):
            if field_name:
                param_query = param_query.replace(f"{{{field_name}}}", "%s", 1)
                values.append(data[field_name])

        return param_query, values

    @staticmethod
    def _execute_templates_in_order(
        cursor: Any,
        connection: Any,
        templates: list[str],
        frontmatter_data: dict[str, Any],
    ) -> list[str]:
        """
        Execute template queries in proper order with error handling.
        """
        pre_main = []  # Simple INSERTs
        post_main = []  # Junction INSERTs with subqueries

        # Separate templates by type
        for tmpl in templates:
            # Junction tables have INSERT ... SELECT subqueries
            if "SELECT" in tmpl.upper() and "FROM" in tmpl.upper():
                post_main.append(tmpl)
            else:
                pre_main.append(tmpl)

        # Execute pre-main templates
        PostgresContentManager._execute_template_list(
            cursor, pre_main, frontmatter_data, "pre-main"
        )

        # Return post-main templates to execute after main INSERT
        return post_main

    @staticmethod
    def _execute_template_list(
        cursor: Any,
        templates: list[str],
        frontmatter_data: dict[str, Any],
        phase: str = "template",
    ) -> None:
        """
        Execute a list of templates with savepoint-based error handling.
        """
        for i, insert_sql_template in enumerate(templates):
            # Create a savepoint for each template so we can rollback individual failures
            phase_safe = phase.replace("-", "_")
            savepoint_name = f"sp_{phase_safe}_{i}"
            cursor.execute(f"SAVEPOINT {savepoint_name}")

            try:
                # Convert template to parameterized query for safe value substitution
                param_query, values = (
                    PostgresContentManager._convert_template_to_parameterized(
                        insert_sql_template, frontmatter_data
                    )
                )
                logger.debug(
                    f"Executing {phase} template: {param_query} with values {values}"
                )
                cursor.execute(param_query, values)
            except KeyError as e:
                # Rollback this specific query
                cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")

                # Template has missing field - check if we can iterate through a list
                missing_field = e.args[0]

                # Create another savepoint for list iteration attempt
                cursor.execute(f"SAVEPOINT {savepoint_name}_list")
                try:
                    list_field_used = (
                        PostgresContentManager._try_execute_with_list_iteration(
                            cursor, insert_sql_template, frontmatter_data, missing_field
                        )
                    )
                    if list_field_used:
                        # List iteration succeeded, release the savepoint
                        cursor.execute(f"RELEASE SAVEPOINT {savepoint_name}_list")
                    else:
                        # No list available for iteration - skip this template
                        cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}_list")
                        logger.debug(
                            f"Skipping {phase} template due to missing field '{missing_field}': {insert_sql_template}"
                        )
                except Exception:
                    # List iteration also failed
                    cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}_list")
                    logger.debug(
                        f"Skipping {phase} template due to missing field '{missing_field}': {insert_sql_template}"
                    )
            except Exception as db_error:
                # Handle database errors like unique constraint violations
                cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
                logger.warning(
                    f"Skipping {phase} template due to database error: {db_error}\n"
                    f"Template: {insert_sql_template}"
                )
            else:
                # Query executed successfully, release the savepoint
                cursor.execute(f"RELEASE SAVEPOINT {savepoint_name}")

    @staticmethod
    def _try_execute_with_list_iteration(
        cursor: Any,
        template: str,
        frontmatter_data: dict[str, Any],
        missing_field: str,
    ) -> bool:
        """
        Attempt to execute a template by iterating through a list field.
        """
        # Find all list fields in frontmatter
        list_fields = {k: v for k, v in frontmatter_data.items() if isinstance(v, list)}

        if not list_fields:
            return False

        # Try each list field to see if it can satisfy the missing field
        for list_field_name, list_items in list_fields.items():
            if not list_items:
                continue

            for item in list_items:
                test_data = {**frontmatter_data, missing_field: item}

                try:
                    param_query, values = (
                        PostgresContentManager._convert_template_to_parameterized(
                            template, test_data
                        )
                    )

                    logger.debug(
                        f"Executing insert_sql template with list iteration (field='{list_field_name}', item='{item}'): {param_query} with values {values}"
                    )
                    cursor.execute(param_query, values)
                except KeyError:
                    continue

            return True

        return False

    @staticmethod
    def create_entry_static(
        content: str = "Hello World",
        connection: Optional[Any] = None,
        table: Optional[str] = None,
        collection_name: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """
        Static implementation of create_entry for use by CLI or instance method.
        """
        # Parse markdown with frontmatter first to get context for template substitution
        post = frontmatter.loads(content)

        # Add any additional kwargs to the frontmatter
        for key, val in kwargs.items():
            if key not in ("connection", "table", "collection_name"):
                post[key] = val

        # Combine frontmatter and content
        frontmatter_data = post.metadata
        markdown_content = post.content

        # Add the markdown content to the data if not already present
        if "content" not in frontmatter_data:
            frontmatter_data["content"] = markdown_content

        if "slug" not in frontmatter_data:
            pass

        post_main_templates: list[str] = []

        if collection_name:
            settings = PGSettings()
            insert_sql_list = settings.get_insert_sql(collection_name)

            if insert_sql_list and connection:
                if "created_at" not in frontmatter_data:
                    frontmatter_data["created_at"] = datetime.now().isoformat()

                if "updated_at" not in frontmatter_data:
                    frontmatter_data["updated_at"] = datetime.now().isoformat()

                original_autocommit = connection.autocommit
                try:
                    connection.autocommit = False

                    with connection.cursor() as cur:
                        post_main_templates = (
                            PostgresContentManager._execute_templates_in_order(
                                cur, connection, insert_sql_list, frontmatter_data
                            )
                        )

                    connection.commit()
                except Exception:
                    try:
                        connection.rollback()
                    except Exception:
                        pass
                    raise
                finally:
                    try:
                        connection.autocommit = original_autocommit
                    except Exception:
                        try:
                            connection.rollback()
                            connection.autocommit = original_autocommit
                        except Exception:
                            pass

        # Extract allowed columns from read_sql configuration
        allowed_columns = None
        if collection_name:
            settings = PGSettings()
            read_sql = settings.get_read_sql(collection_name)
            if read_sql and isinstance(read_sql, str):
                select_match = re.search(
                    r"SELECT\s+(?:DISTINCT\s+ON\s+\([^)]+\)\s+)?(.+?)\s+FROM",
                    read_sql,
                    re.IGNORECASE,
                )
                if select_match:
                    select_clause = select_match.group(1)
                    col_names = []
                    for col in select_clause.split(","):
                        col = col.strip()
                        if " as " in col.lower():
                            col = col.split(" as ")[-1].strip()
                        if "." in col:
                            col = col.split(".")[-1].strip()
                        col_names.append(col)
                    allowed_columns = set(col_names)

        if allowed_columns:
            filtered_data = {
                k: v for k, v in frontmatter_data.items() if k in allowed_columns
            }
        else:
            filtered_data = frontmatter_data

        columns = list(filtered_data.keys())
        values = list(filtered_data.values())

        if table is None:
            # Fallback if no table provided (should usually be provided)
            # This is a bit risky if called statically without context
            if collection_name:
                table = collection_name
            else:
                raise ValueError("Table name is required for insertion.")

        insert_query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            sql.Identifier(str(table.casefold())),
            sql.SQL(", ").join(map(sql.Identifier, columns)),
            sql.SQL(", ").join(sql.Placeholder() * len(values)),
        )

        if connection:
            original_autocommit = connection.autocommit
            try:
                connection.autocommit = False

                with connection.cursor() as cur:
                    cur.execute(insert_query, values)

                    if post_main_templates:
                        PostgresContentManager._execute_template_list(
                            cur, post_main_templates, frontmatter_data, "post-main"
                        )

                connection.commit()
            except Exception:
                try:
                    connection.rollback()
                except Exception:
                    pass
                raise
            finally:
                try:
                    connection.autocommit = original_autocommit
                except Exception:
                    try:
                        connection.rollback()
                        connection.autocommit = original_autocommit
                    except Exception:
                        pass

            result = insert_query.as_string(connection)
            return str(result)

        return str(insert_query)

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
        Instance method that calls the static implementation.
        """
        # Prepare metadata dict
        if metadata is None:
            metadata = {}

        # Get connection from postgres_query
        connection = self.postgres_query.connection

        # Determine collection_name
        collection_name = (
            self.postgres_query.collection_name
            or getattr(self.collection, "collection_name", None)
            or self.collection.__class__.__name__.lower()
        )

        # Determine table name
        if table is None:
            table = collection_name

        return PostgresContentManager.create_entry_static(
            content=content or "",
            connection=connection,
            table=table,
            collection_name=collection_name,
            **metadata,
            **kwargs,
        )

    @staticmethod
    def populate_from_file(
        file_path: str | Path,
        connection: Any,
        collection_name: str,
        table: str,
        extract_slug_from_filename: bool = True,
        **extra_metadata: Any,
    ) -> str:
        """
        Read a markdown file, extract metadata, and populate database.
        """
        file_path = Path(file_path)
        content = file_path.read_text()
        post = frontmatter.loads(content)

        if extract_slug_from_filename and "slug" not in post.metadata:
            slug = file_path.stem
            slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", slug)
            slug = re.sub(r"^\d{4}-\d{2}-", "", slug)
            post.metadata["slug"] = slug

        for key, value in extra_metadata.items():
            if key not in post.metadata:
                post.metadata[key] = value

        updated_content = frontmatter.dumps(post)

        return PostgresContentManager.create_entry_static(
            content=updated_content,
            connection=connection,
            collection_name=collection_name,
            table=table,
        )

    @staticmethod
    def populate_from_directory(
        directory: str | Path,
        connection: Any,
        collection_name: str,
        table: str,
        pattern: str = "*.md",
        extract_slug_from_filename: bool = True,
        **shared_metadata: Any,
    ) -> list[str]:
        """
        Populate database from all markdown files in a directory.
        """
        directory = Path(directory)
        results = []

        for file_path in sorted(directory.glob(pattern)):
            if file_path.is_file():
                result = PostgresContentManager.populate_from_file(
                    file_path=file_path,
                    connection=connection,
                    collection_name=collection_name,
                    table=table,
                    extract_slug_from_filename=extract_slug_from_filename,
                    **shared_metadata,
                )
                results.append(result)

        return results
