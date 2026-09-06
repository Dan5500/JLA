import sqlite3
from pathlib import Path

import pytest

import config.vaults as vault_config
from JLA.database.connection import initialize_database
from JLA.database import vault_sync


@pytest.fixture()
def vault_setup(tmp_path, monkeypatch):
    vault_root = tmp_path / "vault"
    vault_root.mkdir()
    config_path = tmp_path / "vaults.yaml"
    config_path.write_text(
        f"""vaults:
  test-vault:
    name: test-vault
    path: {vault_root.as_posix()}
    read: true
    write: true
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(vault_config, "CONFIG_PATH", config_path)
    return vault_root


@pytest.fixture()
def conn():
    connection = sqlite3.connect(":memory:")
    initialize_database(connection)
    return connection


def write_note(vault_root: Path, relative_path: str, content: str) -> Path:
    note_path = vault_root / relative_path
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(content, encoding="utf-8")
    return note_path


def read_note_row(connection: sqlite3.Connection, vault_name: str, file_path: str):
    cursor = connection.cursor()
    cursor.execute(
        "SELECT note_id, vault, file_path, file_hash, modified_time, file_size, title, index_status FROM notes WHERE vault = ? AND file_path = ?",
        (vault_name, file_path),
    )
    return cursor.fetchone()


def read_links(connection: sqlite3.Connection):
    cursor = connection.cursor()
    cursor.execute(
        "SELECT source_note_id, link_index, target_name, target_path, target_note_id FROM links ORDER BY link_index"
    )
    return cursor.fetchall()


def read_chunks(connection: sqlite3.Connection):
    cursor = connection.cursor()
    cursor.execute(
        "SELECT note_id, parent_chunk_id, chunk_index, name, start_line, end_line FROM chunks ORDER BY chunk_index"
    )
    return cursor.fetchall()


def test_new_note_insertion(vault_setup, conn):
    write_note(vault_setup, "alpha.md", "# Alpha\n\nBody\n")

    summaries = vault_sync.sync_all_vaults(conn)

    assert summaries[0].new == 1
    row = read_note_row(conn, "test-vault", "alpha.md")
    assert row is not None
    assert row[1] == "test-vault"
    assert row[2] == "alpha.md"
    assert row[6] == "alpha"
    assert row[7] == "indexed"
    assert read_links(conn) == []
    assert read_chunks(conn) == []


def test_unchanged_note_is_skipped(vault_setup, conn, monkeypatch):
    write_note(vault_setup, "alpha.md", "# Alpha\n\nBody\n")
    vault_sync.sync_all_vaults(conn)

    monkeypatch.setattr(
        vault_sync,
        "parse_markdown",
        lambda *_args, **_kwargs: pytest.fail("parse_markdown should not be called for unchanged notes"),
    )

    summaries = vault_sync.sync_all_vaults(conn)

    assert summaries[0].unchanged == 1
    row = read_note_row(conn, "test-vault", "alpha.md")
    assert row is not None


def test_changed_note_updates_links_and_hash(vault_setup, conn):
    write_note(vault_setup, "alpha.md", "# Alpha\n\n[[beta]]\n")
    write_note(vault_setup, "beta.md", "# Beta\n")
    write_note(vault_setup, "gamma.md", "# Gamma\n")

    vault_sync.sync_all_vaults(conn)
    first_row = read_note_row(conn, "test-vault", "alpha.md")
    first_hash = first_row[3]

    write_note(vault_setup, "alpha.md", "# Alpha\n\n[[gamma]]\n")
    summaries = vault_sync.sync_all_vaults(conn)

    assert summaries[0].changed == 1
    second_row = read_note_row(conn, "test-vault", "alpha.md")
    assert second_row is not None
    assert second_row[3] != first_hash
    links = read_links(conn)
    assert len(links) == 1
    assert links[0][3] == "gamma.md"


def test_deleted_note_is_removed(vault_setup, conn):
    note_path = write_note(vault_setup, "alpha.md", "# Alpha\n")
    vault_sync.sync_all_vaults(conn)

    note_path.unlink()
    summaries = vault_sync.sync_all_vaults(conn)

    assert summaries[0].deleted == 1
    assert read_note_row(conn, "test-vault", "alpha.md") is None
    assert read_links(conn) == []


def test_outgoing_links_are_replaced_without_duplicates(vault_setup, conn):
    write_note(vault_setup, "alpha.md", "# Alpha\n\n[[beta]]\n[[beta]]\n[[gamma]]\n")
    write_note(vault_setup, "beta.md", "# Beta\n")
    write_note(vault_setup, "gamma.md", "# Gamma\n")

    vault_sync.sync_all_vaults(conn)
    links = read_links(conn)

    assert len(links) == 2
    assert {row[3] for row in links} == {"beta.md", "gamma.md"}

    write_note(vault_setup, "alpha.md", "# Alpha\n\n[[gamma]]\n[[gamma]]\n")
    vault_sync.sync_all_vaults(conn)
    links = read_links(conn)

    assert len(links) == 1
    assert links[0][3] == "gamma.md"


def test_backlinks_follow_the_link_graph(vault_setup, conn):
    write_note(vault_setup, "alpha.md", "# Alpha\n\n[[beta]]\n")
    write_note(vault_setup, "beta.md", "# Beta\n")
    write_note(vault_setup, "gamma.md", "# Gamma\n")

    vault_sync.sync_all_vaults(conn)
    backlinks = vault_sync.get_backlinks(conn, "test-vault", "beta.md")
    assert [link.target_name for link in backlinks] == ["alpha.md"]

    write_note(vault_setup, "alpha.md", "# Alpha\n\n[[gamma]]\n")
    vault_sync.sync_all_vaults(conn)

    assert vault_sync.get_backlinks(conn, "test-vault", "beta.md") == []
    backlinks = vault_sync.get_backlinks(conn, "test-vault", "gamma.md")
    assert [link.target_name for link in backlinks] == ["alpha.md"]


def test_sync_rolls_back_on_failure(vault_setup, conn, monkeypatch):
    write_note(vault_setup, "alpha.md", "# Alpha\n\n[[beta]]\n")
    write_note(vault_setup, "beta.md", "# Beta\n")
    vault_sync.sync_all_vaults(conn)

    write_note(vault_setup, "alpha.md", "# Alpha\n\n[[gamma]]\n")
    write_note(vault_setup, "gamma.md", "# Gamma\n")
    before_row = read_note_row(conn, "test-vault", "alpha.md")
    before_links = read_links(conn)

    def failing_replace_links(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(vault_sync, "_replace_links", failing_replace_links)

    summaries = vault_sync.sync_all_vaults(conn)

    assert summaries[0].errors
    after_row = read_note_row(conn, "test-vault", "alpha.md")
    after_links = read_links(conn)
    assert after_row == before_row
    assert after_links == before_links


def test_malformed_links_do_not_break_sync(vault_setup, conn):
    write_note(vault_setup, "alpha.md", "# Alpha\n\n[[\n[[   ]]\n[[beta]]\n")
    write_note(vault_setup, "beta.md", "# Beta\n")

    summaries = vault_sync.sync_all_vaults(conn)

    assert not summaries[0].errors
    links = read_links(conn)
    assert len(links) == 1
    assert links[0][3] == "beta.md"
