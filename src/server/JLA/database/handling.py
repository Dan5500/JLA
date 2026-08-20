import sqlite3
import logging
from pydantic import TypeAdapter

logger = logging.getLogger(__name__)

def get_schema(conn: sqlite3.Connection, table_name: str) -> list:
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    table_data = cursor.fetchall()

    return table_data

def list_db_tables(conn: sqlite3.Connection) -> list[str]:
    """
    List all table names in the SQLite database.

    Args:
        conn (sqlite3.Connection): The SQLite database connection.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    return tables

def read_db_table(conn: sqlite3.Connection, table_name: str) -> list[tuple]:
    """
    Read all rows from a specified table in the SQLite database.

    Args:
        conn (sqlite3.Connection): The SQLite database connection.
        table_name (str): The name of the table to read from.

    Returns:
        list[tuple]: A list of tuples representing the rows in the table.
    """
    # check that the table actually exists in the database
    # also ensures the input is allowed (preventing SQL injection)
    valid_name = False
    for table in list_db_tables(conn):
        if table_name == table:
            valid_name = True
    if not valid_name:
        logger.warning(f"Table '{table_name}' does not exist in the database.")
        raise ValueError(f"Table '{table_name}' does not exist in the database.")

    # read the table
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM '{table_name}'")
    rows = cursor.fetchall()
    logger.debug(f"Read all rows in table: '{table_name}'")
    return rows

# reads a specified row in a table
def read_row(conn: sqlite3.Connection, table_name: str, row_id: int = -1): # maybe make it return sqlite3.Row instead of a list?
    # validate the table name
    valid_name = False
    for table in list_db_tables(conn):
        if table_name == table:
            valid_name = True
    if not valid_name:
        logger.warning(f"Table '{table_name}' does not exist in the database.")
        raise ValueError(f"Table '{table_name}' does not exist in the database.")
    
    cursor = conn.cursor()

    if(row_id == -1):
        # assuming every table has the automatic/autoincrement primary key first column id
        cursor.execute(f"SELECT * FROM {table_name} WHERE id = (SELECT MAX(id) FROM {table_name})")
        row = cursor.fetchall()
        logger.debug(f"Read latest row in table: {table_name}")
    else:
        # assuming every table has the automatic/autoincrement primary key first column id
        cursor.execute(f"SELECT * FROM {table_name} WHERE id = {row_id}")
        row = cursor.fetchall()
        logger.debug(f"Read row #{str(row_id)} in table: {table_name}")

    return row

def insert_row(conn: sqlite3.Connection, table_name: str, values: list[str]) -> None:
    # validate the table name
    valid_name = False
    for table in list_db_tables(conn):
        if table_name == table:
            valid_name = True
    if not valid_name:
        logger.warning(f"Table '{table_name}' does not exist in the database.")
        raise ValueError(f"Table '{table_name}' does not exist in the database.")

    # check that the values are in the right schema for this table
    # make sure there is a correct amount AND
    # that the data types are correct
    cursor = conn.cursor()

    cursor.execute(f"PRAGMA table_info({table_name})")
    table_data = cursor.fetchall()
    column_names = [col[1] for col in table_data]
    column_types = [col[2] for col in table_data]

    # check # of values
    # subtract 1 from column names to account for the automatic id column
    '''
        i could check if a table doesnt have an automatic ID
        as its first column by using the PRAGMA table_info() 
        data that I already have. 

        col[5] indicates if the column is the primary key for that row
        so if I do if(table_data[0][5] == 1), i'd be able to know
        if there is an automatic id in the table.

        but assuming every table i make for this project will have that
        automatic first column id, im not gonna worry abt it

        (col[5] is an integer, 0 if not pk, 1 if it is)
        pk = primary key
    '''
    if(len(column_names)-1 != len(values)):
        raise ValueError(f"Incorrect amount of values passed for table '{table_name}'")

    # checks the data types using Pydantic and 
    # fits the data type to the correct type if possible
    # then makes a verified values list, which is ready to be passed into SQLite
    correct_values = []
    for i in range(len(values)):
        match column_types[i+1]:
            case "NULL":
                logger.warning(f"Replacing value {i+1} with Null")
                correct_values.append(None)
            case "INTEGER":
                value_adapter = TypeAdapter(int)

                # raises a ValidationError if incompatiable. make sure to catch in main.py
                validated_value = value_adapter.validate_python(values[i])
                correct_values.append(validated_value)
            case "REAL":
                value_adapter = TypeAdapter(float)

                # raises a ValidationError if incompatiable. make sure to catch in main.py
                validated_value = value_adapter.validate_python(values[i])
                correct_values.append(validated_value)
            case "TEXT":
                value_adapter = TypeAdapter(str)

                # raises a ValidationError if incompatiable. make sure to catch in main.py
                validated_value = value_adapter.validate_python(values[i])
                correct_values.append(validated_value)
            case "BLOB":
                value_adapter = TypeAdapter(bytes)

                # raises a ValidationError if incompatiable. make sure to catch in main.py
                validated_value = value_adapter.validate_python(values[i])
                correct_values.append(validated_value)

    # construct the schema parameter for the SQLite command
    # as well as the ? part of the command
    schema = ""
    qmarks = ""
    for i in range(1,len(column_names)):
        if(column_names[i] != column_names[len(column_names)-1]):
            schema = schema + column_names[i] + ", "
            qmarks = qmarks + "?, "
        else:
            schema = schema + column_names[i]
            qmarks = qmarks + "?"

    # insert the row
    cursor.execute(f"INSERT INTO {table_name} ({schema}) VALUES ({qmarks})", tuple(correct_values))
    # log
    logger.debug(f"Inserted new row into {table_name} with values {correct_values}")
    
def update_row(conn: sqlite3.Connection, table_name: str, row_id: int, col_name: str, value: str) -> None:
    # validate the table name
    valid_name = False
    for table in list_db_tables(conn):
        if table_name == table:
            valid_name = True
    if not valid_name:
        logger.warning(f"Table '{table_name}' does not exist in the database.")
        raise ValueError(f"Table '{table_name}' does not exist in the database.")

    # check that the value is correct for its specified column
    # (right data type)
    cursor = conn.cursor()

    cursor.execute(f"PRAGMA table_info({table_name})")
    table_data = cursor.fetchall()
    column_names = [col[1] for col in table_data]
    column_types = [col[2] for col in table_data]

    # validate the column name
    index = -1
    for i in range(1,len(column_names)):
        if(col_name == column_names[i]):
            index = i
    if index == -1:
        logger.warning(f"Column '{col_name}' does not exist in table {table_name}")
        raise ValueError(f"Column '{col_name}' does not exist in table {table_name}")
    

    # checks the data type using Pydantic and 
    # fits the data type to the correct type if possible
    # then makes a verified value variable, which is ready to be passed into SQLite
    match column_types[index]:
        case "NULL":
            logger.warning(f"Replacing value with Null")
            validated_value = None
        case "INTEGER":
            value_adapter = TypeAdapter(int)

            # raises a ValidationError if incompatiable. make sure to catch in main.py
            validated_value = value_adapter.validate_python(value)
        case "REAL":
            value_adapter = TypeAdapter(float)

            # raises a ValidationError if incompatiable. make sure to catch in main.py
            validated_value = value_adapter.validate_python(value)
        case "TEXT":
            value_adapter = TypeAdapter(str)

            # raises a ValidationError if incompatiable. make sure to catch in main.py
            validated_value = "'" + value_adapter.validate_python(value) + "'"
        case "BLOB":
            value_adapter = TypeAdapter(bytes)

            # raises a ValidationError if incompatiable. make sure to catch in main.py
            validated_value = value_adapter.validate_python(value)
            
    # update the row
    cursor.execute(f"UPDATE {table_name} SET {col_name} = {validated_value} WHERE id = {row_id}")
    # log
    logger.debug(f"Updated row #{row_id} in {table_name}'s {col_name} value with {validated_value}")
