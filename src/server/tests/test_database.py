from JLA.database.connection import get_connection, initialize_database

def test_connection():
    # Test the database connection
    conn = get_connection()
    assert conn is not None  # Replace with actual test logic

def test_initialize_database():
    # Test the database initialization
    conn = get_connection()
    initialize_database(conn)
    # Add assertions to check if tables are created correctly
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    assert ('conversations',) in tables
    assert ('messages',) in tables
    assert ('tool_calls',) in tables