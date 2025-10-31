"""
SQL Parser for extracting render-engine objects (pages and collections)
"""

import re
from dataclasses import dataclass, asdict
from typing import List, Dict, Any


@dataclass
class SQLObject:
    """Represents a render-engine SQL object"""

    name: str
    type: str  # 'page' or 'collection'
    table: str
    columns: List[str]
    attributes: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SQLParser:
    """Parses SQL files to extract render-engine page and collection definitions"""

    def __init__(self, ignore_pk: bool = False, ignore_timestamps: bool = False):
        """
        Initialize the SQL parser.

        Args:
            ignore_pk: If True, automatically ignore PRIMARY KEY columns
            ignore_timestamps: If True, automatically ignore TIMESTAMP columns
        """
        self.ignore_pk = ignore_pk
        self.ignore_timestamps = ignore_timestamps

    # Pattern for page definitions
    # Syntax: -- @page [parent_name]
    PAGE_PATTERN = re.compile(
        r"--\s*@page(?:\s+['\"]?(\w+)['\"]?)?\s*\n\s*CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s*\((.*?)\);",
        re.IGNORECASE | re.DOTALL,
    )

    # Pattern for collection definitions (collection name and parent are optional)
    # Syntax: -- @collection [parent_name]
    COLLECTION_PATTERN = re.compile(
        r"--\s*@collection(?:\s+['\"]?(\w+)['\"]?)?\s*\n\s*CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s*\((.*?)\);",
        re.IGNORECASE | re.DOTALL,
    )

    # Pattern for junction/relationship table definitions
    # Syntax: -- @junction [parent_name]
    JUNCTION_PATTERN = re.compile(
        r"--\s*@junction(?:\s+['\"]?(\w+)['\"]?)?\s*\n\s*CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s*\((.*?)\);",
        re.IGNORECASE | re.DOTALL,
    )

    # Pattern for attribute table definitions
    # Syntax: -- @attribute [parent_name]
    ATTRIBUTE_PATTERN = re.compile(
        r"--\s*@attribute(?:\s+['\"]?(\w+)['\"]?)?\s*\n\s*CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s*\((.*?)\);",
        re.IGNORECASE | re.DOTALL,
    )

    # Pattern for all CREATE TABLE statements
    ALL_TABLES_PATTERN = re.compile(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s*\((.*?)\);",
        re.IGNORECASE | re.DOTALL,
    )

    # Pattern for column definitions
    COLUMN_PATTERN = re.compile(r"(\w+)\s+([^,\)]+?)(?:,|$)", re.IGNORECASE)

    # Pattern for comments
    COMMENT_PATTERN = re.compile(r"--\s*@(\w+)\s*(.+?)(?:\n|$)")

    def parse(self, sql_content: str) -> List[Dict[str, Any]]:
        """
        Parse SQL content and extract render-engine objects.

        Supported annotation syntax:
            -- @page [parent_collection]
            -- @collection [parent_collection]
            -- @attribute [parent_collection]
            -- @junction [parent_collection]

        Parent collection can be unquoted or quoted (e.g., 'Blog' or Blog).

        Args:
            sql_content: The SQL file content as a string

        Returns:
            List of parsed objects with structure:
            {
                'name': str,
                'type': 'page', 'collection', 'attribute', or 'junction',
                'table': str,
                'columns': [str],
                'attributes': {
                    'parent_collection': str (optional),  # Parent collection/page name
                    'collection_name': str (for collections)
                }
            }
        """
        objects = []

        # Find all pages
        for match in self.PAGE_PATTERN.finditer(sql_content):
            parent_name = match.group(1)
            table_name = match.group(2)
            columns_def = match.group(3)
            columns, ignored_columns, aggregate_columns = self._parse_columns(columns_def)

            obj = {
                "name": table_name,
                "type": "page",
                "table": table_name,
                "columns": columns,
                "attributes": {},
            }
            if ignored_columns:
                obj["attributes"]["ignored_columns"] = ignored_columns
            if aggregate_columns:
                obj["attributes"]["aggregate_columns"] = aggregate_columns
            if parent_name:
                obj["attributes"]["parent_collection"] = parent_name
            objects.append(obj)

        # Find all collections
        for match in self.COLLECTION_PATTERN.finditer(sql_content):
            parent_name = match.group(1)  # Optional parent collection name
            table_name = match.group(2)
            columns_def = match.group(3)
            columns, ignored_columns, aggregate_columns = self._parse_columns(columns_def)

            # Collection name defaults to table name
            collection_name = table_name

            obj = {
                "name": collection_name,
                "type": "collection",
                "table": table_name,
                "columns": columns,
                "attributes": {"collection_name": collection_name},
            }
            if ignored_columns:
                obj["attributes"]["ignored_columns"] = ignored_columns
            if aggregate_columns:
                obj["attributes"]["aggregate_columns"] = aggregate_columns
            if parent_name:
                obj["attributes"]["parent_collection"] = parent_name
            objects.append(obj)

        # Find all junction tables
        for match in self.JUNCTION_PATTERN.finditer(sql_content):
            parent_name = match.group(1)
            table_name = match.group(2)
            columns_def = match.group(3)
            columns, ignored_columns, aggregate_columns = self._parse_columns(columns_def)

            obj = {
                "name": table_name,
                "type": "junction",
                "table": table_name,
                "columns": columns,
                "attributes": {},
            }
            if ignored_columns:
                obj["attributes"]["ignored_columns"] = ignored_columns
            if aggregate_columns:
                obj["attributes"]["aggregate_columns"] = aggregate_columns
            if parent_name:
                obj["attributes"]["parent_collection"] = parent_name
            objects.append(obj)

        # Find all attribute tables
        for match in self.ATTRIBUTE_PATTERN.finditer(sql_content):
            parent_name = match.group(1)
            table_name = match.group(2)
            columns_def = match.group(3)
            columns, ignored_columns, aggregate_columns = self._parse_columns(columns_def)

            obj = {
                "name": table_name,
                "type": "attribute",
                "table": table_name,
                "columns": columns,
                "attributes": {},
            }
            if ignored_columns:
                obj["attributes"]["ignored_columns"] = ignored_columns
            if aggregate_columns:
                obj["attributes"]["aggregate_columns"] = aggregate_columns
            if parent_name:
                obj["attributes"]["parent_collection"] = parent_name
            objects.append(obj)

        # Find unmarked tables and add them as untyped/inferred tables
        # Keep track of tables we've already processed
        processed_tables = {obj["table"] for obj in objects}

        for match in self.ALL_TABLES_PATTERN.finditer(sql_content):
            table_name = match.group(1)
            columns_def = match.group(2)

            # Skip if we already parsed this table
            if table_name in processed_tables:
                continue

            columns, ignored_columns, aggregate_columns = self._parse_columns(columns_def)

            # Add as unmarked table (will be inferred from usage in junctions)
            obj = {
                "name": table_name,
                "type": "unmarked",
                "table": table_name,
                "columns": columns,
                "attributes": {},
            }
            if ignored_columns:
                obj["attributes"]["ignored_columns"] = ignored_columns
            if aggregate_columns:
                obj["attributes"]["aggregate_columns"] = aggregate_columns
            objects.append(obj)

        return objects

    def _parse_columns(self, columns_def: str) -> tuple:
        """
        Extract column names from column definitions.

        Returns:
            Tuple of (columns, ignored_columns, aggregate_columns) where:
            - columns: List of all column names
            - ignored_columns: List of column names marked with -- ignore comment or by flags
            - aggregate_columns: List of column names marked with @aggregate comment
        """
        columns = []
        ignored_columns = []
        aggregate_columns = []

        # Split by lines to parse each column definition
        # This handles -- ignore and @aggregate comments that appear on the same line as the column
        lines = columns_def.split('\n')

        for line in lines:
            line_stripped = line.strip()

            # Skip empty lines and comment-only lines
            if not line_stripped or line_stripped.startswith('--'):
                continue

            # Remove trailing comma for processing
            line_for_parsing = line_stripped.rstrip(',').strip()

            # Check for annotations in the comment
            has_ignore = bool(re.search(r'--\s*ignore', line_stripped, re.IGNORECASE))
            has_aggregate = bool(re.search(r'--\s*@aggregate', line_stripped, re.IGNORECASE))

            # Remove the comment part for parsing
            col_def_no_comment = line_for_parsing.split('--')[0] if '--' in line_for_parsing else line_for_parsing

            # Remove parentheses and extra whitespace
            col_def_no_comment = col_def_no_comment.strip().strip('()')

            # Extract the first word as the column name (ignore constraints)
            words = col_def_no_comment.split()
            if words:
                col_name = words[0].strip()
                # Skip constraint keywords and empty names
                if col_name and col_name.upper() not in ('PRIMARY', 'FOREIGN', 'UNIQUE', 'CHECK', 'CONSTRAINT'):
                    # Avoid duplicate column names
                    if col_name not in columns:
                        columns.append(col_name)

                        # Check if column should be ignored
                        should_ignore = has_ignore

                        # Check for PRIMARY KEY
                        if self.ignore_pk and 'PRIMARY KEY' in line_stripped.upper():
                            should_ignore = True

                        # Check for TIMESTAMP
                        if self.ignore_timestamps and 'TIMESTAMP' in line_stripped.upper():
                            should_ignore = True

                        if should_ignore:
                            ignored_columns.append(col_name)

                        # Check for @aggregate annotation
                        if has_aggregate:
                            aggregate_columns.append(col_name)

        return columns, ignored_columns, aggregate_columns
