"""
Common CLI utilities and shared functions for render-engine-pg commands.

Provides shared pipeline logic, error handling, and option decorators.
"""

import sys
from typing import List, Dict, Any

import click

from .relationship_analyzer import RelationshipAnalyzer
from .query_generator import InsertionQueryGenerator
from .read_query_generator import ReadQueryGenerator
from .toml_generator import TOMLConfigGenerator


def generate_toml_config(
    objects: List[Dict[str, Any]],
    relationships: List[Dict[str, Any]],
    verbose: bool = False,
) -> str:
    """
    Generate TOML configuration from parsed objects and relationships.

    This is the common pipeline used by all CLI modes:
    1. Analyze relationships
    2. Generate insertion queries
    3. Generate read queries
    4. Generate TOML configuration

    Args:
        objects: List of parsed objects (with ignored_columns already set by SQLParser)
        relationships: List of relationships from RelationshipAnalyzer
        verbose: If True, print debug information to stderr

    Returns:
        Generated TOML configuration as string
    """
    if verbose:
        click.echo("Analyzing relationships...", err=True)

    analyzer = RelationshipAnalyzer()
    relationships = analyzer.analyze(objects)

    if verbose:
        click.echo(f"Found {len(relationships)} relationships", err=True)

    # Generate insertion queries
    if verbose:
        click.echo("Generating insertion queries...", err=True)

    insert_generator = InsertionQueryGenerator()
    ordered_objects, insert_queries = insert_generator.generate(objects, relationships)

    # Generate read queries
    if verbose:
        click.echo("Generating read queries...", err=True)

    read_generator = ReadQueryGenerator()
    read_queries = read_generator.generate(objects, relationships)

    # Generate TOML configuration
    if verbose:
        click.echo("Generating TOML configuration...", err=True)

    toml_generator = TOMLConfigGenerator()
    output_content = toml_generator.generate(
        ordered_objects, insert_queries, read_queries, relationships
    )

    return output_content


def handle_cli_error(e: Exception, verbose: bool = False) -> None:
    """
    Handle and display CLI errors.

    Args:
        e: The exception that occurred
        verbose: If True, show full traceback
    """
    click.secho(f"Error: {e}", fg="red", err=True)
    if verbose:
        import traceback

        traceback.print_exc(file=sys.stderr)


def create_option_output():
    """Create --output/-o option decorator."""
    return click.option(
        "-o",
        "--output",
        type=click.Path(path_type=None),
        default=None,
        help="Output file path (default: print to stdout)",
    )


def create_option_verbose():
    """Create --verbose/-v option decorator."""
    return click.option(
        "-v",
        "--verbose",
        is_flag=True,
        help="Show detailed analysis output",
    )


def create_option_ignore_pk():
    """Create --ignore-pk option decorator."""
    return click.option(
        "--ignore-pk",
        is_flag=True,
        help="Automatically ignore PRIMARY KEY columns in INSERT statements",
    )


def create_option_ignore_timestamps():
    """Create --ignore-timestamps option decorator."""
    return click.option(
        "--ignore-timestamps",
        is_flag=True,
        help="Automatically ignore TIMESTAMP columns in INSERT statements",
    )


def create_option_interactive():
    """Create --interactive option decorator."""
    return click.option(
        "--interactive",
        is_flag=True,
        help="Use interactive mode to manually classify unmarked tables",
    )
