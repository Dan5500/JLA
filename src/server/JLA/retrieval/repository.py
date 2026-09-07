import sqlite3
from collections import defaultdict
from typing import Any


def fetch_all_notes(conn: sqlite3.Connection, vault: str | None = None) -> list[dict[str, Any]]:
    sql = """
        SELECT note_id, vault, file_path, title, modified_time
        FROM notes
        WHERE 1 = 1
    """
    params: list[Any] = []

    if vault is not None:
        sql += " AND vault = ?"
        params.append(vault)

    sql += " ORDER BY vault, file_path"
    cursor = conn.cursor()
    cursor.execute(sql, params)
    return [
        {
            "note_id": int(row[0]),
            "vault": row[1],
            "file_path": row[2],
            "title": row[3],
            "modified_time": float(row[4]),
        }
        for row in cursor.fetchall()
    ]


def fetch_chunks_for_note_ids(conn: sqlite3.Connection, note_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
    if not note_ids:
        return {}

    placeholders = ", ".join("?" for _ in note_ids)
    cursor = conn.cursor()
    cursor.execute(
        f"""
            SELECT note_id, chunk_id, name, start_line, end_line
            FROM chunks
            WHERE note_id IN ({placeholders})
            ORDER BY note_id, chunk_index
        """,
        note_ids,
    )

    chunks_by_note: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for note_id, chunk_id, name, start_line, end_line in cursor.fetchall():
        chunks_by_note[int(note_id)].append(
            {
                "chunk_id": int(chunk_id),
                "name": name,
                "start_line": int(start_line),
                "end_line": int(end_line),
            }
        )
    return dict(chunks_by_note)


def fetch_link_neighbors(conn: sqlite3.Connection, seed_note_ids: list[int]) -> dict[int, list[int]]:
    if not seed_note_ids:
        return {}

    seed_ids = sorted(set(seed_note_ids))
    placeholders = ", ".join("?" for _ in seed_ids)
    cursor = conn.cursor()
    cursor.execute(
        f"""
            SELECT source_note_id, target_note_id
            FROM links
            WHERE source_note_id IN ({placeholders})
        """,
        seed_ids,
    )
    outgoing: dict[int, set[int]] = defaultdict(set)
    for source_note_id, target_note_id in cursor.fetchall():
        if target_note_id is not None:
            outgoing[int(source_note_id)].add(int(target_note_id))

    cursor.execute(
        f"""
            SELECT DISTINCT l.source_note_id, n.note_id
            FROM links AS l
            JOIN notes AS n
              ON n.vault = (SELECT vault FROM notes WHERE note_id = l.target_note_id)
             AND n.file_path = l.target_path
            WHERE l.target_note_id IN ({placeholders})
        """,
        seed_ids,
    )
    incoming: dict[int, set[int]] = defaultdict(set)
    for source_note_id, related_note_id in cursor.fetchall():
        if related_note_id is not None:
            incoming[int(source_note_id)].add(int(related_note_id))

    neighbors: dict[int, list[int]] = {}
    for note_id in seed_ids:
        related = set(outgoing.get(note_id, set()))
        related |= {target_id for source_id, target_ids in incoming.items() for target_id in target_ids if source_id == note_id}
        neighbors[note_id] = sorted(related)
    return neighbors


def fetch_related_note_ids(conn: sqlite3.Connection, seed_note_ids: list[int]) -> dict[int, list[int]]:
    if not seed_note_ids:
        return {}

    seed_ids = sorted(set(seed_note_ids))
    placeholders = ", ".join("?" for _ in seed_ids)
    cursor = conn.cursor()
    cursor.execute(
        f"""
            WITH outgoing AS (
                SELECT source_note_id AS note_id, target_note_id AS related_note_id
                FROM links
                WHERE source_note_id IN ({placeholders})
            ),
            incoming AS (
                SELECT target_note_id AS note_id, source_note_id AS related_note_id
                FROM links
                WHERE target_note_id IN ({placeholders})
            )
            SELECT note_id, related_note_id
            FROM outgoing
            UNION ALL
            SELECT note_id, related_note_id
            FROM incoming
        """,
        seed_ids + seed_ids,
    )

    related: dict[int, set[int]] = defaultdict(set)
    for note_id, related_note_id in cursor.fetchall():
        if note_id is None or related_note_id is None:
            continue
        related[int(note_id)].add(int(related_note_id))
    return {note_id: sorted(related_ids) for note_id, related_ids in related.items()}
