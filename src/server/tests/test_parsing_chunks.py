from JLA.retrieval import Header
from JLA.retrieval.parsing import build_chunks_from_headers


def test_build_chunks_from_headers_creates_hierarchy_and_ranges():
    headers = [
        Header("Architecture", 1, 1),
        Header("Memory", 2, 2),
        Header("SQLite", 3, 3),
        Header("Obsidian", 3, 4),
        Header("Models", 2, 5),
    ]

    chunks = build_chunks_from_headers(headers, total_lines=8)

    assert len(chunks) == 1

    architecture = chunks[0]
    assert architecture.name == "Architecture"
    assert architecture.start_line == 1
    assert architecture.end_line == 8

    assert len(architecture.subchunks) == 2

    memory = architecture.subchunks[0]
    assert memory.name == "Memory"
    assert memory.start_line == 2
    assert memory.end_line == 4

    assert [chunk.name for chunk in memory.subchunks] == ["SQLite", "Obsidian"]
    assert memory.subchunks[0].start_line == 3
    assert memory.subchunks[0].end_line == 3
    assert memory.subchunks[1].start_line == 4
    assert memory.subchunks[1].end_line == 4

    models = architecture.subchunks[1]
    assert models.name == "Models"
    assert models.start_line == 5
    assert models.end_line == 8


def test_build_chunks_from_headers_closes_top_level_siblings():
    headers = [
        Header("One", 1, 1),
        Header("Two", 1, 6),
    ]

    chunks = build_chunks_from_headers(headers, total_lines=10)

    assert len(chunks) == 2
    assert chunks[0].name == "One"
    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 5
    assert chunks[1].name == "Two"
    assert chunks[1].start_line == 6
    assert chunks[1].end_line == 10
