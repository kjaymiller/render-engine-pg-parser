from typing import NamedTuple
from psycopg import Connection
from typing import Optional


def get_db_connection(
    connection_string: Optional[str] = None,
    *,
    host: str = "localhost",
    port: int = 5432,
    database: str = None,
    user: str = None,
    password: str = None,
) -> Connection:
    """
    Connection factory (keyword-only arguments).

    Can use either connection_string OR individual params.
    Returns a Connection for use with context manager.
    """
    if connection_string:
        return Connection.connect(connection_string, autocommit=True)
    else:
        return Connection.connect(
            host=host,
            port=port,
            dbname=database,
            user=user,
            password=password,
            autocommit=True,
        )


class PostgresQuery(NamedTuple):
    """Configuration for querying PostgreSQL

    Can be used in two ways:
    1. With explicit query: PostgresQuery(connection=db, query="SELECT ...")
    2. With collection_name: PostgresQuery(connection=db, collection_name="blog")
       - The query will be loaded from pyproject.toml [tool.render-engine.pg].read_sql

    Explicit query takes precedence if both are provided.
    """

    connection: Connection
    query: Optional[str] = None
    collection_name: Optional[str] = None
