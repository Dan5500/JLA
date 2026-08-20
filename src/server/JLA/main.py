# imports
import logging
import os
import sys
import pathlib
import readline # enable arrow key usage
import pytest
import shlex

from logging_config import setup_logging
from retrieval.vault_reading import read_vault_note
from config import ConfigFileMissingError, ConfigMalformedError
from permissions import get_readable_vault_path, get_writable_vault_path, list_readable_vault_names, list_writable_vault_names
from memory.vault_writing import LineIndexError, write_vault_note, edit_vault_note
from database.handling import list_db_tables, read_db_table, insert_row, get_schema, read_row, update_row
from database.connection import get_connection, initialize_database

script_dir = pathlib.Path(__file__).resolve().parent
PROJECT_ROOT = script_dir.parent
TESTS_DIR = PROJECT_ROOT / "tests"

logger = logging.getLogger(__name__)

def main() -> None:
    """
        Top level function to run the JLA server.
    """
    setup_logging()
    logger.info("JLA started")
    print("Welcome to the JLA server!\nThis is a temporary CLI for setting up the JLA backend.\nType 'help' for a list of commands")

    # maybe create connections on command input, but for now, 
    # the connection to the database is created at the start of the server and closed at the end
    
    # initalize and get database connection
    conn = get_connection()
    initialize_database(conn)

    alive = True

    while alive:
        command = input("> ")
        try:
            command = shlex.split(command)
        except ValueError as e:
            logger.error("Error parsing command: %s", e)
            # print(f"Error parsing command: {e}")
            continue
        try:
            match command[0]:
                # "help" command to display available commands
                case "help":
                    print(
                        "Available commands:\n"
                        "\thelp - displays this help message\n"
                        "\tclear - clears the terminal screen\n"
                        "\texit [-f] - exits the server\n"
                        "\t\t-f - force exit without confirmation\n"
                        "\tquit [-f] - alias for exit\n"
                        "\tclose [-f] - alias for exit\n"
                        "\ttest <command/test> - runs test commands\n"
                        "\t\tlist - lists available tests\n"
                        "\t\ttest-all - runs the full test suite\n"
                        "\tread <command> - reads data from specified source\n"
                        "\t\tvault <vault_name> <note_relative_path> - reads a note from the specified vault\n"
                        "\t\tdatabase <table_name> - reads data from the specified database table\n"
                        "\twrite <command> - writes data to specified destination\n"
                        "\t\tvault <vault_name> <note_relative_path> <content> - writes a note to the specified vault\n"
                        "\tedit <command> - edit an existing note in the vault\n"
                        "\t\tvault <vault_name> <note_relative_path> <line_number> <new_content> - edits a specific line in a note\n"
                    )
                # "exit" or "quit" command to exit the server
                case "exit" | "quit" | "close":
                    try:
                        match command[1]:
                            case "-f":
                                logger.info("Force exit requested")
                                print("Force exiting JLA server...")
                                sys.exit(0)
                            case _:
                                print("invalid argument(s)")
                    except IndexError:
                        print("Are you sure you want to exit? (y/n)")
                        confirm = input("? ")
                        if confirm.lower() in ["y", "yes"]:
                            logger.info("JLA shutting down normally")
                            print("Exiting JLA server...")
                            alive = False

                case "clear":
                        os.system('cls' if os.name == 'nt' else 'clear')

                # "test" command for running tests
                case "test":
                    try:
                        match command[1]:
                            case "list":
                                print(
                                    "Available test groups:\n"
                                    "\tdatabase - database tests in tests/test_database.py\n"
                                    "\tvault - vault handling tests in tests/test_vault.py\n"
                                    "\tconfig - configuration loading tests in tests/test_config.py\n"
                                    "\ttest-all - runs the full test suite\n"
                                )
                            case "test-all":
                                print("Running all tests...")
                                pytest.main([str(TESTS_DIR)])
                            case "vault":
                                print("Running vault tests from tests/test_vault.py...")
                                pytest.main([str(TESTS_DIR / "test_vault.py")])
                            case "database":
                                print("Running database tests from tests/test_database.py...")
                                pytest.main([str(TESTS_DIR / "test_database.py")])
                            case "config":
                                print("Running config tests from tests/test_config.py...")
                                pytest.main([str(TESTS_DIR / "test_config.py")])
                            case _:
                                print(f"Unknown test command: {command[1]}")
                    except IndexError:
                        print("Usage: \n\t test <test/command> [args]\n\nCommands:\n\tlist - lists available tests/groups\n\ttest-all - runs all tests\n\ttest-database - runs the database test group\nArguments:\n\tnone yet!")
                case "read":
                    try:
                        match command[1]:
                            case "vault":
                                try:
                                    vault_name = command[2]
                                    note_path = command[3]
                                except IndexError:
                                    print("Usage: read vault <vault_name> <note_relative_path>")
                                    print("Available readable vaults:")
                                    for vault_name in list_readable_vault_names():
                                        print(f"\t{vault_name}")
                                    continue

                                try:
                                    vault_path = get_readable_vault_path(vault_name)
                                except KeyError:
                                    print(f"Unknown vault: {vault_name}")
                                    print("Available readable vaults:")
                                    for vault_name in list_readable_vault_names():
                                        print(f"\t{vault_name}")
                                    continue
                                except PermissionError:
                                    print(f"Read access is disabled for vault: {vault_name}")
                                    continue

                                try:
                                    content = read_vault_note(vault_path, note_path)
                                    print(f"Content of {note_path}:\n{content}")
                                except ValueError:
                                    print("Invalid note path: path traversal outside the vault is not allowed.")
                                except FileNotFoundError:
                                    print(f"Note not found: {note_path}")
                            case _:
                                print(f"Unknown read command: {command[1]}")
                    except IndexError:
                        print("Usage: read <read/command> [args]\n\nCommands:\n\tvault - reads a note from the vault\nArguments:\n\tvault <vault_name> <note_relative_path> - reads the specified note from the configured vault")

                case "write":
                    try:
                        match command[1]:
                            case "vault":
                                try:
                                    vault_name = command[2]
                                    note_path = command[3]
                                    content = command[4]

                                    raiseit = False # there's def a better way to do this
                                    try:
                                        command[5]
                                        raiseit = True
                                        # make sure the user uses quotes around the content; 
                                        # if they don't, this will raise an IndexError 
                                        # we can catch it to give a better error message
                                    except IndexError:
                                        pass
                                    if raiseit:
                                        raise IndexError
                                    write_vault_note(get_writable_vault_path(vault_name), note_path, content)
                                    print(f"Wrote note to {vault_name}/{note_path}")
                                except KeyError:
                                    print(f"Unknown vault: {vault_name}")
                                    print("Available writable vaults:")
                                    for vault_name in list_writable_vault_names():
                                        print(f"\t{vault_name}")
                                except PermissionError:
                                    print(f"Write access is disabled for vault: {vault_name}")
                                except ValueError:
                                    print("Invalid note path: path traversal outside the vault is not allowed.")
                                except IndexError:
                                    print("Usage: write vault <vault_name> <note_relative_path> <content>")
                                    print("--- MAKE SURE TO USE QUOTES AROUND THE CONTENT AND NOTE PATH IF THEY CONTAIN SPACES! ---")
                                    print("Available writable vaults:")
                                    for vault_name in list_writable_vault_names():
                                        print(f"\t{vault_name}")
                                    continue
                            case _:
                                print(f"Unknown write command: {command[1]}")
                    except IndexError:
                        print('''Usage: write <write/command> [args]\n\nCommands:\n\tvault - writes a note to the vault\nArguments:\n\tvault <vault_name> <note_relative_path> <content> - writes the specified content to the specified note in the configured vault''')

                case "edit":
                    try:
                        match command[1]:
                            case "vault":
                                try:
                                    vault_name = command[2]
                                    note_path = command[3]
                                    line_number = int(command[4])
                                    new_content = command[5]

                                    raiseit = False # there's def a better way to do this
                                    try:
                                        command[6]
                                        raiseit = True
                                    except IndexError:
                                        pass
                                    if raiseit:
                                        raise IndexError
                                    edit_vault_note(get_writable_vault_path(vault_name), note_path, line_number-1, new_content)
                                    print(f"Edited line {line_number} of note {vault_name}/{note_path}")
                                except KeyError:
                                    print(f"Unknown vault: {vault_name}")
                                    print("Available writable vaults:")
                                    for vault_name in list_writable_vault_names():
                                        print(f"\t{vault_name}")
                                except PermissionError:
                                    print(f"Write access is disabled for vault: {vault_name}")
                                except ValueError:
                                    print("Invalid note path: path traversal outside the vault is not allowed.")
                                except FileNotFoundError:
                                    print(f"Note not found: {note_path}")
                                except LineIndexError:
                                    print(f"Line index out of bounds for editing: {note_path}")
                                    print("Make sure the line number is valid for the specified note.")
                                except IndexError:
                                    print("Usage: edit vault <vault_name> <note_relative_path> <line_number> <new_content>")
                                    print("--- MAKE SURE TO USE QUOTES AROUND THE CONTENT AND NOTE PATH IF THEY CONTAIN SPACES! ---")
                                    print("Available writable vaults:")
                                    for vault_name in list_writable_vault_names():
                                        print(f"\t{vault_name}")
                            case _:
                                print(f"Unknown edit command: {command[1]}")
                    except IndexError:
                        print("Usage: edit <edit/command> [args]\n\nCommands:\n\tvault - edits a note in the vault\nArguments:\n\tvault <vault_name> <note_relative_path> <line_number> <new_content> - edits the specified line in the specified note in the configured vault")

                case "database":
                    try:
                        match command[1]:
                            case "list-tables":
                                print(list_db_tables(conn))

                            case "schema":
                                table_name = command[2]
                                print(get_schema(conn, table_name))

                            case "read-table":
                                try:
                                    table_name = command[2]
                                    print(read_db_table(conn, table_name))
                                except ValueError as e:
                                    print(f"ValueError: {e}")
                                except IndexError:
                                    print("Usage: read database <table_name>")
                                    print(list_db_tables(conn))

                            case "insert-row":
                                table_name = command[2]
                                i = 3
                                # get parameters (this is a cooked method, fix it ltr; works for now)
                                values = []
                                while i<len(command):
                                    values.append(command[i])
                                    i = i+1

                                # insert row & give feedback if fails
                                try:
                                    insert_row(conn, table_name, values)

                                    print("Do you want to save? y/n")
                                    print(f"inputted values: {read_row(conn, table_name)}")
                                    answer = input("? ")
                                    if answer.lower() in ["y", "yes"]:
                                        conn.commit()
                                except Exception as e:
                                    print(f"Error: {e}")

                            case "update-row":
                                table_name = command[2]
                                row_id = command[3]
                                col_name = command[4]
                                value = command[5]

                                # update row & give feedback if fails
                                try:
                                    update_row(conn, table_name, row_id, col_name, value)

                                    print("Do you want to save? y/n")
                                    print(f"inputted values: {read_row(conn, table_name, row_id)}")
                                    answer = input("? ")
                                    if answer.lower() in ["y", "yes"]:
                                        conn.commit()
                                except Exception as e:
                                    print(f"Error: {e}")

                            case "save":
                                print("Are you sure? This cannot be undone. y/n")
                                answer = input("? ")
                                if answer.lower() in ["y", "yes"]:
                                    conn.commit()

                            case "reload":
                                print("All unsaved changes will be deleted. Are you sure? y/n")
                                answer = input("? ")
                                if answer.lower() in ["y", "yes"]:
                                    print("Reloading database...")
                                    conn = get_connection()

                            case "read-row":
                                table_name = command[2]
                                try:
                                    try:
                                        row_id = command[3]
                                        print(read_row(conn, table_name, row_id))
                                    except IndexError:
                                        print(read_row(conn, table_name))
                                except Exception as e:
                                    print(e)

                    except IndexError:
                        print('''Usage: database <command> [args]

Commands:
    save - saves all changes made to database
    reload - trashes all unsaved changes
    list-tables - lists all available tables
    schema - describes the schema for a specific table
    insert-row - inserts a row into a specified table
    update-row - updates a specified row in a specified table
    read-table - reads all rows in a table
    read-row - reads a specified row in a specified table. If no row id is specified, the latest row is read
Arguments:
    schema <table_name> 
    insert-row <table_name> <value1> <value2> <value3>...
        MAKE SURE THE DATA TYPES ARE RIGHT FOR THE TABLE'S SCHEMA
        to view a tables schema, run the schema subcommand
    update-row <table_name> <row_id> <col_name> <value>
        MAKE SURE THE DATA TYPES ARE RIGHT FOR THE TABLE'S SCHEMA
    read-table <table_name>
    read-row <table_name> [row_id]''')

                case _:
                    logger.debug("Unknown CLI command received: %s", command)
                    print(f"Unknown command: {command}")
        
        except (ConfigFileMissingError, ConfigMalformedError) as exc:
            logger.error("Configuration error: %s", exc, exc_info=True)
            print(exc)
        except IndexError:
            print("No command entered. Please enter a command.")


if __name__ == "__main__":
    #start_backend() - backend doesnt really exist as of rn
    # i've just been making a CLI to test all the tools that I make
    main()
else:
    print("not running the CLI, starting only backend server")
    # not yet implemented btw. 
    # in order to get to this point, you'd run "import main" in another file
    # and it'll start running everything in this else block.
    # the move is to make another function that does everything
    # it'll be smth like so:
    
    #start_backend()