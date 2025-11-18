#!/usr/bin/env python3
"""
Unified CLI for render-engine PostgreSQL Parser.

Intelligently classifies SQL schema tables and generates TOML configuration.
Supports:
- Automatic classification of unmarked tables (default)
- Interactive classification (--interactive flag)
- Manual annotation via SQL comments (-- @collection, etc.)
- Ignoring PRIMARY KEY and TIMESTAMP columns (--ignore-pk, --ignore-timestamps)
"""

import sys
from pathlib import Path
from typing import Optional

import click

from .sql_parser import SQLParser
from .relationship_analyzer import RelationshipAnalyzer
from .interactive_classifier import InteractiveClassifier
from .auto_classifier import AutoClassifier, ObjectType
from .cli_common import (
    generate_toml_config,
    handle_cli_error,
    create_option_output,
    create_option_verbose,
    create_option_ignore_pk,
    create_option_ignore_timestamps,
    create_option_interactive,
)


@click.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@create_option_output()
@create_option_verbose()
@create_option_interactive()
@create_option_ignore_pk()
@create_option_ignore_timestamps()
def main(
    input_file: Path,
    output: Optional[str],
    verbose: bool,
    interactive: bool,
    ignore_pk: bool,
    ignore_timestamps: bool,
) -> None:
    """
    Analyze SQL schema and generate render-engine TOML configuration.

    This command reads a SQL file (typically from pg_dump), classifies all tables
    as pages, collections, attributes, or junctions, and generates TOML configuration
    with INSERT and SELECT queries.

    Classification modes:
    - AUTO (default): Automatically classifies unmarked tables using intelligent heuristics
    - INTERACTIVE (--interactive): Prompts user to manually classify each unmarked table
    - ANNOTATED: Uses -- @collection, -- @page, etc. comments in SQL for classification

    Examples:
        # Auto-classify and ignore PRIMARY KEY columns
        render-engine-pg schema.sql --ignore-pk

        # Interactive mode for complex schemas
        render-engine-pg schema.sql --interactive

        # Save to file with verbose output
        render-engine-pg schema.sql --ignore-pk -o config.toml -v
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

        # Parse SQL - captures annotated objects and all unmarked tables
        sql_parser = SQLParser(
            ignore_pk=ignore_pk, ignore_timestamps=ignore_timestamps
        )
        parsed_objects = sql_parser.parse(sql_content)

        if verbose:
            click.echo(f"Found {len(parsed_objects)} objects", err=True)
            for obj in parsed_objects:
                click.echo(f"  - {obj['type']}: {obj['name']}", err=True)

        # Separate annotated from unmarked tables
        annotated_objects = [obj for obj in parsed_objects if obj["type"] != "unmarked"]
        unmarked_objects = [obj for obj in parsed_objects if obj["type"] == "unmarked"]

        if verbose:
            click.echo(
                f"  ({len(annotated_objects)} annotated, {len(unmarked_objects)} unmarked)",
                err=True,
            )

        # Classify unmarked tables
        classified_objects = list(annotated_objects)  # Start with annotated

        if unmarked_objects:
            if interactive:
                # Interactive mode: use existing InteractiveClassifier
                if verbose:
                    click.echo("\nStarting interactive classification...", err=True)

                classifier = InteractiveClassifier(verbose=verbose)
                classified_objects, classified_count = classifier.classify_tables(
                    parsed_objects, skip_annotated=True
                )

                if verbose:
                    click.echo(f"Classified {classified_count} tables", err=True)
            else:
                # Auto mode: use heuristics to classify
                if verbose:
                    click.echo(
                        "\nAuto-classifying unmarked tables using heuristics...",
                        err=True,
                    )

                # First analyze relationships for all objects
                analyzer = RelationshipAnalyzer()
                relationships = analyzer.analyze(parsed_objects)

                # Auto-classify unmarked tables
                auto_classifier = AutoClassifier()
                classified_count = 0

                for obj in unmarked_objects:
                    result = auto_classifier.classify(
                        obj, relationships, verbose=verbose
                    )
                    obj["type"] = result.object_type.value
                    classified_count += 1

                    if verbose and result.reasoning:
                        click.echo(
                            f"  {obj['name']}: {result.object_type.value} "
                            f"(confidence: {result.confidence:.0%})",
                            err=True,
                        )

                classified_objects = annotated_objects + unmarked_objects

                if verbose:
                    click.echo(f"Auto-classified {classified_count} tables", err=True)
        else:
            if verbose:
                click.echo("No unmarked tables to classify", err=True)

        # Filter out any remaining unmarked tables
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

        # Generate TOML configuration using common pipeline
        output_content = generate_toml_config(filtered_objects, [], verbose=verbose)

        # Write output
        if output:
            output_path = Path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output_content)
            if verbose:
                click.echo(f"Output written to {output_path}", err=True)
        else:
            click.echo(output_content)

        if verbose:
            click.echo("Done!", err=True)

    except Exception as e:
        handle_cli_error(e, verbose=verbose)
        sys.exit(1)


if __name__ == "__main__":
    main()
