from pathlib import Path
import logging

from permissions import get_readable_vault_path

logger = logging.getLogger(__name__)

# find all notes in a vault
# returns a generator
# u need to use next() to access the things in it
def find_all_notes(vault_name: str):
    vault_path = get_readable_vault_path(vault_name)
    notes = vault_path.rglob("*.md")
    return notes

def find_note_path(vault_name: str, note_name: str) -> Path | None:
    vault_path = get_readable_vault_path(vault_name)
    requested = Path(note_name.strip())
    if requested.suffix == "":
        requested = requested.with_suffix(".md")

    # check root directory first, to avoid unnecessary recursion
    # also, obsidian automatically changes the link name to the directory its in, if there's multiple notes of the same name
    # so this avoids the case where it finds the wrong note in a subdirectory
    candidate = (vault_path / requested).resolve()
    if candidate.is_file() and candidate.is_relative_to(vault_path):
        return candidate

    # there might be a better way to search for the note, but this is a simple approach for now
    for note in vault_path.rglob("*.md"):
        if note.stem == requested.stem or note.relative_to(vault_path).as_posix() == requested.as_posix():
            return note
    return None
