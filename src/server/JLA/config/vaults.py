from pathlib import Path
from typing import Any

from . import ConfigMalformedError, load_yaml_config

SERVER_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = SERVER_DIR / "config" / "vaults.yaml"


def load_vault_config() -> dict[str, dict[str, Any]]:
    config = load_yaml_config(CONFIG_PATH)

    if "vaults" not in config:
        raise ConfigMalformedError(f"Malformed vault config: {CONFIG_PATH}")

    vaults = config["vaults"]
    if not isinstance(vaults, dict):
        raise ConfigMalformedError(f"Malformed vault config: {CONFIG_PATH}")

    return vaults


def get_vault(vault_name: str) -> dict[str, Any]:
    vaults = load_vault_config()
    if vault_name not in vaults:
        raise KeyError(vault_name)

    vault = vaults[vault_name]
    if not isinstance(vault, dict):
        raise ValueError(f"Invalid vault configuration for: {vault_name}")

    return vault


def list_readable_vault_names() -> list[str]:
    vaults = load_vault_config()
    return sorted(
        name
        for name, config in vaults.items()
        if isinstance(config, dict) and config.get("read") is True
    )


def get_vault_path(vault_name: str) -> Path:
    vault = get_vault(vault_name)
    path = vault.get("path")
    if not isinstance(path, str):
        raise ValueError(f"Invalid path for vault: {vault_name}")

    return Path(path)


def get_readable_vault_path(vault_name: str) -> Path:
    vault = get_vault(vault_name)

    if vault.get("read") is not True:
        raise PermissionError(vault_name)

    path = vault.get("path")

    if not isinstance(path, str):
        raise ValueError(f"Invalid path for vault: {vault_name}")

    return Path(path).resolve()