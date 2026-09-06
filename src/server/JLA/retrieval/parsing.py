import logging
import re
import yaml
from pathlib import Path

from . import Note, Header, Link, Chunk
from config.vaults import list_readable_vault_names, get_readable_vault_path
from .discovery import find_note_path

logger = logging.getLogger(__name__)

def build_chunks_from_headers(headers: list[Header], total_lines: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    stack: list[tuple[int, Chunk]] = []

    for header in headers:
        chunk = Chunk(name=header.name, start_line=header.line, end_line=total_lines)

        # Close all completed chunks before opening the next section.
        while stack and stack[-1][0] >= header.level:
            _, completed_chunk = stack.pop()
            completed_chunk.end_line = header.line - 1

        if stack:
            stack[-1][1].subchunks.append(chunk)
        else:
            chunks.append(chunk)

        stack.append((header.level, chunk))

    return chunks

def _resolve_vault_location(file: Path) -> tuple[str, str, Path]:
    resolved_file = file.resolve()

    for name in list_readable_vault_names():
        vault_path = get_readable_vault_path(name)
        if resolved_file.is_relative_to(vault_path):
            relative_path = resolved_file.relative_to(vault_path).as_posix()
            logger.debug("note is in vault: %s at: %s", name, relative_path)
            return name, relative_path, vault_path

    raise ValueError("file is not in any configured vault")


def _extract_metadata(content: str, file: Path) -> dict:
    yaml_regex = r"^---\s*\n([\s\S]*?)\n---\s*(?:\n|$)"
    yaml_match = re.match(yaml_regex, content)
    if yaml_match is None:
        return {}

    try:
        metadata = yaml.safe_load(yaml_match.group(1))
    except Exception as exc:
        logger.warning("YAML properties malformed in note: %s\n\t%s", file, exc)
        return {}

    if not isinstance(metadata, dict):
        return {}

    return metadata


def _extract_headers(content: str) -> list[Header]:
    headers: list[Header] = []
    for match in re.finditer(r"^(#{1,6})\s+(.+)$", content, re.MULTILINE):
        headers.append(
            Header(
                match.group(2),
                len(match.group(1)),
                content[: match.start()].count("\n") + 1,
            )
        )
    return headers


def _normalize_link_target(raw_target: str) -> str:
    target = raw_target.strip()
    if "|" in target:
        target = target.split("|", 1)[0].strip()
    if "#" in target:
        target = target.split("#", 1)[0].strip()
    return target


def _extract_links(content: str, vault: str, relative_path: str) -> list[Link]:
    links: list[Link] = []
    seen: set[tuple[str, str | None]] = set()
    vault_root = get_readable_vault_path(vault)

    for match in re.finditer(r"\[\[([^\[\]\r\n]+?)\]\]", content):
        raw_target = match.group(1).strip()
        if not raw_target:
            continue

        normalized_target = _normalize_link_target(raw_target)
        if not normalized_target:
            continue

        resolved_path: str | None = None
        target_path = find_note_path(vault, normalized_target)
        if target_path is not None:
            try:
                resolved_path = target_path.relative_to(vault_root).as_posix()
            except ValueError:
                resolved_path = None

        dedupe_key = (raw_target, resolved_path)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        links.append(Link(raw_target, resolved_path, relative_path))

    return links


def parse_markdown(file: Path, content: str) -> Note:
    if not file.is_file():
        raise ValueError("path is not a file")
    if file.suffix != ".md":
        raise ValueError("file is not a markdown file")

    vault, relative_path, _ = _resolve_vault_location(file)
    metadata = _extract_metadata(content, file)
    headers = _extract_headers(content)
    chunks = build_chunks_from_headers(headers, len(content.splitlines()))
    links = _extract_links(content, vault, relative_path)

    return Note(file.stem, vault, relative_path, metadata, headers, chunks, links)


def parse_file(file: Path) -> Note:
    content = file.read_text(encoding="utf-8")
    return parse_markdown(file, content)