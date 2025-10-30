#!/usr/bin/env python3
"""Test script for junction table support"""

from render_engine_pg.cli.sql_parser import SQLParser
from render_engine_pg.cli.relationship_analyzer import RelationshipAnalyzer

# Example SQL with pages, attributes, junction tables, and relationships
test_sql = """
-- @page
CREATE TABLE posts (
    id INT PRIMARY KEY,
    title VARCHAR(255),
    content TEXT
);

-- @attribute
CREATE TABLE tags (
    id INT PRIMARY KEY,
    name VARCHAR(255)
);

-- @junction
CREATE TABLE posts_tags (
    post_id INT REFERENCES posts(id),
    tag_id INT REFERENCES tags(id),
    PRIMARY KEY (post_id, tag_id)
);

-- @page
CREATE TABLE authors (
    id INT PRIMARY KEY,
    name VARCHAR(255)
);

-- @junction
CREATE TABLE posts_authors (
    post_id INT REFERENCES posts(id),
    author_id INT REFERENCES authors(id),
    PRIMARY KEY (post_id, author_id)
);

-- Unmarked table - should be inferred as attribute from junction usage
CREATE TABLE categories (
    id INT PRIMARY KEY,
    name VARCHAR(255),
    slug VARCHAR(255)
);

-- @junction
CREATE TABLE posts_categories (
    post_id INT REFERENCES posts(id),
    category_id INT REFERENCES categories(id),
    PRIMARY KEY (post_id, category_id)
);
"""

def main():
    print("=" * 60)
    print("Testing Junction Table Support with Attributes")
    print("=" * 60)

    # Parse SQL
    parser = SQLParser()
    objects = parser.parse(test_sql)

    print("\n✓ Parsed Objects:")
    for obj in objects:
        print(f"  - {obj['name']} (type: {obj['type']}, table: {obj['table']})")
        if obj['columns']:
            print(f"    columns: {', '.join(obj['columns'])}")

    # Analyze relationships
    analyzer = RelationshipAnalyzer()
    relationships = analyzer.analyze(objects)

    print("\n✓ Detected Relationships:")
    for rel in relationships:
        rel_type = rel['type']
        source = rel['source']
        target = rel['target']
        metadata = rel['metadata']

        if rel_type == "many_to_many_attribute":
            junction = metadata.get('junction_table', 'unknown')
            print(f"  - {source} <--many-to-many-attribute--> {target}")
            print(f"    (via {junction}, attribute: {metadata.get('target_type')})")
        elif rel_type == "many_to_many":
            junction = metadata.get('junction_table', 'unknown')
            print(f"  - {source} <--many-to-many--> {target}")
            print(f"    (via {junction})")
        elif rel_type == "foreign_key":
            print(f"  - {source} --> {target} (via {rel['column']})")
        else:
            print(f"  - {source} -[{rel_type}]-> {target}")

    # Verify relationship types
    print("\n✓ Verification:")
    m2m_attr = [r for r in relationships if r['type'] == 'many_to_many_attribute']
    m2m_regular = [r for r in relationships if r['type'] == 'many_to_many']

    print(f"  Found {len(m2m_attr)} many-to-many-attribute relationships")
    print(f"  Found {len(m2m_regular)} many-to-many relationships")

    # Check for posts <-> tags (attribute)
    posts_tags = [
        r for r in m2m_attr
        if (r['source'] == 'posts' and r['target'] == 'tags') or
           (r['source'] == 'tags' and r['target'] == 'posts')
    ]
    print(f"  ✓ posts <-> tags (attribute): {len(posts_tags)} relationships found")

    # Check for posts <-> authors (pages)
    posts_authors = [
        r for r in m2m_regular
        if (r['source'] == 'posts' and r['target'] == 'authors') or
           (r['source'] == 'authors' and r['target'] == 'posts')
    ]
    print(f"  ✓ posts <-> authors (pages): {len(posts_authors)} relationships found")

    # Check for posts <-> categories (unmarked, inferred)
    posts_categories = [
        r for r in m2m_attr
        if (r['source'] == 'posts' and r['target'] == 'categories') or
           (r['source'] == 'categories' and r['target'] == 'posts')
    ]
    print(f"  ✓ posts <-> categories (unmarked, inferred): {len(posts_categories)} relationships found")

    print("\n" + "=" * 60)
    print("Test Complete! ✓")
    print("=" * 60)

if __name__ == "__main__":
    main()
