import pathlib

import pytest

from JLA.config import ConfigFileMissingError, ConfigMalformedError, load_yaml_config
from JLA.config.vaults import CONFIG_PATH, get_vault, load_vault_config


def test_runtime_config_file_is_loaded_not_example(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "vaults.example.yaml").write_text(
        "vaults:\n  placeholder:\n    name: placeholder\n    path: /tmp\n    read: true\n    write: false\n",
        encoding="utf-8",
    )

    monkeypatch.setattr("JLA.config.CONFIG_DIR", config_dir)

    with pytest.raises(ConfigFileMissingError, match="Missing config file:"):
        load_yaml_config("vaults.yaml")


def test_missing_runtime_config_message_is_actionable(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    monkeypatch.setattr("JLA.config.CONFIG_DIR", config_dir)

    with pytest.raises(ConfigFileMissingError, match="Copy vaults.example.yaml to vaults.yaml"):
        load_yaml_config("vaults.yaml")


def test_malformed_vault_config_is_rejected(monkeypatch, tmp_path):
    temp_config = tmp_path / "vaults.yaml"
    temp_config.write_text("vaults:\n  bad: [unclosed", encoding="utf-8")

    monkeypatch.setattr("JLA.config.vaults.CONFIG_PATH", temp_config)

    with pytest.raises(ConfigMalformedError, match="Malformed YAML"):
        load_vault_config()


def test_runtime_vault_path_values_are_loaded_from_runtime_config():
    vault_config = get_vault("assistant-memory")

    assert isinstance(vault_config["path"], str)
    assert "assistant-memory" in vault_config["name"]


def test_example_files_exist_and_do_not_contain_local_paths():
    base_dir = pathlib.Path(__file__).resolve().parents[1]
    config_dir = base_dir / "config"

    assert (config_dir / "vaults.example.yaml").exists()
    assert (config_dir / "models.example.yaml").exists()
    assert (config_dir / "permissions.example.yaml").exists()
    assert (config_dir / "app.example.yaml").exists()

    assert "/home/daniel" not in (config_dir / "vaults.example.yaml").read_text()
    assert "/home/daniel" not in (config_dir / "models.example.yaml").read_text()
    assert "/home/daniel" not in (config_dir / "permissions.example.yaml").read_text()
    assert "/home/daniel" not in (config_dir / "app.example.yaml").read_text()


def test_env_example_contains_placeholder_keys_only():
    base_dir = pathlib.Path(__file__).resolve().parents[1]
    env_example = base_dir / ".env.example"

    assert env_example.exists()

    contents = env_example.read_text().splitlines()
    assert "OPENAI_API_KEY=" in contents
    assert "ANTHROPIC_API_KEY=" in contents
    assert all(
        line == "OPENAI_API_KEY=" or line == "ANTHROPIC_API_KEY=" or not line.startswith("OPENAI_API_KEY=") and not line.startswith("ANTHROPIC_API_KEY=")
        for line in contents
    )
