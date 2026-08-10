# imports
import logging
import os
import sys
import pathlib
import readline
import pytest

from logging_config import setup_logging
from retrieval.vault_handling import read_vault_note
from JLA.config import ConfigFileMissingError, ConfigMalformedError
from config.vaults import get_readable_vault_path, list_readable_vault_names

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
    alive = True

    while alive:
        command = input("> ")
        command = command.split()
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
                        "\ttest <command> - runs test commands\n"
                        "\t\tlist - lists available tests\n"
                        "\t\ttest-all - runs the full test suite\n"
                        "\tread <command> - reads data from specified source\n"
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
                                    "\ttest-all - runs the full test suite\n"
                                )
                            case "test-all":
                                pytest.main([str(TESTS_DIR)])
                                print("Running all tests...")
                            case "vault":
                                pytest.main([str(TESTS_DIR / "test_vault.py")])
                                print("Running vault tests from tests/test_vault.py...")
                            case "database":
                                pytest.main([str(TESTS_DIR / "test_database.py")])
                                print("Running database tests from tests/test_database.py...")
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
                case _:
                    logger.debug("Unknown CLI command received: %s", command)
                    print(f"Unknown command: {command}")
        except (ConfigFileMissingError, ConfigMalformedError) as exc:
            logger.error("Configuration error: %s", exc, exc_info=True)
            print(exc)
        except IndexError:
            print("No command entered. Please enter a command.")


if __name__ == "__main__":
    main()