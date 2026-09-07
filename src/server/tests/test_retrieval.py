import sqlite3

import pytest

from JLA.database.connection import initialize_database
from JLA.retrieval.retriever import RetrievalResult, retrieve_notes


@pytest.fixture()
def conn():
    connection = sqlite3.connect(":memory:")
    initialize_database(connection)
    return connection


def seed_notes(conn: sqlite3.Connection) -> None:
    conn.executemany(
        """
        INSERT INTO notes (vault, file_path, file_hash, modified_time, file_size, title)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            ("personal", "alpha.md", "hash-alpha", 100.0, 1, "Alpha"),
            ("personal", "projects/architecture.md", "hash-arch", 101.0, 2, "System Architecture"),
            ("personal", "projects/meeting-notes.md", "hash-meeting", 102.0, 3, "Quarterly Meeting Notes"),
            ("team", "alpha-summary.md", "hash-summary", 103.0, 4, "Alpha Summary"),
            ("personal", "notes/finance.md", "hash-finance", 104.0, 5, "Budget Planning"),
            ("team", "notes/operations.md", "hash-ops", 105.0, 6, "Operations"),
            ("personal", "notes/related.md", "hash-related", 106.0, 7, "Related Research"),
        ],
    )

    conn.executemany(
        """
        INSERT INTO chunks (note_id, parent_chunk_id, chunk_index, name, start_line, end_line)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (1, None, 0, "Alpha Overview", 1, 20),
            (2, None, 0, "Architecture Overview", 1, 20),
            (2, None, 1, "System design", 21, 40),
            (3, None, 0, "Meeting Agenda", 1, 20),
            (5, None, 0, "Budget Review", 1, 30),
            (5, None, 1, "Spend Forecast", 31, 60),
            (7, None, 0, "Linked Notes", 1, 10),
        ],
    )

    conn.executemany(
        """
        INSERT INTO links (source_note_id, link_index, target_name, target_path, target_note_id, target_section)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (1, 0, "System Architecture", "projects/architecture.md", 2, None),
            (2, 0, "Alpha", "alpha.md", 1, None),
            (5, 0, "Operations", "notes/operations.md", 6, None),
            (6, 0, "Budget Planning", "notes/finance.md", 5, None),
        ],
    )


def test_filename_match_ranks_exact_file_name_first(conn):
    seed_notes(conn)

    result = retrieve_notes(conn, "alpha")

    assert result.total >= 2
    assert result.results[0].file_path == "alpha.md"
    assert "filename" in result.results[0].matched_by


def test_title_match_ranks_title_before_keyword_only_matches(conn):
    seed_notes(conn)

    result = retrieve_notes(conn, "architecture system")

    assert result.results[0].file_path == "projects/architecture.md"
    assert result.results[0].score >= result.results[1].score


def test_keyword_match_uses_note_and_chunk_words(conn):
    seed_notes(conn)

    result = retrieve_notes(conn, "budget spend")

    assert result.results[0].file_path == "notes/finance.md"
    assert any(chunk.name == "Spend Forecast" for chunk in result.results[0].chunks)


def test_metadata_filters_narrow_results(conn):
    seed_notes(conn)

    result = retrieve_notes(conn, "alpha vault:team")

    assert result.total == 1
    assert result.results[0].file_path == "alpha-summary.md"


def test_link_expansion_adds_related_notes_after_seed_match(conn):
    seed_notes(conn)

    result = retrieve_notes(conn, "system architecture")

    assert any(item.file_path == "alpha.md" for item in result.results)
    assert any(item.file_path == "projects/architecture.md" for item in result.results)


def test_duplicate_suppression_removes_repeat_results(conn):
    seed_notes(conn)

    result = retrieve_notes(conn, "alpha architecture")

    file_paths = [item.file_path for item in result.results]
    assert file_paths.count("alpha.md") == 1
    assert file_paths.count("projects/architecture.md") == 1


def test_result_ranking_order_is_sensible(conn):
    seed_notes(conn)

    result = retrieve_notes(conn, "alpha architecture")

    assert [item.file_path for item in result.results[:2]] == ["alpha.md", "projects/architecture.md"]


def test_display_includes_note_and_chunk_details(conn):
    seed_notes(conn)

    result = retrieve_notes(conn, "budget spend")
    text = result.display_text()

    assert "notes/finance.md" in text
    assert "Budget Planning" in text
    assert "Spend Forecast" in text


def test_empty_or_no_match_prompts_return_clean_results(conn):
    seed_notes(conn)

    empty = retrieve_notes(conn, "   ")
    no_match = retrieve_notes(conn, "totally-not-a-real-note")

    assert isinstance(empty, RetrievalResult)
    assert empty.total == 0
    assert isinstance(no_match, RetrievalResult)
    assert no_match.total == 0


def test_malformed_partial_queries_do_not_crash(conn):
    seed_notes(conn)

    result = retrieve_notes(conn, "vault:personal path:projects ???")

    assert isinstance(result, RetrievalResult)
    assert result.total >= 0
