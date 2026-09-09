"""Read-only queries over the vault index.

The retriever reads Markdown section text from the vault files; this module never
stores or returns Markdown bodies.
"""

import json
import sqlite3
from collections import defaultdict
from typing import Any


def fetch_all_notes(conn: sqlite3.Connection, vault: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT note_id, vault, file_path, title, modified_time, metadata_json
        FROM notes WHERE vault = ? AND index_status = 'indexed'
        ORDER BY file_path
        """,
        (vault,),
    ).fetchall()
    notes = []
    for note_id, note_vault, file_path, title, modified_time, metadata_json in rows:
        try:
            metadata = json.loads(metadata_json or "{}")
        except (TypeError, json.JSONDecodeError):
            metadata = {}
        notes.append({"note_id": int(note_id), "vault": note_vault, "file_path": file_path,
                      "title": title, "modified_time": float(modified_time), "metadata": metadata})
    return notes


def fetch_chunks_for_note_ids(conn: sqlite3.Connection, note_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
    if not note_ids:
        return {}
    placeholders = ", ".join("?" for _ in note_ids)
    rows = conn.execute(
        f"""
        SELECT note_id, chunk_id, parent_chunk_id, chunk_index, name, heading_path,
               start_line, end_line, content_hash
        FROM chunks WHERE note_id IN ({placeholders})
        ORDER BY note_id, chunk_index
        """,
        note_ids,
    ).fetchall()
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[int(row[0])].append({
            "note_id": int(row[0]), "chunk_id": int(row[1]), "parent_chunk_id": row[2],
            "chunk_index": int(row[3]), "name": row[4], "heading_path": row[5],
            "start_line": int(row[6]), "end_line": int(row[7]), "content_hash": row[8],
        })
    return dict(grouped)


def fetch_related_note_ids(conn: sqlite3.Connection, seed_note_ids: list[int], vault: str) -> dict[int, list[int]]:
    if not seed_note_ids:
        return {}
    placeholders = ", ".join("?" for _ in seed_note_ids)
    rows = conn.execute(
        f"""
        WITH related AS (
            SELECT source_note_id AS note_id, target_note_id AS related_note_id
            FROM links WHERE source_note_id IN ({placeholders})
            UNION ALL
            SELECT target_note_id AS note_id, source_note_id AS related_note_id
            FROM links WHERE target_note_id IN ({placeholders})
        )
        SELECT related.note_id, related.related_note_id
        FROM related JOIN notes ON notes.note_id = related.related_note_id
        WHERE notes.vault = ? AND notes.index_status = 'indexed'
        """,
        seed_note_ids + seed_note_ids + [vault],
    ).fetchall()
    related: dict[int, set[int]] = defaultdict(set)
    for note_id, related_note_id in rows:
        if note_id is not None and related_note_id is not None:
            related[int(note_id)].add(int(related_note_id))
    return {note_id: sorted(ids) for note_id, ids in related.items()}
