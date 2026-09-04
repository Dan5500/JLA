# from pathlib import Path
from dataclasses import dataclass, field

@dataclass
class Link:
    target_name: str # content of the string (what it displays)
    target_path: str | None = None # path to target relative to vault root
    # header: str | None = None # name of header its found under
    parent_path: str | None = None # path to the parent file

@dataclass
class Header:
    name: str # name of header
    level: int # number of pounds before the words (how big the words are)
    line: int # line number this header is found at

@dataclass
class Note:
    name: str
    vault: str
    location: str # path to note relative to vault root
    metadata: dict = field(default_factory=dict) # YAML properties frontmatter that obisidan hides
    headers: list[Header] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)
    backlinks: list[Link] = field(default_factory=list) # links from other notes that goes to this note

    # maybe add a static method that take a note path and returns a parsed Note class