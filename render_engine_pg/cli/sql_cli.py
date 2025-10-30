#!/usr/bin/env python3
"""
SQL Query Generator CLI for render-engine PostgreSQL Parser

Analyzes .sql files for render-engine objects (pages, collections) and generates
insertion queries based on relationships.
"""

import sys
from pathlib import Path
from typing import Optional

import click
import json

from .sql_parser import SQLParser
from .relationship_analyzer import RelationshipAnalyzer
from .query_generator import InsertionQueryGenerator


@click.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="Output file path (default: print to stdout)",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Show detailed analysis output",
)
@click.option(
    "--objects",
    type=click.Choice(["pages", "collections", "attributes", "junctions"], case_sensitive=False),
    multiple=True,
    default=["pages", "collections", "attributes", "junctions"],
    help="Which object types to process (default: all)",
)
@click.option(
    "--format",
    type=click.Choice(["sql", "json"]),
    default="sql",
    help="Output format (default: sql)",
)
def main(
    input_file: Path,
    output: Optional[Path],
    verbose: bool,
    objects: tuple,
    format: str,
):
    """Generate SQL insertion queries for render-engine objects from a .sql file."""
    try:
        # Validate file extension
        if input_file.suffix != ".sql":
            click.secho(
                "Warning: File does not have .sql extension",
                fg="yellow",
            )

        # Read input file
        if verbose:
            click.echo("Parsing SQL file...", err=True)

        sql_content = input_file.read_text()

        # Parse SQL
        sql_parser = SQLParser()
        parsed_objects = sql_parser.parse(sql_content)

        if verbose:
            click.echo(f"Found {len(parsed_objects)} objects", err=True)
            for obj in parsed_objects:
                click.echo(f"  - {obj['type']}: {obj['name']}", err=True)

        # Filter by object types
        # Map plural CLI options to singular object types
        object_type_map = {
            "pages": "page",
            "collections": "collection",
            "attributes": "attribute",
            "junctions": "junction",
        }
        target_types = set()
        for obj_type in objects:
            if obj_type.lower() in object_type_map:
                target_types.add(object_type_map[obj_type.lower()])
            else:
                target_types.add(obj_type.lower())

        # If no valid types specified, include all
        if not target_types:
            target_types = {"page", "collection", "attribute", "junction"}

        filtered_objects = [
            obj
            for obj in parsed_objects
            if obj["type"].lower() in target_types
        ]

        # Analyze relationships
        if verbose:
            click.echo("Analyzing relationships...", err=True)

        analyzer = RelationshipAnalyzer()
        relationships = analyzer.analyze(filtered_objects)

        if verbose:
            click.echo(
                f"Found {len(relationships)} relationships",
                err=True,
            )

        # Generate queries
        if verbose:
            click.echo("Generating insertion queries...", err=True)

        generator = InsertionQueryGenerator()
        queries = generator.generate(filtered_objects, relationships)

        # Format output
        if format == "sql":
            output_content = "\n\n".join(queries)
        else:  # json
            output_content = json.dumps(
                {
                    "objects": filtered_objects,
                    "relationships": relationships,
                    "queries": queries,
                },
                indent=2,
            )

        # Write output
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(output_content)
            if verbose:
                click.echo(f"Output written to {output}", err=True)
        else:
            click.echo(output_content)

        if verbose:
            click.echo("Done!", err=True)

    except Exception as e:
        click.secho(f"Error: {e}", fg="red", err=True)
        if verbose:
            import traceback

            traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
