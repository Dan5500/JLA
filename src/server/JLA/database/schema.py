import sqlite3
import logging

logger = logging.getLogger(__name__)

# template for creating a table in the database, making this faster/easier to create tables
def _create_table(conn: sqlite3.Connection, sql: str, table_name: str) -> None:
    cursor = conn.cursor()
    cursor.execute(sql)
    conn.commit()
    logger.info("Ensured %s table exists", table_name)

# testing table: for testing purposes
def create_testing_table(conn: sqlite3.Connection) -> None:
    """
    Create a testing table for demonstration purposes.

    Args:
        conn (sqlite3.Connection): The SQLite database connection.
    """
    _create_table(conn, '''
        CREATE TABLE IF NOT EXISTS testing (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            value TEXT NOT NULL
        )
    ''', "testing")

# notes table: for indexing vault markdown files
def create_notes_table(conn: sqlite3.Connection) -> None:
    """Create the notes table used to index vault markdown files."""
    _create_table(conn, '''
        CREATE TABLE IF NOT EXISTS notes (
            note_id INTEGER PRIMARY KEY AUTOINCREMENT,
            vault TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            modified_time REAL NOT NULL,
            file_size INTEGER NOT NULL,
            title TEXT,
            index_status TEXT NOT NULL DEFAULT 'indexed',
            last_indexed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(vault, file_path)
        )
    ''', "notes")

# links table: for indexing outgoing links in vault markdown files
def create_links_table(conn: sqlite3.Connection) -> None:
    """Create the outgoing links table."""
    _create_table(conn, '''
        CREATE TABLE IF NOT EXISTS links (
            link_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_note_id INTEGER NOT NULL,
            link_index INTEGER NOT NULL,
            target_name TEXT NOT NULL,
            target_path TEXT,
            target_note_id INTEGER,
            target_section TEXT,
            FOREIGN KEY(source_note_id) REFERENCES notes(note_id) ON DELETE CASCADE,
            FOREIGN KEY(target_note_id) REFERENCES notes(note_id) ON DELETE SET NULL,
            UNIQUE(source_note_id, link_index)
        )
    ''', "links")

# chunks table: for indexing header sections in vault markdown files
def create_chunks_table(conn: sqlite3.Connection) -> None:
    """Create the chunks table used to index header sections."""
    _create_table(conn, '''
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
            note_id INTEGER NOT NULL,
            parent_chunk_id INTEGER,
            chunk_index INTEGER NOT NULL,
            name TEXT NOT NULL,
            start_line INTEGER NOT NULL,
            end_line INTEGER NOT NULL,
            FOREIGN KEY(note_id) REFERENCES notes(note_id) ON DELETE CASCADE,
            FOREIGN KEY(parent_chunk_id) REFERENCES chunks(chunk_id) ON DELETE CASCADE,
            UNIQUE(note_id, chunk_index)
        )
    ''', "chunks")

# conversations table: for storing conversations with the AI
def create_conversations_table(conn: sqlite3.Connection) -> None:
    """
    Create the conversations table if it does not already exist.

    Args:
        conn (sqlite3.Connection): The SQLite database connection.
    """
    _create_table(conn, '''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''', "conversations")

# messages table: for storing individual messages in each conversation
# this table is linked to the conversations table via a foreign key
# might want to routinely clean this, as it can get massive and is not needed for the AI to function
def create_messages_table(conn: sqlite3.Connection) -> None:
    """
    Create the messages table if it does not already exist.

    Args:
        conn (sqlite3.Connection): The SQLite database connection.
    """
    _create_table(conn, '''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        )
    ''', "messages")

# tool_calls table: for storing tool calls made by the AI
# this table is linked to the conversations table via a foreign key
# good for logging and debugging, as well as for future analysis of tool usage
def create_tool_calls_table(conn: sqlite3.Connection) -> None:
    """
    Create the tool calls table if it does not already exist.

    Args:
        conn (sqlite3.Connection): The SQLite database connection.
    """
    _create_table(conn, '''
        CREATE TABLE IF NOT EXISTS tool_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            tool_name TEXT NOT NULL,
            arguments_json TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        )
    ''', "tool_calls")
