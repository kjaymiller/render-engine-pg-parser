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
        self.relationships = []

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
            # Skip if already classified (might have been auto-classified as junction)
            if obj["type"] != "unmarked":
                continue

            suggested_type = self._display_table_info(obj)
            classification = self._prompt_classification(obj, suggested_type)

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

            # Auto-classify junctions for this collection
            if classification.object_type == ObjectType.COLLECTION:
                related_junctions = self._find_junctions_for_collection(obj["name"], objects)
                for junction_obj in related_junctions:
                    # Auto-classify junction with this collection as parent
                    junction_obj["type"] = ObjectType.JUNCTION.value
                    junction_obj["attributes"]["parent_collection"] = obj["name"]
                    classified_count += 1

                    click.echo(f"  ✓ Auto-classified '{junction_obj['name']}' as 'junction'")
                    click.echo(f"    Parent: {obj['name']}")
                    click.echo()

        return objects, classified_count

    def _display_table_info(self, obj: Dict[str, Any]) -> Optional[ObjectType]:
        """
        Display table information to help user classify it.

        Args:
            obj: Table object to display

        Returns:
            Suggested ObjectType if a strong hint exists, None otherwise
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
        suggested_type, hint_text = self._suggest_classification(obj)
        if hint_text:
            click.echo(click.style(f"  Hint: {hint_text}", fg="green"))
            return suggested_type

        return None

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

    def _find_junctions_for_collection(self, collection_name: str, all_objects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Find all junction tables that connect to a given collection.

        Args:
            collection_name: Name of the collection to find junctions for
            all_objects: List of all table objects

        Returns:
            List of junction table objects that relate to this collection
        """
        junctions = []

        for obj in all_objects:
            # Skip if already classified
            if obj["type"] != "unmarked":
                continue

            # Check if this could be a junction table
            columns = obj["columns"]
            fk_count = sum(1 for col in columns if col.endswith("_id"))

            # Junction tables typically have 2+ FK columns and few total columns
            if fk_count >= 2 and len(columns) <= 4:
                # Check if it connects to this collection
                related = self._get_related_tables(obj["name"])
                if collection_name in related:
                    junctions.append(obj)

        return junctions

    def _suggest_classification(self, obj: Dict[str, Any]) -> tuple:
        """
        Suggest a classification based on table structure.

        Args:
            obj: Table object to analyze

        Returns:
            Tuple of (suggestion_type: ObjectType or None, suggestion_text: str or None)
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
            return ObjectType.JUNCTION, "This looks like a junction table (many-to-many relationship)"

        # Attribute table heuristics:
        # - Single primary key, few other columns
        # - Often names like 'tags', 'categories', etc.
        if len(columns) <= 3 and any(c == "id" for c in columns):
            # Check if it looks like lookup/reference data
            if any(
                lookup in table_name.lower()
                for lookup in ["tag", "categor", "status", "type", "role"]
            ):
                return ObjectType.ATTRIBUTE, "This looks like an attribute/lookup table"

        # Collection/Page heuristics:
        # - Multiple content columns (title, content, description, etc.)
        content_indicators = ["content", "title", "description", "body", "text"]
        content_cols = [
            c for c in columns if any(ind in c.lower() for ind in content_indicators)
        ]
        if len(content_cols) >= 2:
            return ObjectType.COLLECTION, "This looks like a content table (collection or page)"

        return None, None

    def _prompt_classification(self, obj: Dict[str, Any], suggested_type: Optional[ObjectType] = None) -> Optional[Classification]:
        """
        Prompt user to classify a single table.

        Args:
            obj: Table object to classify
            suggested_type: ObjectType from hint analysis, if available

        Returns:
            Classification object or None if skipped
        """
        while True:
            # Build prompt with shortcut keys
            prompt_text = (
                "Classify as: "
                "[p]age / [c]ollection / [a]ttribute / [j]unction / [s]kip?"
            )

            # If we have a hint, suggest pressing Enter to use it
            if suggested_type:
                hint_shortcut = next(
                    (k for k, v in self.SHORTCUT_TO_TYPE.items() if v == suggested_type),
                    None
                )
                if hint_shortcut:
                    prompt_text += f" (or press Enter for hint: {hint_shortcut})"
                    default_choice = hint_shortcut
                else:
                    default_choice = "s"
            else:
                default_choice = "s"

            choice = click.prompt(prompt_text, default=default_choice).lower().strip()

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

        # Ask for parent collection if applicable (attributes and junctions only)
        # Pages are standalone and don't have parent collections
        parent_collection = None
        if object_type in (ObjectType.ATTRIBUTE, ObjectType.JUNCTION):
            # Check if this is a shared lookup table (referenced by multiple junction tables)
            # These should not have a parent collection
            is_shared_lookup = self._is_shared_lookup_table(obj["name"])

            # For junctions, try to auto-detect parent from relationships
            if object_type == ObjectType.JUNCTION:
                detected_parents = self._detect_junction_parents(obj)
                if detected_parents:
                    # Show detected relationships
                    parent_str = " ← → ".join(detected_parents)
                    click.echo(f"  Detected: Junction connects {parent_str}")
                    # Use first table as parent (typically the collection)
                    parent_collection = detected_parents[0]
                    click.echo(f"  Parent collection: {parent_collection} (auto-detected)")

            # For attributes or junctions without detected parents, ask user
            # Skip parent prompt for shared lookup tables (attributes referenced by multiple collections)
            if not parent_collection and not is_shared_lookup:
                parent_prompt = (
                    "Parent collection name (optional, press Enter to skip)"
                )
                parent_collection = click.prompt(parent_prompt, default="").strip()
                if not parent_collection:
                    parent_collection = None
            elif is_shared_lookup and object_type == ObjectType.ATTRIBUTE:
                click.echo("  Shared lookup table - no parent collection")

        # Ask for unique columns for attributes and junctions (enables upsert behavior)
        unique_columns = None
        if object_type in (ObjectType.ATTRIBUTE, ObjectType.JUNCTION):
            click.echo(f"  Unique columns enable upsert (insert or update) behavior.")
            unique_cols_input = click.prompt(
                "  Enter unique column names (comma-separated, or press Enter to skip)",
                default=""
            ).strip()
            if unique_cols_input:
                unique_columns = [col.strip() for col in unique_cols_input.split(",") if col.strip()]

        # Store unique columns in attributes for query generator
        if unique_columns:
            obj["attributes"]["unique_columns"] = unique_columns

        return Classification(
            object_type=object_type,
            parent_collection=parent_collection
        )

    def _is_shared_lookup_table(self, table_name: str) -> bool:
        """
        Check if a table is a shared lookup table (referenced by multiple junction tables).

        A shared lookup table is one that is referenced via FK from 2+ different junction tables
        (e.g., tags used by blog_tags, notes_tags, microblog_tags).

        Args:
            table_name: Name of the table to check

        Returns:
            True if table is referenced by FK from 2+ junction tables
        """
        junction_sources = set()

        # Find all FK relationships pointing to this table
        for rel in self.relationships:
            if rel["target"] == table_name and rel["type"] == "foreign_key":
                source_table = rel["source"]
                # Check if source is a junction table (has junction-like name pattern)
                if "_" in source_table:  # Junction tables typically have underscore (e.g., blog_tags)
                    junction_sources.add(source_table)

        return len(junction_sources) >= 2

    def _detect_junction_parents(self, junction_obj: Dict[str, Any]) -> List[str]:
        """
        Detect parent tables for a junction table by analyzing foreign key columns.

        For a junction table like blog_tags(blog_id, tag_id), this identifies
        that it connects 'blog' and 'tags'.

        Args:
            junction_obj: The junction table object

        Returns:
            List of parent table/object names (typically 2 for M2M junctions)
        """
        parents = []

        # Build table name to object name mapping
        table_to_name = {}
        for rel in self.relationships:
            # Look for relationships that reference this junction
            if "junction_table" in rel.get("metadata", {}) and rel["metadata"]["junction_table"] == junction_obj["name"]:
                # Extract the parent tables from the relationship
                if rel["source"] not in parents:
                    parents.append(rel["source"])
                if rel["target"] not in parents and len(parents) < 2:
                    parents.append(rel["target"])

        # If no relationships found, try to infer from FK column patterns
        if not parents:
            for column in junction_obj["columns"]:
                # Look for _id suffix and infer table name
                if column.endswith("_id"):
                    # Remove _id suffix and singularize if needed
                    table_hint = column[:-3]  # Remove _id
                    # Find matching object
                    for rel in self.relationships:
                        if rel.get("column") == column:
                            parents.append(rel.get("target"))
                            break

        return parents[:2]  # Return up to 2 parents for M2M
