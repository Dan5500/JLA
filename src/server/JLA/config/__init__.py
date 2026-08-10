from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

SERVER_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = SERVER_DIR / "config"


class ConfigError(Exception):
    """Base class for configuration loading errors."""


class ConfigFileMissingError(ConfigError, FileNotFoundError):
    """Raised when a required runtime config file is missing."""


class ConfigMalformedError(ConfigError, ValueError):
    """Raised when a configuration file cannot be parsed or has invalid structure."""


def resolve_config_path(config_path: str | Path) -> Path:
    path = Path(config_path)
    if not path.is_absolute():
        path = CONFIG_DIR / path

    if not path.exists():
        example_path = (
            path.with_suffix(".example.yaml")
            if path.suffix == ".yaml"
            else path.with_name(f"{path.name}.example.yaml")
        )
        raise ConfigFileMissingError(
            f"Missing config file: {path}. "
            f"Copy {example_path.name} to {path.name} and configure it for this machine."
        )

    return path


def load_yaml_config(config_path: str | Path) -> dict[str, Any]:
    config_path = resolve_config_path(config_path)

    with open(config_path, "r", encoding="utf-8") as config_file:
        try:
            config = yaml.safe_load(config_file)
        except yaml.YAMLError as exc:
            raise ConfigMalformedError(
                f"Malformed YAML in config file: {config_path}"
            ) from exc

    if config is None:
        return {}
    if not isinstance(config, dict):
        raise ConfigMalformedError(f"Malformed config: {config_path}")

    return config
