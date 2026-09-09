import sqlite3

import pytest

import JLA.config.vaults as vault_config
from JLA.database.connection import initialize_database
from JLA.database.vault_sync import sync_vault
from JLA.retrieval.retriever import RetrievalResult, retrieve_notes


@pytest.fixture()
def vault(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    root.mkdir()
    config = tmp_path / "vaults.yaml"
    config.write_text(f"vaults:\n  test:\n    path: {root}\n    read: true\n    write: true\n", encoding="utf-8")
    monkeypatch.setattr(vault_config, "CONFIG_PATH", config)
    return root


@pytest.fixture()
def conn():
    connection = sqlite3.connect(":memory:")
    initialize_database(connection)
    return connection


def write(vault, path, content):
    target = vault / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def index(conn, vault):
    summary = sync_vault(conn, "test")
    assert not summary.errors


def test_filename_title_and_body_search_rank_sections(conn, vault):
    write(vault, "projects/launch-plan.md", "# Overview\nNothing here.\n\n## Risks\nThe lunar launch window is narrow.\n")
    write(vault, "archive.md", "# Archive\nlaunch is mentioned here too.\n")
    index(conn, vault)

    filename = retrieve_notes(conn, "launch-plan", "test")
    assert filename.results[0].file_path == "projects/launch-plan.md"
    assert filename.results[0].title == "launch-plan"

    result = retrieve_notes(conn, "lunar", "test")
    assert result.total == 1
    chunk = result.results[0].chunks[0]
    assert chunk.name == "Risks"
    assert chunk.heading_path == "Overview > Risks"
    assert "lunar" in chunk.content.lower()
    assert chunk.content_hash
    assert any("section text match" in reason for reason in chunk.reasons)


def test_metadata_filters_are_flexible_and_vault_scoped(conn, vault):
    write(vault, "work.md", "---\ntags: [work, urgent]\nproject: atlas\n---\n# Work\nStatus\n")
    write(vault, "home.md", "---\ntags: home\n---\n# Home\nStatus\n")
    index(conn, vault)

    result = retrieve_notes(conn, "tag:work project:atlas", "test")
    assert [item.file_path for item in result.results] == ["work.md"]
    assert retrieve_notes(conn, "vault:other", "test").total == 0


def test_link_expansion_stays_in_vault_and_preserves_provenance(conn, vault):
    write(vault, "alpha.md", "# Alpha\nneedle\n[[beta#Details]]\n")
    write(vault, "beta.md", "# Beta\n## Details\nconnected information\n")
    index(conn, vault)

    result = retrieve_notes(conn, "needle", "test")
    assert [item.file_path for item in result.results] == ["alpha.md", "beta.md"]
    assert result.results[1].expansion_source == ["alpha.md"]


def test_retrieval_reads_files_but_never_writes_the_index(conn, vault):
    write(vault, "note.md", "# Note\nneedle\n")
    index(conn, vault)
    before = conn.execute("SELECT file_hash, last_indexed_at FROM notes").fetchall()
    writes = []
    conn.set_trace_callback(lambda sql: writes.append(sql) if sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) else None)

    result = retrieve_notes(conn, "needle", "test")

    conn.set_trace_callback(None)
    assert result.total == 1
    assert writes == []
    assert conn.execute("SELECT file_hash, last_indexed_at FROM notes").fetchall() == before


def test_empty_and_wrong_vault_queries_are_clean(conn, vault):
    write(vault, "note.md", "# Note\ncontent\n")
    index(conn, vault)
    assert isinstance(retrieve_notes(conn, "", "test"), RetrievalResult)
    assert retrieve_notes(conn, "content", None).total == 0
