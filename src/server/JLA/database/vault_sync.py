from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from dataclasses import dataclass, field
from itertools import count
from pathlib import Path

from ..config.vaults import list_readable_vault_names
from ..permissions import get_readable_vault_path
from ..retrieval import Chunk, Link, Note
from ..retrieval.parsing import parse_markdown

logger = logging.getLogger(__name__)

# slots = True optimizes effiency and key lookup
@dataclass(slots=True)
class VaultSyncSummary:
    vault_name: str
    scanned: int = 0
    new: int = 0
    changed: int = 0
    unchanged: int = 0
    deleted: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass(slots=True)
class NoteRecord:
    note_id: int
    file_hash: str
    modified_time: float
    file_size: int
    index_status: str

# the underscore in the method name is the same as type hinting a private method
# there are no private methods in python, so this kinda shows that the method is meant to be private
# hashing makes it so you can easily tell if a file has been changed
# the hashcode for a file fully changes by the tiniest edit
def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _relative_note_path(vault_root: Path, file: Path) -> str:
    return file.resolve().relative_to(vault_root.resolve()).as_posix()

# gets the meant target from a link regular expression match
# in obsidian, if there is multiple notes of the same name, itll give the relative path to it before a |
def _normalize_link_target(raw_target: str) -> str:
    target = raw_target.strip()
    if "|" in target:
        target = target.split("|", 1)[0].strip()
    if "#" in target:
        target = target.split("#", 1)[0].strip()
    return target

# get all notes and their data from the database, return a dict of it all
def _load_note_records(conn: sqlite3.Connection, vault_name: str) -> dict[str, NoteRecord]:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT note_id, file_path, file_hash, modified_time, file_size, index_status
        FROM notes
        WHERE vault = ?
        """,
        (vault_name,),
    )

    records: dict[str, NoteRecord] = {}
    for note_id, file_path, file_hash, modified_time, file_size, index_status in cursor.fetchall():
        records[str(file_path)] = NoteRecord(
            note_id=int(note_id),
            file_hash=str(file_hash),
            modified_time=float(modified_time),
            file_size=int(file_size),
            index_status=str(index_status),
        )
    return records


def _resolve_link_target(
    current_paths: dict[str, Path],
    current_paths_by_stem: dict[str, list[str]],
    raw_target: str,
) -> str | None:
    normalized_target = _normalize_link_target(raw_target)
    # can only happen if raw_target = ""
    if not normalized_target:
        return None

    candidate = Path(normalized_target)
    candidate_paths = [candidate.as_posix()]
    if candidate.suffix == "":
        candidate_paths.append(candidate.with_suffix(".md").as_posix())

    for candidate_path in candidate_paths:
        if candidate_path in current_paths:
            return candidate_path

    stem_matches = current_paths_by_stem.get(candidate.stem, [])
    if len(stem_matches) == 1:
        return stem_matches[0]

    return None


def _upsert_note_metadata(
    conn: sqlite3.Connection,
    note: Note,
    file_hash: str,
    modified_time: float,
    file_size: int,
) -> int:
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO notes (
            vault,
            file_path,
            file_hash,
            modified_time,
            file_size,
            title,
            metadata_json,
            index_status,
            last_indexed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 'indexed', CURRENT_TIMESTAMP)
        ON CONFLICT(vault, file_path) DO UPDATE SET
            file_hash = excluded.file_hash,
            modified_time = excluded.modified_time,
            file_size = excluded.file_size,
            title = excluded.title,
            metadata_json = excluded.metadata_json,
            index_status = excluded.index_status,
            last_indexed_at = CURRENT_TIMESTAMP
        """,
        (
            note.vault,
            note.location,
            file_hash,
            modified_time,
            file_size,
            note.name,
            json.dumps(note.metadata, default=str, sort_keys=True),
        ),
    )

    cursor.execute(
        "SELECT note_id FROM notes WHERE vault = ? AND file_path = ?",
        (note.vault, note.location),
    )
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError("note upsert failed")
    return int(row[0])


def _insert_chunk_tree(
    cursor: sqlite3.Cursor,
    note_id: int,
    chunk: Chunk,
    chunk_index: int,
    parent_chunk_id: int | None,
    counter: count,
    lines: list[str],
) -> None:
    chunk_text = "\n".join(lines[chunk.start_line - 1:chunk.end_line])
    content_hash = _hash_bytes(chunk_text.encode("utf-8"))
    cursor.execute(
        """
        INSERT INTO chunks (
            note_id,
            parent_chunk_id,
            chunk_index,
            name,
            heading_path,
            start_line,
            end_line,
            content_hash
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            note_id,
            parent_chunk_id,
            chunk_index,
            chunk.name,
            chunk.heading_path,
            chunk.start_line,
            chunk.end_line,
            content_hash,
        ),
    )
    current_chunk_id = int(cursor.lastrowid)
    for subchunk in chunk.subchunks:
        _insert_chunk_tree(cursor, note_id, subchunk, next(counter), current_chunk_id, counter, lines)


def _replace_chunks(conn: sqlite3.Connection, note_id: int, chunks: list[Chunk], content: str) -> None:
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chunks WHERE note_id = ?", (note_id,))
    chunk_counter = count()
    lines = content.splitlines()
    for chunk in chunks:
        _insert_chunk_tree(cursor, note_id, chunk, next(chunk_counter), None, chunk_counter, lines)


def _replace_links(
    conn: sqlite3.Connection,
    note: Note,
    note_id: int,
    links: list[Link],
    current_paths: dict[str, Path],
    current_paths_by_stem: dict[str, list[str]],
) -> None:
    cursor = conn.cursor()
    cursor.execute("DELETE FROM links WHERE source_note_id = ?", (note_id,))

    seen: set[tuple[str, str | None]] = set()
    link_index = 0
    for link in links:
        resolved_path = _resolve_link_target(current_paths, current_paths_by_stem, link.target_name)
        if resolved_path is None and link.target_path:
            resolved_path = link.target_path

        dedupe_key = (link.target_name, resolved_path)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        target_note_id = None
        if resolved_path is not None:
            cursor.execute(
                "SELECT note_id FROM notes WHERE vault = ? AND file_path = ?",
                (note.vault, resolved_path),
            )
            target_row = cursor.fetchone()
            if target_row is not None:
                target_note_id = int(target_row[0])

        cursor.execute(
            """
            INSERT INTO links (
                source_note_id,
                link_index,
                target_name,
                target_path,
                target_note_id,
                target_section
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                note_id,
                link_index,
                link.target_name,
                resolved_path,
                target_note_id,
                link.target_section,
            ),
        )
        link_index += 1


def _sync_note(
    conn: sqlite3.Connection,
    vault_name: str,
    file: Path,
    note_record: NoteRecord | None,
    current_paths: dict[str, Path],
    current_paths_by_stem: dict[str, list[str]],
) -> tuple[str, int | None]:
    data = file.read_bytes()
    file_hash = _hash_bytes(data)
    stat = file.stat()

    if note_record is not None and note_record.file_hash == file_hash and note_record.index_status == "indexed":
        return "unchanged", note_record.note_id

    content = data.decode("utf-8")
    note = parse_markdown(file, content)

    with conn:
        note_id = _upsert_note_metadata(conn, note, file_hash, stat.st_mtime, stat.st_size)
        _replace_links(conn, note, note_id, note.links, current_paths, current_paths_by_stem)
        _replace_chunks(conn, note_id, note.chunks, content)

    return ("new" if note_record is None else "changed"), note_id


def _resolve_link_ids(conn: sqlite3.Connection, vault_name: str) -> None:
    """Resolve forward links after every note in a vault has been inserted."""
    with conn:
        conn.execute(
            """
            UPDATE links
            SET target_note_id = (
                SELECT target.note_id
                FROM notes AS source
                JOIN notes AS target
                  ON target.vault = source.vault
                 AND target.file_path = links.target_path
                WHERE source.note_id = links.source_note_id
            )
            WHERE source_note_id IN (SELECT note_id FROM notes WHERE vault = ?)
            """,
            (vault_name,),
        )


def sync_vault(conn: sqlite3.Connection, vault_name: str, full_rebuild: bool = False) -> VaultSyncSummary:
    vault_root = get_readable_vault_path(vault_name)
    summary = VaultSyncSummary(vault_name=vault_name)

    current_files: dict[str, Path] = {}
    current_paths_by_stem: dict[str, list[str]] = {}
    for file in sorted(vault_root.rglob("*.md")):
        if not file.is_file():
            continue
        relative_path = _relative_note_path(vault_root, file)
        current_files[relative_path] = file.resolve()
        current_paths_by_stem.setdefault(file.stem, []).append(relative_path)

    existing_records = _load_note_records(conn, vault_name)

    if full_rebuild:
        with conn:
            conn.execute("DELETE FROM notes WHERE vault = ?", (vault_name,))
        existing_records = {}
    else:
        stale_paths = sorted(set(existing_records) - set(current_files))
        for stale_path in stale_paths:
            with conn:
                conn.execute(
                    "DELETE FROM notes WHERE vault = ? AND file_path = ?",
                    (vault_name, stale_path),
                )
            summary.deleted += 1

    for relative_path, file in current_files.items():
        summary.scanned += 1
        note_record = existing_records.get(relative_path)
        try:
            status, _ = _sync_note(
                conn,
                vault_name,
                file,
                note_record,
                current_files,
                current_paths_by_stem,
            )
            match status:
                case "new":
                    summary.new += 1
                case "changed":
                    summary.changed += 1
                case _:
                    summary.unchanged += 1
        except Exception as exc:
            logger.exception("Failed to sync note %s/%s", vault_name, relative_path)
            summary.errors.append(f"{vault_name}/{relative_path}: {exc}")

    _resolve_link_ids(conn, vault_name)

    logger.debug("Vault sync summary for %s: %s", vault_name, summary)
    return summary


def sync_all_vaults(conn: sqlite3.Connection, full_rebuild: bool = False) -> list[VaultSyncSummary]:
    summaries: list[VaultSyncSummary] = []
    for vault_name in list_readable_vault_names():
        summaries.append(sync_vault(conn, vault_name, full_rebuild=full_rebuild))
    return summaries

# use this to get backlinks for any note
def get_backlinks(conn: sqlite3.Connection, vault_name: str, file_path: str) -> list[Link]:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT source.vault, source.file_path, links.target_name
        FROM links
        JOIN notes AS source ON source.note_id = links.source_note_id
        JOIN notes AS target
            ON target.vault = source.vault
           AND target.file_path = links.target_path
        WHERE target.vault = ?
          AND target.file_path = ?
        ORDER BY source.file_path, links.link_index
        """,
        (vault_name, file_path),
    )

    backlinks: list[Link] = []
    for source_vault, source_path, target_name in cursor.fetchall():
        backlinks.append(Link(target_name=source_path, target_path=source_path, parent_path=source_vault))
    return backlinks
