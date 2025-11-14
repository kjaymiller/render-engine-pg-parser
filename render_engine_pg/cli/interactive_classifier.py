"""
Interactive table classifier for SQL schemas without annotations.

Allows users to classify unannotated tables as page/collection/attribute/junction
through interactive prompts, then generates TOML config automatically.
"""

from typing import List, Dict, Any, Optional
import click
from render_engine_pg.cli.relationship_analyzer import RelationshipAnalyzer
from render_engine_pg.cli.types import ObjectType, Classification


class InteractiveClassifier:
    """Guides user through interactive classification of database tables."""

    # Shortcut keys to ObjectType mapping
    SHORTCUT_TO_TYPE = {
        "p": ObjectType.PAGE,
        "c": ObjectType.COLLECTION,
        "a": ObjectType.ATTRIBUTE,
        "j": ObjectType.JUNCTION,
        "s": None,  # skip
    }

    def __init__(self, verbose: bool = False):
        """
        Initialize classifier.

        Args:
            verbose: If True, show detailed information during classification
        """
        self.verbose = verbose
        self.analyzer = RelationshipAnalyzer()
        self.relationships: List[Dict[str, Any]] = []

    def classify_tables(
        self, objects: List[Dict[str, Any]], skip_annotated: bool = True
    ) -> tuple:
        """
        Interactively classify tables.

        Args:
            objects: List of table objects from SQLParser
            skip_annotated: If True, skip tables that are already annotated

        Returns:
            Tuple of (classified_objects, count_of_classified_tables)
        """
        # First pass: analyze all relationships
        self.relationships = self.analyzer.analyze(objects)

        # Filter to unmarked tables if requested
        tables_to_classify = []
        for obj in objects:
            if skip_annotated and obj["type"] != "unmarked":
                continue
            tables_to_classify.append(obj)

        if not tables_to_classify:
            click.echo("No unmarked tables to classify.")
            return objects, 0

        classified_count = 0

        # Interactive classification loop
        for obj in tables_to_classify:
            self._display_table_info(obj)
            classification = self._prompt_classification(obj)

            if classification is None:
                click.echo("  → Skipped\n")
                continue

            # Update the object with new classification
            obj["type"] = classification.object_type.value
            if classification.parent_collection:
                obj["attributes"]["parent_collection"] = (
                    classification.parent_collection
                )

            # Add collection_name for collections
            if classification.object_type == ObjectType.COLLECTION:
                obj["attributes"]["collection_name"] = obj["name"]

            classified_count += 1
            click.echo(f"  ✓ Classified as '{classification.object_type.value}'")
            if classification.parent_collection:
                click.echo(f"    Parent: {classification.parent_collection}")
            click.echo()

        return objects, classified_count

    def _display_table_info(self, obj: Dict[str, Any]) -> None:
        """
        Display table information to help user classify it.

        Args:
            obj: Table object to display
        """
        table_name = obj["name"]
        columns = obj["columns"]

        click.echo(click.style(f"\nTable: {table_name}", fg="cyan", bold=True))
        click.echo(f"  Columns: {', '.join(columns)}")

        # Detect primary key
        pk_indicators = [
            c
            for c in columns
            if c == "id" or c.startswith(f"{table_name[:-1]}_id")
        ]
        if pk_indicators:
            click.echo(f"  Primary Key: {pk_indicators[0]}")

        # Find related tables through foreign keys
        related = self._get_related_tables(table_name)
        if related:
            click.echo(f"  Related Tables: {', '.join(related)}")

        # Provide classification hints
        hints = self._suggest_classification(obj)
        if hints:
            click.echo(f"  Hint: {hints}")

    def _get_related_tables(self, table_name: str) -> List[str]:
        """
        Find tables related to the given table.

        Args:
            table_name: Name of the table to find relations for

        Returns:
            List of related table names
        """
        related = set()
        for rel in self.relationships:
            if rel["source"] == table_name:
                related.add(rel["target"])
            elif rel["target"] == table_name:
                related.add(rel["source"])
        return sorted(list(related))

    def _suggest_classification(self, obj: Dict[str, Any]) -> Optional[str]:
        """
        Suggest a classification based on table structure.

        Args:
            obj: Table object to analyze

        Returns:
            Suggestion string or None
        """
        table_name = obj["name"]
        columns = obj["columns"]

        # Check for junction table patterns (table_table)
        related = self._get_related_tables(table_name)

        # Junction table heuristics:
        # - 2+ foreign keys (detected as related tables)
        # - Composite primary key pattern
        # - Few columns overall
        fk_count = sum(1 for col in columns if col.endswith("_id"))
        if len(related) >= 2 and fk_count >= 2 and len(columns) <= 4:
            return "This looks like a junction table (many-to-many relationship)"

        # Attribute table heuristics:
        # - Single primary key, few other columns
        # - Often names like 'tags', 'categories', etc.
        if len(columns) <= 3 and any(c == "id" for c in columns):
            # Check if it looks like lookup/reference data
            if any(
                lookup in table_name.lower()
                for lookup in ["tag", "categor", "status", "type", "role"]
            ):
                return "This looks like an attribute/lookup table"

        # Collection/Page heuristics:
        # - Multiple content columns (title, content, description, etc.)
        content_indicators = ["content", "title", "description", "body", "text"]
        content_cols = [
            c for c in columns if any(ind in c.lower() for ind in content_indicators)
        ]
        if len(content_cols) >= 2:
            return "This looks like a content table (collection or page)"

        return None

    def _prompt_classification(self, obj: Dict[str, Any]) -> Optional[Classification]:
        """
        Prompt user to classify a single table.

        Args:
            obj: Table object to classify

        Returns:
            Classification object or None if skipped
        """
        while True:
            # Build prompt with shortcut keys
            prompt_text = (
                "Classify as: "
                "[p]age / [c]ollection / [a]ttribute / [j]unction / [s]kip?"
            )
            choice = click.prompt(prompt_text, default="s").lower().strip()

            # Handle shortcuts and full type names
            object_type = None
            if choice in self.SHORTCUT_TO_TYPE:
                object_type = self.SHORTCUT_TO_TYPE[choice]
                break
            else:
                # Try to match full type names
                try:
                    object_type = ObjectType(choice)
                    break
                except ValueError:
                    click.echo("  Invalid choice. Please enter: p, c, a, j, or s")
                    continue

        # Handle skip
        if object_type is None:
            return None

        # Ask for parent collection if applicable
        parent_collection = None
        if object_type in (ObjectType.PAGE, ObjectType.ATTRIBUTE, ObjectType.JUNCTION):
            parent_prompt = (
                "Parent collection name (optional, press Enter to skip)"
            )
            parent_collection = click.prompt(parent_prompt, default="").strip()
            if not parent_collection:
                parent_collection = None

        return Classification(
            object_type=object_type, parent_collection=parent_collection
        )
