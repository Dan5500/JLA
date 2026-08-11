from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def safe_vault_path(vault: Path, relative_path: str) -> Path:
    vault = vault.resolve()
    target = (vault / relative_path).resolve()
    logger.debug("Resolved vault path for %s to %s", relative_path, target)

    if not target.is_relative_to(vault):
        logger.warning("Vault path escapes configured vault: %s", relative_path)
        raise ValueError("Path escapes the configured vault")

    return target

def read_vault_note(vault: Path, relative_path: str) -> str:
    try:
        target = safe_vault_path(vault, relative_path)
    except ValueError:
        logger.warning(
            "Invalid vault note path request: %s",
            relative_path,
        )
        raise
    if not target.exists():
        logger.warning("Vault note not found: %s", relative_path)
        raise FileNotFoundError(f"Note not found: {relative_path}")

    logger.info("Reading vault note: %s", relative_path)
    with open(target, "r", encoding="utf-8") as f:
        return f.read()

