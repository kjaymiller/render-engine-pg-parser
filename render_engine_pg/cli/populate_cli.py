"""
CLI command for populating PostgreSQL database from markdown files.

This command reads markdown files with YAML frontmatter, extracts metadata,
and populates a PostgreSQL database using pre-configured insert_sql templates
from pyproject.toml.
"""

import os
import sys
import logging
from pathlib import Path

import click

from render_engine_pg.connection import get_db_connection
from render_engine_pg.parsers import PGFilePopulationParser
from .cli_common import handle_cli_error, create_option_verbose

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(name)s - %(levelname)s - %(message)s'
)


@click.command()
@click.argument("table_name")
@click.argument("content_path", type=click.Path(exists=True, path_type=Path))
@create_option_verbose()
def main(table_name: str, content_path: Path, verbose: bool) -> None:
    """
    Populate a PostgreSQL database table from markdown files.

    Reads markdown files from CONTENT_PATH, extracts YAML frontmatter metadata,
    derives slug from filename, and executes database inserts using pre-configured
    insert_sql templates from [tool.render-engine.pg] in pyproject.toml.

    TABLE_NAME: The database table name (e.g., blog, notes, microblog)
    CONTENT_PATH: Path to directory containing markdown files
    """
    try:
        # Get database connection from environment variable
        conn_string = os.environ.get("CONNECTION_STRING")
        if not conn_string:
            raise ValueError(
                "CONNECTION_STRING environment variable not set. "
                "Set it to a valid PostgreSQL connection string."
            )

        conn = get_db_connection(conn_string)

        if verbose:
            click.echo(f"Connecting to database...", err=True)
            click.echo(f"Parsing markdown files from {content_path}...", err=True)

        # Load settings to show what will be executed
        from render_engine_pg.re_settings_parser import PGSettings
        settings = PGSettings()
        insert_sql = settings.get_insert_sql(table_name)
        read_sql = settings.get_read_sql(table_name)

        if verbose:
            if insert_sql:
                click.echo(f"Found {len(insert_sql)} insert_sql templates for '{table_name}'", err=True)
                for i, template in enumerate(insert_sql, 1):
                    click.echo(f"  Template {i}: {template[:80]}...", err=True)
            else:
                click.echo(f"⚠ No insert_sql templates found for '{table_name}'", err=True)

            if read_sql:
                click.echo(f"Found read_sql for '{table_name}'", err=True)
            else:
                click.echo(f"⚠ No read_sql found for '{table_name}'", err=True)

        # Find all markdown files
        md_files = sorted(list(content_path.glob("*.md")))
        click.echo(f"Found {len(md_files)} markdown files")

        if not md_files:
            click.echo("No markdown files found. Exiting.")
            return

        if verbose:
            click.echo(f"Inserting into table '{table_name}'...", err=True)

        # Populate database from each file
        inserted_count = 0
        failed_count = 0

        for md_file in md_files:
            try:
                if verbose:
                    click.echo(f"Processing {md_file.name}...", err=True)

                PGFilePopulationParser.populate_from_file(
                    file_path=md_file,
                    connection=conn,
                    collection_name=table_name,
                    table=table_name,
                    extract_slug_from_filename=True,
                )
                click.echo(f"✓ Inserted: {md_file.name}")
                inserted_count += 1
            except Exception as e:
                click.secho(f"✗ Failed: {md_file.name} - {e}", fg="red")
                failed_count += 1

                if verbose:
                    import traceback

                    traceback.print_exc(file=sys.stderr)

        # Summary
        click.echo(f"\nDatabase population complete!")
        click.echo(f"Inserted: {inserted_count}, Failed: {failed_count}")

        if failed_count > 0:
            sys.exit(1)

    except Exception as e:
        handle_cli_error(e, verbose=verbose)
        sys.exit(1)


if __name__ == "__main__":
    main()
