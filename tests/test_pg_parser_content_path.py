from render_engine_pg.parsers import PGPageParser
from render_engine_pg.connection import PostgresQuery
from unittest.mock import MagicMock, patch


def test_parse_content_path_with_query():
    # Mock connection and cursor
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {
        "title": "Test Title",
        "content": "Test Content",
    }
    mock_connection = MagicMock()
    mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

    # Create PostgresQuery
    query = PostgresQuery(connection=mock_connection, query="SELECT * FROM posts")

    # Parse
    attrs, content = PGPageParser.parse_content_path(query)

    # Verify
    mock_cursor.execute.assert_called_with("SELECT * FROM posts")
    assert attrs == {"title": "Test Title", "content": "Test Content"}
    assert content == "Test Content"
    print("test_parse_content_path_with_query passed")


def test_parse_content_path_with_collection_name():
    # Mock connection and cursor
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {
        "title": "From Settings",
        "content": "Settings Content",
    }
    mock_connection = MagicMock()
    mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

    # Create PostgresQuery with collection_name
    query = PostgresQuery(connection=mock_connection, collection_name="blog")

    # Mock settings
    with patch("render_engine_pg.parsers.PGSettings") as MockSettings:
        mock_settings_instance = MockSettings.return_value
        mock_settings_instance.get_read_sql.return_value = "SELECT * FROM blog_posts"

        # Parse
        attrs, content = PGPageParser.parse_content_path(query)

        # Verify
        MockSettings.assert_called()
        mock_settings_instance.get_read_sql.assert_called_with("blog")
        mock_cursor.execute.assert_called_with("SELECT * FROM blog_posts")
        assert attrs == {"title": "From Settings", "content": "Settings Content"}
        assert content == "Settings Content"
        print("test_parse_content_path_with_collection_name passed")


if __name__ == "__main__":
    test_parse_content_path_with_query()
    test_parse_content_path_with_collection_name()
