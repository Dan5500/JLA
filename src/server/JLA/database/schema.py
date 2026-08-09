import sqlite3
import logging

logger = logging.getLogger(__name__)


def create_conversations_table(conn: sqlite3.Connection) -> None:
    """
    Create the conversations table if it does not already exist.

    Args:
        conn (sqlite3.Connection): The SQLite database connection.
    """
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    logger.info("Ensured conversations table exists")


def create_messages_table(conn: sqlite3.Connection) -> None:
    """
    Create the messages table if it does not already exist.

    Args:
        conn (sqlite3.Connection): The SQLite database connection.
    """
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        )
    ''')
    conn.commit()
    logger.info("Ensured messages table exists")


def create_tool_calls_table(conn: sqlite3.Connection) -> None:
    """
    Create the tool calls table if it does not already exist.

    Args:
        conn (sqlite3.Connection): The SQLite database connection.
    """
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tool_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            tool_name TEXT NOT NULL,
            arguments_json TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        )
    ''')
    conn.commit()
    logger.info("Ensured tool_calls table exists")
