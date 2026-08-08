# imports
import os
import sys
import readline
import pytest


def main() -> None:
    """
        Top level function to run the JLA server.
    """
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
                        "\ttest <command> - runs test commands\n"
                        "\t\tlist - lists available tests\n"
                        "\t\ttest-all - runs the full test suite\n"
                    )
                # "exit" or "quit" command to exit the server
                case "exit" | "quit":
                    try:
                        match command[1]:
                            case "-f":
                                print("Force exiting JLA server...")
                                sys.exit(0)
                            case _:
                                print("invalid argument(s)")
                    except IndexError:
                        print("Are you sure you want to exit? (y/n)")
                        confirm = input("? ")
                        if confirm.lower() in ["y", "yes"]:
                            print("Exiting JLA server...")
                            alive = False

                case "clear":
                        os.system('cls' if os.name == 'nt' else 'clear')

                # "test" command for running tests
                case "test":
                    try:
                        match command[1]:
                            case "list":
                                print("there are none! hahah")
                            case "test-all":
                                pytest.main()
                                print("Running all tests...")
                            case _:
                                print(f"Executing test: {command[1]}")
                    except IndexError:
                        print("Usage: \n\t test <test/command> [args]\n\nCommands:\n\tlist - lists available tests\n\ttest-all - runs all tests\nArguments:\n\tnone yet!")

                case _:
                    print(f"Unknown command: {command}")
        except IndexError:
            print("No command entered. Please enter a command.")


if __name__ == "__main__":
    main()