import sqlite3
import pathlib
import logging

from .schema import (
    create_conversations_table,
    create_messages_table,
    create_tool_calls_table,
)

logger = logging.getLogger(__name__)
script_dir = pathlib.Path(__file__).resolve().parent
DB_PATH = script_dir.parents[1] / "data" / "jla.db"

def get_connection() -> sqlite3.Connection:
    """
    Get a connection to the SQLite database.

    Args:
        db_path (str): The path to the SQLite database file.

    Returns:
        sqlite3.Connection: A connection object to the SQLite database.
    """
    try:
        logger.debug("Opening database connection to %s", DB_PATH)
        conn = sqlite3.connect(DB_PATH)
        logger.debug("Database connection opened")
        return conn
    except sqlite3.Error:
        logger.exception("Failed to open database connection to %s", DB_PATH)
        raise

def initialize_database(conn: sqlite3.Connection) -> None:
    """
    Initialize the SQLite database by creating necessary tables.

    Args:
        conn (sqlite3.Connection): The connection object to the SQLite database.
    """
    try:
        create_conversations_table(conn)
        create_messages_table(conn)
        create_tool_calls_table(conn)
        logger.info("Database initialized successfully")
    except Exception:
        logger.exception("Failed to initialize database")
        raise