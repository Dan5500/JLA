import sqlite3
import pytest

from JLA.database.connection import initialize_database
from JLA.database import handling


def make_db():
    conn = sqlite3.connect(":memory:")
    initialize_database(conn)
    return conn


def test_list_tables_and_get_schema():
    conn = make_db()
    tables = handling.list_db_tables(conn)
    # initialize_database creates the testing table and others
    assert 'testing' in tables

    schema = handling.get_schema(conn, 'testing')
    col_names = [col[1] for col in schema]
    assert 'id' in col_names and 'name' in col_names and 'value' in col_names


def test_read_db_table_and_read_row():
    conn = make_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO testing (name, value) VALUES (?, ?)", ("alice", "42"))
    cur.execute("INSERT INTO testing (name, value) VALUES (?, ?)", ("bob", "100"))

    rows = handling.read_db_table(conn, 'testing')
    # should have at least the two we inserted
    assert any(r[1] == 'alice' for r in rows)
    assert any(r[1] == 'bob' for r in rows)

    # read_row default (-1) returns latest row
    latest = handling.read_row(conn, 'testing')
    assert latest and latest[0][1] == 'bob'

    # read specific id
    first = handling.read_row(conn, 'testing', 1)
    assert first and first[0][1] == 'alice'


def test_read_db_table_invalid_table():
    conn = make_db()
    with pytest.raises(ValueError):
        handling.read_db_table(conn, 'no_such_table')


def test_insert_row_success_and_validation():
    conn = make_db()
    # normal insert
    handling.insert_row(conn, 'testing', ['charlie', '7'])
    rows = handling.read_db_table(conn, 'testing')
    assert any(r[1] == 'charlie' and r[2] == '7' for r in rows)

    # wrong number of values
    with pytest.raises(ValueError):
        handling.insert_row(conn, 'testing', ['only_one_value'])

    # create a dedicated table with INTEGER and REAL to test type validation
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE int_test (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            n INTEGER NOT NULL,
            r REAL NOT NULL,
            t TEXT NOT NULL
        )
    ''')

    # valid insert should work
    handling.insert_row(conn, 'int_test', [1, 3.14, 'ok'])
    rows = handling.read_db_table(conn, 'int_test')
    assert any(r[1] == 1 and abs(r[2] - 3.14) < 1e-6 and r[3] == 'ok' for r in rows)

    # invalid integer value should raise (pydantic validation)
    with pytest.raises(Exception):
        handling.insert_row(conn, 'int_test', ['not_int', 2.5, 'x'])


def test_update_row_behaviour_and_errors():
    conn = make_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO testing (name, value) VALUES (?, ?)", ("dave", "1"))

    # successful update
    handling.update_row(conn, 'testing', 1, 'name', 'david')
    row = handling.read_row(conn, 'testing', 1)
    assert row and row[0][1] == 'david'

    # invalid column name
    with pytest.raises(ValueError):
        handling.update_row(conn, 'testing', 1, 'no_column', 'x')

    # invalid table name
    with pytest.raises(ValueError):
        handling.update_row(conn, 'no_table', 1, 'name', 'x')

    # create table with integer column and test invalid type for update
    cur.execute('''
        CREATE TABLE int_update (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            n INTEGER NOT NULL
        )
    ''')
    cur.execute("INSERT INTO int_update (n) VALUES (?)", (5,))

    # valid update
    handling.update_row(conn, 'int_update', 1, 'n', 10)
    updated = handling.read_row(conn, 'int_update', 1)
    assert updated and updated[0][1] == 10

    # invalid update value should raise (validation)
    with pytest.raises(Exception):
        handling.update_row(conn, 'int_update', 1, 'n', 'not_a_number')
