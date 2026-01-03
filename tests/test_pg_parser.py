from render_engine_pg.parsers import PGPageParser


def test_pg_parser_content():
    # Content as list
    data = [{"title": "Hello", "content": "some content"}]
    attrs, result_content = PGPageParser.parse_content(data)
    assert attrs == {"data": data}
    assert result_content is None


def test_pg_parser_with_single_item_list():
    # Content as empty list
    data = []
    attrs, result_content = PGPageParser.parse_content(data)
    assert attrs == {"data": data}
    assert result_content is None
