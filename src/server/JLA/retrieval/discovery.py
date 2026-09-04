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
    for note in vault_path.rglob("*.md"):
        if(note.stem == note_name):
            return note
    return None
# eventually use this to create a database table of the md files
# and each note would have their own list of metadata
# metadata being from parsing it
