"""
Tests for the connection module and get_db_connection factory function.
"""

import pytest
from render_engine_pg.connection import get_db_connection, PostgresQuery


class TestGetDbConnection:
    """Tests for the get_db_connection factory function."""

    def test_connection_object_returned(self, mocker, mock_connection):
        """Test that a connection object is returned."""
        mocker.patch(
            "render_engine_pg.connection.Connection.connect",
            return_value=mock_connection,
        )

        result = get_db_connection(
            host="localhost",
            port=5432,
            database="test_db",
            user="test_user",
            password="test_pass",
        )

        assert result is not None
        assert result == mock_connection
        assert hasattr(result, "autocommit")

    def test_connection_with_correct_parameters(self, mocker):
        """Test that connection is called with correct parameters."""
        mock_connect = mocker.patch("render_engine_pg.connection.Connection.connect")
        mock_connect.return_value = mocker.MagicMock()

        get_db_connection(
            host="db.example.com",
            port=5433,
            database="production_db",
            user="app_user",
            password="secure_password",
        )

        mock_connect.assert_called_once_with(
            host="db.example.com",
            port=5433,
            dbname="production_db",
            user="app_user",
            password="secure_password",
            autocommit=True,
        )

    def test_connection_with_connection_string(self, mocker):
        """Test that connection string is used when provided."""
        mock_connect = mocker.patch("render_engine_pg.connection.Connection.connect")
        mock_connect.return_value = mocker.MagicMock()

        connection_string = "postgresql://user:pass@localhost:5432/mydb"
        get_db_connection(connection_string=connection_string)

        mock_connect.assert_called_once_with(connection_string, autocommit=True)

    def test_connection_autocommit_enabled(self, mocker):
        """Test that autocommit is always set to True."""
        mock_connect = mocker.patch("render_engine_pg.connection.Connection.connect")
        mock_connect.return_value = mocker.MagicMock()

        get_db_connection(
            host="localhost", database="test_db", user="user", password="pass"
        )

        # Verify autocommit=True in the call
        call_kwargs = mock_connect.call_args.kwargs
        assert call_kwargs["autocommit"] is True

    def test_connection_string_overrides_parameters(self, mocker):
        """Test that connection_string takes precedence over individual parameters."""
        mock_connect = mocker.patch("render_engine_pg.connection.Connection.connect")
        mock_connect.return_value = mocker.MagicMock()

        connection_string = "postgresql://user:pass@localhost:5432/mydb"
        get_db_connection(
            connection_string=connection_string,
            host="ignored.com",
            database="ignored_db",
        )

        # Connection.connect should be called with connection_string and autocommit
        assert mock_connect.call_count == 1
        call_args = mock_connect.call_args
        assert call_args[0][0] == connection_string
        assert call_args.kwargs["autocommit"] is True


class TestPostgresQuery:
    """Tests for the PostgresQuery NamedTuple."""

    def test_postgres_query_creation(self, mock_connection):
        """Test that PostgresQuery object can be created with connection and query."""
        query_str = "SELECT * FROM pages WHERE id = %s"

        pg_query = PostgresQuery(connection=mock_connection, query=query_str)

        assert pg_query.connection == mock_connection
        assert pg_query.query == query_str

    def test_postgres_query_has_required_fields(self, mock_connection):
        """Test that PostgresQuery has both connection and query fields."""
        pg_query = PostgresQuery(
            connection=mock_connection, query="SELECT * FROM pages"
        )

        assert hasattr(pg_query, "connection")
        assert hasattr(pg_query, "query")
        assert pg_query.connection is mock_connection
        assert isinstance(pg_query.query, str)
