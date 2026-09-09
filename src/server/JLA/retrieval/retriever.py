import hashlib
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from ..config.vaults import get_readable_vault_path
from . import Chunk, Note
from . import repository

_STOP_WORDS = {"and", "or", "the", "with", "for", "from", "a", "an", "of", "in", "to"}


@dataclass(slots=True)
class QueryIntent:
    prompt: str
    filename_terms: set[str] = field(default_factory=set)
    title_terms: set[str] = field(default_factory=set)
    keywords: set[str] = field(default_factory=set)
    metadata_filters: dict[str, str] = field(default_factory=dict)
    expand_links: bool = True


@dataclass(slots=True)
class RetrievedChunk:
    chunk_id: int
    note_id: int
    name: str
    heading_path: str
    start_line: int
    end_line: int
    content_hash: str
    score: int = 0
    matched_terms: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    content: str = ""


@dataclass(slots=True)
class RetrievedNote:
    note_id: int
    vault: str
    file_path: str
    title: str
    score: int
    note: Note | None = None
    matched_by: dict[str, list[str]] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    chunks: list[RetrievedChunk] = field(default_factory=list)
    expansion_source: list[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.title


@dataclass(slots=True)
class RetrievalResult:
    query: str
    results: list[RetrievedNote]

    @property
    def total(self) -> int:
        return len(self.results)

    def display_text(self) -> str:
        if not self.results:
            return "No notes retrieved."
        lines: list[str] = []
        for item in self.results:
            lines.append(f"{item.vault}/{item.file_path} | {item.title} | score={item.score}")
            lines.extend(f"  reason: {reason}" for reason in item.reasons)
            for chunk in item.chunks:
                lines.append(f"  - {chunk.heading_path} ({chunk.start_line}-{chunk.end_line}) | score={chunk.score}")
                lines.extend(f"    reason: {reason}" for reason in chunk.reasons)
        return "\n".join(lines)


def _normalize(value: str) -> str:
    return re.sub(r"[_-]+", " ", value.strip().lower()).strip(" [](){}<>\"'`.")


def _tokens(text: str) -> set[str]:
    return {_normalize(token) for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9._/-]*", text.lower()) if _normalize(token) not in _STOP_WORDS}


def parse_query_intent(prompt: str) -> QueryIntent:
    clean = (prompt or "").strip()
    filters: dict[str, str] = {}
    remaining = clean
    for match in re.finditer(r"(?i)\b([A-Za-z][A-Za-z0-9_-]*)\s*:\s*([^\s]+)", clean):
        filters[match.group(1).lower()] = match.group(2).strip()
        remaining = remaining.replace(match.group(0), " ")
    terms = _tokens(remaining)
    return QueryIntent(clean, {term for term in terms if "/" in term or "." in term}, set(terms), set(terms), filters)


def _date_value(value: str) -> float | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return None


def _metadata_matches(note: dict[str, Any], filters: dict[str, str], vault: str) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    for key, value in filters.items():
        expected = value.casefold()
        if key == "vault":
            if expected != vault.casefold(): return False, []
        elif key == "folder":
            if Path(note["file_path"]).parent.as_posix().casefold() != expected: return False, []
        elif key == "path":
            if expected not in note["file_path"].casefold(): return False, []
        elif key in {"after", "before", "modified"}:
            threshold = _date_value(value)
            if threshold is None: return False, []
            modified = note["modified_time"]
            if (key == "before" and modified >= threshold) or (key != "before" and modified < threshold): return False, []
        else:
            metadata = note.get("metadata", {})
            actual = metadata.get(key)
            if key == "tag" and actual is None:
                actual = metadata.get("tags")
            values = actual if isinstance(actual, list) else [actual]
            if not any(expected == str(item).casefold() for item in values if item is not None): return False, []
        reasons.append(f"metadata filter: {key}={value}")
    return True, reasons


def _note_score(note: dict[str, Any], intent: QueryIntent) -> tuple[int, dict[str, list[str]], list[str]]:
    score, matched, reasons = 0, {}, []
    stem = _normalize(Path(note["file_path"]).stem)
    path = _normalize(note["file_path"])
    title = _normalize(note["title"])
    for term in sorted(intent.keywords):
        if term == stem:
            score += 120; matched.setdefault("filename", []).append(term); reasons.append(f"exact filename: {term}")
        elif term in path:
            score += 30; matched.setdefault("path", []).append(term); reasons.append(f"path match: {term}")
        if term == title:
            score += 80; matched.setdefault("title", []).append(term); reasons.append(f"exact title: {term}")
        elif term in title:
            score += 45; matched.setdefault("title", []).append(term); reasons.append(f"title match: {term}")
    return score, matched, reasons


def _read_chunk_text(vault: str, file_path: str, chunk: dict[str, Any]) -> str | None:
    path = (get_readable_vault_path(vault) / file_path).resolve()
    root = get_readable_vault_path(vault).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    text = "\n".join(lines[chunk["start_line"] - 1:chunk["end_line"]])
    if hashlib.sha256(text.encode("utf-8")).hexdigest() != chunk["content_hash"]:
        return None
    return text


def _rank_chunks(note: dict[str, Any], chunks: list[dict[str, Any]], intent: QueryIntent) -> list[RetrievedChunk]:
    ranked: list[RetrievedChunk] = []
    for row in chunks:
        content = _read_chunk_text(note["vault"], note["file_path"], row)
        if content is None:
            continue
        score, terms, reasons = 0, [], []
        heading = f"{row['name']} {row['heading_path']}".casefold()
        body = content.casefold()
        for term in sorted(intent.keywords):
            if term in heading:
                score += 60; terms.append(term); reasons.append(f"heading match: {term}")
            if term in body:
                score += 25; terms.append(term); reasons.append(f"section text match: {term}")
        if score:
            ranked.append(RetrievedChunk(row["chunk_id"], note["note_id"], row["name"], row["heading_path"],
                                          row["start_line"], row["end_line"], row["content_hash"], score,
                                          sorted(set(terms)), reasons, content))
    ranked.sort(key=lambda chunk: (-chunk.score, chunk.end_line - chunk.start_line, chunk.start_line, chunk.chunk_id))
    selected: list[RetrievedChunk] = []
    for chunk in ranked:
        if all(chunk.end_line < kept.start_line or chunk.start_line > kept.end_line for kept in selected):
            selected.append(chunk)
        if len(selected) == 3:
            break
    return selected


def _note_snapshot(row: dict[str, Any], chunks: list[dict[str, Any]]) -> Note:
    objects = {chunk["chunk_id"]: Chunk(chunk["name"], chunk["start_line"], chunk["end_line"],
                                           heading_path=chunk["heading_path"], content_hash=chunk["content_hash"])
               for chunk in chunks}
    roots: list[Chunk] = []
    for chunk in chunks:
        obj = objects[chunk["chunk_id"]]
        parent = objects.get(chunk["parent_chunk_id"])
        if parent: parent.subchunks.append(obj)
        else: roots.append(obj)
    return Note(row["title"], row["vault"], row["file_path"], row.get("metadata", {}), chunks=roots)


def retrieve_notes(conn: sqlite3.Connection, prompt: str, vault: str | None = None, max_results: int = 8, max_expansion: int = 3) -> RetrievalResult:
    clean = (prompt or "").strip()
    if not clean or not vault:
        return RetrievalResult(clean, [])
    intent = parse_query_intent(clean)
    if intent.metadata_filters.get("vault", vault).casefold() != vault.casefold():
        return RetrievalResult(clean, [])
    rows = repository.fetch_all_notes(conn, vault)
    candidates = []
    for row in rows:
        accepted, filter_reasons = _metadata_matches(row, intent.metadata_filters, vault)
        if not accepted: continue
        candidates.append((row, filter_reasons))
    chunk_map = repository.fetch_chunks_for_note_ids(conn, [row["note_id"] for row, _ in candidates])
    results: dict[int, RetrievedNote] = {}
    for row, filter_reasons in candidates:
        base_score, matched, reasons = _note_score(row, intent)
        chunks = _rank_chunks(row, chunk_map.get(row["note_id"], []), intent)
        if not base_score and not chunks and not intent.metadata_filters:
            continue
        score = base_score + (chunks[0].score if chunks else 0) + (20 if filter_reasons else 0)
        results[row["note_id"]] = RetrievedNote(row["note_id"], vault, row["file_path"], row["title"], score,
                                                   _note_snapshot(row, chunk_map.get(row["note_id"], [])), matched,
                                                   reasons + filter_reasons, chunks)
    direct = sorted(results.values(), key=lambda item: (-item.score, item.file_path.casefold()))
    related = repository.fetch_related_note_ids(conn, [item.note_id for item in direct], vault)
    by_id = {row["note_id"]: row for row in rows}
    expansion_count = 0
    for seed in direct:
        for related_id in related.get(seed.note_id, []):
            if related_id in results or expansion_count >= max_expansion: continue
            row = by_id[related_id]
            accepted, filter_reasons = _metadata_matches(row, intent.metadata_filters, vault)
            if not accepted:
                continue
            results[related_id] = RetrievedNote(related_id, vault, row["file_path"], row["title"], max(seed.score - 30, 1),
                                                  _note_snapshot(row, chunk_map.get(related_id, [])), {"link": [seed.file_path]},
                                                  [f"one-hop link from {seed.file_path}"] + filter_reasons, [], [seed.file_path])
            expansion_count += 1
    ordered = sorted(results.values(), key=lambda item: (-item.score, item.file_path.casefold()))
    return RetrievalResult(clean, ordered[:max_results])
