import re
import yaml
import logging
from pathlib import Path

from . import Note, Header, Link
from config.vaults import list_readable_vault_names, get_readable_vault_path
from .discovery import find_note_path

logger = logging.getLogger(__name__)

'''
    Data to grab from a note/markdown file in the vault:
      - Name
      - YAML Metadata (if included) - this also means you have to figure out how to add invisible yaml to md files
      - Headers & Subheaders
      - Obsidian Links (format: [[note name]](note/location))
      - Backlinks (what files link to this one) - maybe. might not include bc you need to know all the other files first to know what links to this one

    Once all this info is gathered, create a Note class and return it
'''
def parse_file(file: Path) -> Note:
    # ensure the Path is a valid obsidian note
    if(not file.is_file()):
        raise ValueError("path is not a file")
    if(file.suffix != ".md"):
        raise ValueError("file is not a markdown file")

    # find what vault the file is in
    vault = "none"
    for name in list_readable_vault_names():
        vault_path = get_readable_vault_path(name)
        if(file.is_relative_to(vault_path)):
            # get the relative path
            relative_path = file.relative_to(vault_path).as_posix()
            logger.debug(f"note is in vault: {name} at: {relative_path}")
            vault = name
    if(vault == "none"):
        raise ValueError("file is not in any configured vault")

    # maybe add a check that raises an error if the file is more than 25% of the program's given RAM?
    # this would prevent the following line from malfunctioning
    content = file.read_text(encoding="utf-8") # ONLY works if the file fits into RAM, will break if bigger

    # YAML metadata
    yaml_regex = r"^---\s*\n([\s\S]*?)\n---"
    yaml_match = re.search(yaml_regex, content)
    metadata = {}
    if(yaml_match != None):
        try:
            metadata = yaml.safe_load(yaml_match.group(1))
        except Exception as exc:
            logger.warning(f"YAML properties malformed in note: {file}\n\t{exc}")
    # get all headers (list of Header classes)
    headers = []
    header_matches = []
    for match in re.finditer(r"^(#{1,6})\s+(.+)$", content, re.MULTILINE):
        '''
            the commented line of code would scan the file once for every match that
            regex finds, to find out how many new lines there are before the match
            (thus finding the line number of the header), however this is rly ineffecient

            the new/uncommented line of code writes down the text of every header in the file (including the hashtags)
            into a list, and the file is later scanned just once for every match, thus saving resources/increasing effeciency
        '''
        # headers.append(Header(match.group(2), len(match.group(1)), content[:match.start()].count('\n')+1))
        header_matches.append(match)

    # find the line number for each string in header_text[] and effeciently append them to the headers list

    linenum = 0 # line number
    matchnum = 0 # number match we're on; should go all the way up to len(header_matches)-1, no less no more
    logger.debug(f"parsing header matches into objects... # of matches: {len(header_matches)}")
    if(header_matches):
        logger.debug(header_matches)
        for line in content.splitlines():
            if(matchnum < len(header_matches)):
                linenum = linenum + 1
                # because the headers were scanned from top to bottom,
                if(line == header_matches[matchnum].group()):
                    headers.append(Header(header_matches[matchnum].group(2), len(header_matches[matchnum].group(1)), linenum))
                    matchnum = matchnum + 1 # increases the index of matchnum
                # log progress
                logger.debug(f"matchnum: {matchnum}, linenum: {linenum}, line: '{line}'")
            logger.debug(f"parsed all headers. header list: {headers}")
    else:
        logger.debug("header_matches[] is empty")

    if(matchnum != len(header_matches)):
        logger.error("Headers were incorrectly parsed! AKA, fix your code!") 
        # matchnum hypothetically should match up with the length of header_matches[]
        # as long as the comparison in the above for loop (line == header_matches[matchnum].group()) works
        # so this error shouldn't be raised. if it is, however, itll tell me that I messed up the headers
    
    # get all links
    '''
        apparently more effecient to scan the file twice rather than use regex for two different expressions at once
        this is because scanning for two expressions at once in python is really complex and difficult, whilst
        scanning twice for a single pattern at a time would actually be faster. 

        the only caveat of this would be if the file is utterly massive. bc then, the pure time it takes to go thru the file
        would overtake the time saved by not doing two at once.
    '''
    links = [] # list of all links this note points to. a list of Link classes
    for match in re.finditer(r"\[\[(.+?)\]\]", content):
        links.append(Link(match.group(1), str(find_note_path(vault, match.group(1)).relative_to(get_readable_vault_path(vault))), relative_path)) # finish this ltr (missing: target path and header classification implementation)

    # backlinks = [] # add to this after updating the list of all notes
    '''
        in order to get backlinks, I have to go thru every single note and find what notes they link to,
        and then update each one of those notes that they've been backlinked by the note we have

        so it'll go:
        Note A (links to note B) -> update note B's backlinks
        Note B (links to Note A + C) -> update note C's and note A's backlinks
        Note C (links to nothing) -> updates no other notes

        i'll prob have this as its own method that could run every time the server is launched
    '''

    # construct the Note class with the right parameters
    note = Note(file.stem, vault, relative_path, metadata, headers, links)

    return note


r'''
    To find any md headers, use this in regular expression:
        ^(#{1,6})\s+(.+)$
    To find YAML properties in md, use this:
        ^---\s*\n([\s\S]*?)\n---
    To find Obsidian links, use this:
        \[\[(.+?)\]\]
'''