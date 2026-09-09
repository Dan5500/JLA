import logging
import re
from pathlib import Path

import yaml

from ..config.vaults import get_readable_vault_path, list_readable_vault_names
from . import Chunk, Header, Link, Note
from .discovery import find_note_path

logger = logging.getLogger(__name__)


def build_chunks_from_headers(headers: list[Header], total_lines: int) -> list[Chunk]:
    """Create nested, inclusive ranges and retain text before the first heading."""
    chunks: list[Chunk] = []
    stack: list[tuple[int, Chunk]] = []
    if headers and headers[0].line > 1:
        chunks.append(Chunk("(preamble)", 1, headers[0].line - 1, heading_path="(preamble)"))
    elif not headers and total_lines:
        return [Chunk("(preamble)", 1, total_lines, heading_path="(preamble)")]

    for header in headers:
        chunk = Chunk(header.name, header.line, total_lines)
        while stack and stack[-1][0] >= header.level:
            _, completed = stack.pop()
            completed.end_line = header.line - 1
        if stack:
            parent = stack[-1][1]
            chunk.heading_path = f"{parent.heading_path} > {header.name}"
            parent.subchunks.append(chunk)
        else:
            chunk.heading_path = header.name
            chunks.append(chunk)
        stack.append((header.level, chunk))
    return chunks


def _resolve_vault_location(file: Path) -> tuple[str, str, Path]:
    resolved_file = file.resolve()
    for name in list_readable_vault_names():
        vault_path = get_readable_vault_path(name)
        if resolved_file.is_relative_to(vault_path):
            return name, resolved_file.relative_to(vault_path).as_posix(), vault_path
    raise ValueError("file is not in any configured vault")


def _extract_metadata(content: str, file: Path) -> dict:
    match = re.match(r"^---\s*\n([\s\S]*?)\n---\s*(?:\n|$)", content)
    if match is None:
        return {}
    try:
        metadata = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        logger.warning("Malformed YAML frontmatter in %s: %s", file, exc)
        return {}
    return metadata if isinstance(metadata, dict) else {}


def _extract_headers(content: str) -> list[Header]:
    return [Header(match.group(2).strip(), len(match.group(1)), content[:match.start()].count("\n") + 1)
            for match in re.finditer(r"^(#{1,6})\s+(.+?)\s*#*\s*$", content, re.MULTILINE)]


def _split_link_target(raw_target: str) -> tuple[str, str | None]:
    target = raw_target.strip().split("|", 1)[0].strip()
    path, separator, section = target.partition("#")
    return path.strip(), section.strip() if separator and section.strip() else None


def _extract_links(content: str, vault: str, relative_path: str) -> list[Link]:
    links: list[Link] = []
    seen: set[tuple[str, str | None]] = set()
    vault_root = get_readable_vault_path(vault)
    for match in re.finditer(r"\[\[([^\[\]\r\n]+?)\]\]", content):
        raw_target = match.group(1).strip()
        target, section = _split_link_target(raw_target)
        if not target:
            continue
        target_file = find_note_path(vault, target)
        resolved = target_file.relative_to(vault_root).as_posix() if target_file else None
        key = (raw_target, resolved)
        if key not in seen:
            seen.add(key)
            links.append(Link(raw_target, resolved, relative_path, section))
    return links


def parse_markdown(file: Path, content: str) -> Note:
    if not file.is_file() or file.suffix.lower() != ".md":
        raise ValueError("path is not a Markdown file")
    vault, relative_path, _ = _resolve_vault_location(file)
    headers = _extract_headers(content)
    return Note(file.stem, vault, relative_path, _extract_metadata(content, file), headers,
                build_chunks_from_headers(headers, len(content.splitlines())), _extract_links(content, vault, relative_path))


def parse_file(file: Path) -> Note:
    return parse_markdown(file, file.read_text(encoding="utf-8"))
