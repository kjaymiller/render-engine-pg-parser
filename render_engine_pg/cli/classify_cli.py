#!/usr/bin/env python3
"""
Interactive SQL Schema Classifier for render-engine PostgreSQL Parser

Allows users to interactively classify unmarked tables as pages, collections,
attributes, or junctions, then generates TOML configuration automatically.
"""

import sys
from pathlib import Path
from typing import Optional

import click

from .sql_parser import SQLParser
from .interactive_classifier import InteractiveClassifier
from .relationship_analyzer import RelationshipAnalyzer
from .query_generator import InsertionQueryGenerator
from .read_query_generator import ReadQueryGenerator
from .toml_generator import TOMLConfigGenerator


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
    "--ignore-pk",
    is_flag=True,
    help="Automatically ignore PRIMARY KEY columns in INSERT statements",
)
@click.option(
    "--ignore-timestamps",
    is_flag=True,
    help="Automatically ignore TIMESTAMP columns in INSERT statements",
)
def main(
    input_file: Path,
    output: Optional[Path],
    verbose: bool,
    ignore_pk: bool,
    ignore_timestamps: bool,
) -> None:
    """
    Interactively classify SQL schema tables and generate TOML configuration.

    This command reads a SQL file, identifies unannotated tables, and guides you
    through classifying them as pages, collections, attributes, or junctions.
    It then generates INSERT and SELECT queries automatically.
    """
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

        # Parse SQL - this captures all tables (annotated + unmarked)
        sql_parser = SQLParser(
            ignore_pk=ignore_pk, ignore_timestamps=ignore_timestamps
        )
        parsed_objects = sql_parser.parse(sql_content)

        if verbose:
            click.echo(f"Found {len(parsed_objects)} objects", err=True)
            for obj in parsed_objects:
                click.echo(f"  - {obj['type']}: {obj['name']}", err=True)

        # Separate unmarked tables for interactive classification
        unmarked_count = sum(1 for obj in parsed_objects if obj["type"] == "unmarked")
        annotated_count = len(parsed_objects) - unmarked_count

        if verbose:
            click.echo(
                f"  ({annotated_count} annotated, {unmarked_count} unmarked)",
                err=True,
            )

        # Run interactive classifier
        if unmarked_count > 0:
            if verbose:
                click.echo("\nStarting interactive classification...", err=True)

            classifier = InteractiveClassifier(verbose=verbose)
            classified_objects, classified_count = classifier.classify_tables(
                parsed_objects, skip_annotated=True
            )

            if verbose:
                click.echo(
                    f"Classified {classified_count} tables",
                    err=True,
                )
        else:
            if verbose:
                click.echo("No unmarked tables to classify", err=True)
            classified_objects = parsed_objects
            classified_count = 0

        # Filter out unmarked tables that weren't classified
        filtered_objects = [
            obj for obj in classified_objects if obj["type"] != "unmarked"
        ]

        if not filtered_objects:
            click.secho(
                "Error: No classified objects. Cannot generate configuration.",
                fg="red",
                err=True,
            )
            sys.exit(1)

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

        # Generate insertion queries
        if verbose:
            click.echo("Generating insertion queries...", err=True)

        insert_generator = InsertionQueryGenerator()
        ordered_objects, insert_queries = insert_generator.generate(
            filtered_objects, relationships
        )

        # Generate read queries
        if verbose:
            click.echo("Generating read queries...", err=True)

        read_generator = ReadQueryGenerator()
        read_queries = read_generator.generate(filtered_objects, relationships)

        # Generate TOML configuration
        if verbose:
            click.echo("Generating TOML configuration...", err=True)

        toml_generator = TOMLConfigGenerator()
        output_content = toml_generator.generate(
            ordered_objects, insert_queries, read_queries, relationships
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
