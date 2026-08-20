import errno
from pathlib import Path
import logging

from config.vaults import get_vault, load_vault_config

logger = logging.getLogger(__name__)

def get_readable_vault_path(vault_name: str) -> Path:
    vault = get_vault(vault_name)

    if vault.get("read") is not True:
        logger.warning(f"Attempted read access is disabled for vault: {vault_name}")
        raise PermissionError(errno.EACCES, f"Read access is disabled for vault: {vault_name}")

    path = vault.get("path")

    if not isinstance(path, str):
        raise ValueError(f"Invalid path for vault: {vault_name}")

    return Path(path).resolve()

def get_writable_vault_path(vault_name: str) -> Path:
    vault = get_vault(vault_name)

    if vault.get("write") is not True:
        logger.warning(f"Attempted write access is disabled for vault: {vault_name}")
        raise PermissionError(errno.EACCES, f"Write access is disabled for vault: {vault_name}")

    path = vault.get("path")

    if not isinstance(path, str):
        raise ValueError(f"Invalid path for vault: {vault_name}")

    return Path(path).resolve()

def list_readable_vault_names() -> list[str]:
    vaults = load_vault_config()
    return sorted(
        name
        for name, config in vaults.items()
        if isinstance(config, dict) and config.get("read") is True
    )

def list_writable_vault_names() -> list[str]:
    vaults = load_vault_config()
    return sorted(
        name
        for name, config in vaults.items()
        if isinstance(config, dict) and config.get("write") is True
    )


# could add a function to check if a vault is readable or writable and return a boolean
# but for now, just use the above functions and catch the PermissionError if needed