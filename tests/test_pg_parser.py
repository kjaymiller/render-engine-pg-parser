from render_engine_pg.parsers import PGPageParser


def test_pg_parser_content():
    # Content as dict
    data = {"title": "Hello", "content": "some content"}
    attrs, result_content = PGPageParser.parse_content(data)
    assert attrs == data
    assert result_content == "some content"


def test_pg_parser_with_no_content_field():
    # Content dict without content field
    data = {"title": "foo"}
    attrs, result_content = PGPageParser.parse_content(data)
    assert attrs == data
    assert result_content is None
