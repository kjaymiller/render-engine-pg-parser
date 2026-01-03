from render_engine_pg.parsers import PGParser


def test_pg_parser_content():
    # Simple content
    content = "some content"
    attrs, result_content = PGParser.parse_content(content)
    assert attrs == {}
    assert result_content == content


def test_pg_parser_with_frontmatter():
    # Content with frontmatter
    content_with_fm = "---\ntitle: foo\n---\nbar"
    attrs, result_content = PGParser.parse_content(content_with_fm)
    assert attrs == {}
    assert result_content == content_with_fm
