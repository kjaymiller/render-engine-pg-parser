"""
Main CLI group for render-engine PostgreSQL parser.

Provides multiple commands:
- sql: Generate TOML configuration from SQL schema files
- populate: Populate database from markdown files
"""

import click

from render_engine_pg.cli.sql_cli import main as sql_command
from render_engine_pg.cli.populate_cli import main as populate_command


@click.group()
def cli():
    """
    Render-engine PostgreSQL parser CLI.

    Utilities for generating database configurations and populating
    PostgreSQL databases from markdown files.
    """
    pass


# Register commands
cli.add_command(sql_command, name="sql")
cli.add_command(populate_command, name="populate")


if __name__ == "__main__":
    cli()
