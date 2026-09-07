import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import repository


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
    start_line: int
    end_line: int
    reason: str | None = None


@dataclass(slots=True)
class RetrievedNote:
    note_id: int
    vault: str
    file_path: str
    title: str
    score: int
    matched_by: dict[str, list[str]] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    chunks: list[RetrievedChunk] = field(default_factory=list)
    expansion_source: list[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.title or Path(self.file_path).stem


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
            chunk_lines = []
            for chunk in item.chunks:
                chunk_lines.append(f"  - {chunk.name} ({chunk.start_line}-{chunk.end_line})")
            if not chunk_lines:
                chunk_lines.append("  - no chunk metadata")

            matched = ", ".join(f"{key}:{' '.join(val)}" for key, val in item.matched_by.items()) or "no direct match"
            lines.append(f"{item.file_path} | {item.title} | score={item.score} | {matched}")
            lines.extend(chunk_lines)
        return "\n".join(lines)


def _normalize_token(token: str) -> str:
    token = token.strip().lower()
    if not token:
        return ""
    token = token.strip("[](){}<>\"'`.")
    return re.sub(r"[_-]+", " ", token).strip()


def _tokenize_prompt(prompt: str) -> list[str]:
    if not prompt:
        return []
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9._/-]*", prompt.lower())
    return [word for word in words if word and word not in {"and", "or", "the", "with", "for", "from"}]


def parse_query_intent(prompt: str) -> QueryIntent:
    clean_prompt = (prompt or "").strip()
    if not clean_prompt:
        return QueryIntent(prompt="")

    metadata_filters: dict[str, str] = {}
    remaining_text = clean_prompt
    for match in re.finditer(r"(?i)\b(vault|folder|path|tag|project|category|modified|after|before)\s*:\s*([A-Za-z0-9_./-]+)\b", clean_prompt):
        key = match.group(1).lower()
        value = match.group(2).strip()
        metadata_filters[key] = value
        remaining_text = remaining_text.replace(match.group(0), " ")

    tokens = _tokenize_prompt(remaining_text)
    all_terms = set()
    for term in tokens:
        normalized = _normalize_token(term)
        if not normalized:
            continue
        all_terms.add(normalized)

    filename_terms = {term for term in all_terms if re.search(r"[/\\.]", term) or term.endswith("md")}
    title_terms = set(all_terms)
    keywords = set(all_terms)

    if not title_terms and tokens:
        title_terms = {tokens[0]}

    return QueryIntent(
        prompt=clean_prompt,
        filename_terms=filename_terms,
        title_terms=title_terms,
        keywords=keywords,
        metadata_filters=metadata_filters,
        expand_links=True,
    )


def _matches_metadata_filters(note: dict[str, Any], filters: dict[str, str]) -> bool:
    if not filters:
        return True

    for key, value in filters.items():
        lowered_value = value.lower()
        note_value = None
        if key in {"vault", "folder", "path"}:
            note_value = note.get("vault") if key == "vault" else note.get("file_path")
            if note_value is None:
                return False
            note_value = note_value.lower()
            if key == "folder":
                note_value = note_value.rsplit("/", 1)[0] if "/" in note_value else ""
            if key == "path":
                if lowered_value not in note_value:
                    return False
                continue
            if note_value != lowered_value:
                return False
        elif key == "modified":
            try:
                threshold = float(value)
            except ValueError:
                continue
            if note.get("modified_time", 0.0) < threshold:
                return False
        else:
            if key == "tag":
                continue
            note_value = note.get("title") or note.get("file_path") or ""
            if lowered_value not in str(note_value).lower():
                return False
    return True


def _as_searchable_text(value: str | None) -> str:
    return (value or "").lower()


def _note_matches_query_terms(note: dict[str, Any], intent: QueryIntent) -> bool:
    if not intent.keywords:
        return True

    title = (note.get("title") or "").lower()
    file_path = (note.get("file_path") or "").lower()
    search_text = f"{title} {file_path}"
    for term in intent.keywords:
        normalized = _normalize_token(term)
        if not normalized:
            continue
        if normalized in title or normalized in file_path:
            return True
    return False


def _match_score_for_note(note: dict[str, Any], intent: QueryIntent) -> tuple[int, dict[str, list[str]], list[str]]:
    score = 0
    matched_by: dict[str, list[str]] = defaultdict(list)
    reasons: list[str] = []

    title_value = (note.get("title") or "").strip()
    file_path = note.get("file_path") or ""
    stem = Path(file_path).stem.lower()

    for term in sorted(intent.filename_terms | intent.title_terms | intent.keywords):
        normalized_term = _normalize_token(term)
        if not normalized_term:
            continue

        if stem == normalized_term:
            score += 80
            matched_by["filename"].append(normalized_term)
            reasons.append(f"filename exact match: {normalized_term}")
        elif normalized_term in file_path.lower():
            score += 30
            matched_by["filename"].append(normalized_term)
            reasons.append(f"filename contains: {normalized_term}")

        if title_value and normalized_term in _as_searchable_text(title_value):
            score += 45
            matched_by["title"].append(normalized_term)
            reasons.append(f"title contains: {normalized_term}")

        if title_value and _normalize_token(title_value) == normalized_term:
            score += 70
            matched_by["title"].append(normalized_term)
            reasons.append(f"title exact match: {normalized_term}")

        if normalized_term in _as_searchable_text(file_path):
            score += 20
            matched_by["keyword"].append(normalized_term)
            reasons.append(f"path keyword: {normalized_term}")

    for field_name, value in intent.metadata_filters.items():
        if field_name == "vault":
            if note.get("vault") and note["vault"].lower() == value.lower():
                score += 25
                matched_by["metadata"].append(f"vault={value}")
        elif field_name == "path":
            if value.lower() in (note.get("file_path") or "").lower():
                score += 18
                matched_by["metadata"].append(f"path={value}")
        elif field_name == "folder":
            folder = note.get("file_path", "").rsplit("/", 1)[0] if "/" in str(note.get("file_path", "")) else ""
            if folder.lower() == value.lower():
                score += 18
                matched_by["metadata"].append(f"folder={value}")
        elif field_name == "modified":
            try:
                if float(note.get("modified_time", 0.0)) >= float(value):
                    score += 10
                    matched_by["metadata"].append(f"modified>= {value}")
            except ValueError:
                pass

    return score, dict(matched_by), reasons


def _best_chunks_for_note(note_id: int, note_path: str, note_title: str, chunks: list[dict[str, Any]], intent: QueryIntent) -> list[RetrievedChunk]:
    if not chunks:
        return []

    ranked: list[tuple[int, dict[str, Any]]] = []
    for chunk in chunks:
        name = chunk["name"]
        chunk_score = 0
        for term in sorted(intent.keywords | intent.title_terms | intent.filename_terms):
            normalized_term = _normalize_token(term)
            if not normalized_term:
                continue
            if normalized_term in _as_searchable_text(name):
                chunk_score += 30
            if normalized_term in _as_searchable_text(note_title):
                chunk_score += 10
            if normalized_term in _as_searchable_text(note_path):
                chunk_score += 5
        ranked.append((chunk_score, chunk))

    ranked.sort(key=lambda item: (-item[0], item[1]["start_line"]))
    return [
        RetrievedChunk(
            chunk_id=chunk["chunk_id"],
            note_id=note_id,
            name=chunk["name"],
            start_line=chunk["start_line"],
            end_line=chunk["end_line"],
            reason="matched chunk keywords" if chunk_score > 0 else None,
        )
        for chunk_score, chunk in ranked[:3]
    ]


def _expand_linked_results(conn: sqlite3.Connection, seed_results: list[RetrievedNote], max_expansion: int) -> list[RetrievedNote]:
    if not seed_results:
        return []

    seed_ids = [item.note_id for item in seed_results]
    related_by_note = repository.fetch_related_note_ids(conn, seed_ids)
    expanded: list[RetrievedNote] = []
    seen: set[int] = set(item.note_id for item in seed_results)
    for seed in seed_results:
        for related_id in related_by_note.get(seed.note_id, []):
            if related_id in seen:
                continue
            seen.add(related_id)
            related_note = repository.fetch_all_notes(conn)
            note_row = next((row for row in related_note if row["note_id"] == related_id), None)
            if note_row is None:
                continue
            score = max(seed.score - 20, 10)
            expanded_note = RetrievedNote(
                note_id=related_id,
                vault=str(note_row["vault"]),
                file_path=str(note_row["file_path"]),
                title=str(note_row["title"] or Path(note_row["file_path"]).stem),
                score=score,
                matched_by={"link": [seed.file_path]},
                reasons=[f"linked from {seed.file_path}"],
                expansion_source=[seed.file_path],
            )
            expanded.append(expanded_note)
            if len(expanded) >= max_expansion:
                return expanded
    return expanded


def retrieve_notes(conn: sqlite3.Connection, prompt: str, vault: str | None = None, max_results: int = 8, max_expansion: int = 3) -> RetrievalResult:
    clean_prompt = (prompt or "").strip()
    if not clean_prompt:
        return RetrievalResult(query=clean_prompt, results=[])

    intent = parse_query_intent(clean_prompt)
    if not intent.keywords and not intent.metadata_filters:
        return RetrievalResult(query=clean_prompt, results=[])

    note_rows = repository.fetch_all_notes(conn, vault=vault)
    if not note_rows:
        return RetrievalResult(query=clean_prompt, results=[])

    filtered_rows = [
        row for row in note_rows if _matches_metadata_filters(row, intent.metadata_filters)
    ]
    if intent.keywords:
        filtered_rows = [row for row in filtered_rows if _note_matches_query_terms(row, intent)]
    if not filtered_rows:
        return RetrievalResult(query=clean_prompt, results=[])

    candidate_map: dict[int, RetrievedNote] = {}
    for row in filtered_rows:
        score, matched_by, reasons = _match_score_for_note(row, intent)
        if score <= 0:
            continue
        title = str(row.get("title") or Path(row.get("file_path") or "untitled").stem)
        note_result = RetrievedNote(
            note_id=int(row["note_id"]),
            vault=str(row["vault"]),
            file_path=str(row["file_path"]),
            title=title,
            score=score,
            matched_by=matched_by,
            reasons=reasons,
        )
        candidate_map[int(row["note_id"])] = note_result

    seed_results = sorted(candidate_map.values(), key=lambda item: (-item.score, item.file_path.lower()))
    if intent.expand_links:
        expanded = _expand_linked_results(conn, seed_results[: max(1, len(seed_results))], max_expansion=max_expansion)
        for note in expanded:
            existing = candidate_map.get(note.note_id)
            if existing is not None:
                existing.score = max(existing.score, note.score)
                existing.reasons.extend(note.reasons)
                existing.expansion_source.extend(note.expansion_source)
                continue
            candidate_map[note.note_id] = note

    final_results = sorted(candidate_map.values(), key=lambda item: (-item.score, item.file_path.lower()))
    final_results = final_results[:max_results]

    chunk_map = repository.fetch_chunks_for_note_ids(conn, [note.note_id for note in final_results])
    for note in final_results:
        note.chunks = _best_chunks_for_note(note.note_id, note.file_path, note.title, chunk_map.get(note.note_id, []), intent)

    return RetrievalResult(query=clean_prompt, results=final_results)
