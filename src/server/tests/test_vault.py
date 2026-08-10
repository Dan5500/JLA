import pathlib

import pytest

from JLA.config.vaults import (
    get_readable_vault_path,
    get_vault,
    list_readable_vault_names,
)
from JLA.retrieval.vault_handling import read_vault_note, safe_vault_path


def test_safe_vault_path():
    vault_path = get_readable_vault_path("assistant-memory")
    assert safe_vault_path(vault_path, "test.md") == (vault_path / "test.md").resolve()

    with pytest.raises(ValueError):
        safe_vault_path(vault_path, "../outside.md")


def test_read_vault_note():
    vault_path = get_readable_vault_path("assistant-memory")

    content = read_vault_note(vault_path, "test.md")
    assert content == "if you see this, you're successfully reading this note. I guess that's a bit obvious."

    with pytest.raises(FileNotFoundError):
        read_vault_note(vault_path, "non_existent.md")


def test_config_resolves_vault_paths():
    assistant_vault = get_vault("assistant-memory")
    personal_vault = get_vault("personal")

    assert assistant_vault["name"] == "assistant-memory"
    assert personal_vault["name"] == "personal"
    assert isinstance(pathlib.Path(assistant_vault["path"]), pathlib.Path)
    assert isinstance(pathlib.Path(personal_vault["path"]), pathlib.Path)


def test_list_readable_vault_names_contains_configured_vaults():
    readable_vaults = list_readable_vault_names()
    assert "assistant-memory" in readable_vaults
    assert "personal" in readable_vaults


def test_get_vault_unknown_name_raises_key_error():
    with pytest.raises(KeyError):
        get_vault("unknown-vault")


def test_read_permission_respected(monkeypatch, tmp_path):
    temp_config = tmp_path / "vaults.yaml"
    temp_config.write_text(
        "vaults:\n  no-read:\n    name: \"no-read\"\n    path: \"/tmp\"\n    read: false\n",
        encoding="utf-8",
    )

    monkeypatch.setattr("JLA.config.vaults.CONFIG_PATH", temp_config)

    with pytest.raises(PermissionError):
        get_readable_vault_path("no-read")