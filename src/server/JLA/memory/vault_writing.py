import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class LineIndexError(Exception):
    """Custom exception for line index errors in vault note editing."""
    pass


def safe_vault_path(vault: Path, relative_path: str) -> Path:
    vault = vault.resolve()
    target = (vault / relative_path).resolve()
    logger.debug("Resolved vault path for %s to %s", relative_path, target)

    if not target.is_relative_to(vault):
        logger.warning("Vault path escapes configured vault: %s", relative_path)
        raise ValueError("Path escapes the configured vault")

    return target

def write_vault_note(vault: Path, relative_path: str, content: str) -> None:
    try:
        target = safe_vault_path(vault, relative_path)
    except ValueError:
        logger.warning(
            "Invalid vault note path request: %s",
            relative_path,
        )
        raise
    
    target.parent.mkdir(parents=True, exist_ok=True)
    
    with open(target, "w", encoding="utf-8") as f:
        f.write(content.replace(r"\n", "\n").replace(r"\t", "\t"))

    logger.info("Wrote vault note: %s", relative_path)

def edit_vault_note(vault: Path, relative_path: str, line_to_edit: int, new_content: str) -> None:
    try:
        target = safe_vault_path(vault, relative_path)
    except ValueError:
        logger.warning(
            "Invalid vault note path request: %s",
            relative_path,
        )
        raise
    if not target.exists():
        logger.warning("Vault note not found for editing: %s", relative_path)
        raise FileNotFoundError(f"Note not found for editing: {relative_path}")

    with open(target, "r", encoding="utf-8") as file:
        lines = file.readlines()

    # Modify the specific line (ensure it ends with a newline character)
    try:
        lines[line_to_edit] = new_content.replace(r"\n", "\n").replace(r"\t", "\t") + "\n"
    except IndexError:
        # logger.warning("Line index out of bounds for editing: %s", relative_path)
        raise LineIndexError(f"Line index out of bounds for editing: {relative_path}")

    with open(target, "w", encoding="utf-8") as file:
        file.writelines(lines)

    logger.info("Edited vault note: %s", relative_path)