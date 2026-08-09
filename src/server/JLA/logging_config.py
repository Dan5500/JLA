import logging
import sys
import pathlib
from typing import Optional


def setup_logging(level: str = "INFO") -> None:
    """Configure logging for JLA with a file and console handler.

    - File handler: writes DEBUG+ to src/server/logs/jla.log
    - Console handler: writes WARNING+ to stdout

    This function is idempotent: calling it multiple times will not add
    duplicate handlers for the same destinations.
    """
    normalized_level = str(level).upper() if level else "INFO"
    numeric_level = logging.getLevelName(normalized_level)

    # Determine paths: logs/ should live under src/server/logs
    script_dir = pathlib.Path(__file__).resolve().parent
    server_dir = script_dir.parents[1]
    logs_dir = server_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "jla.log"

    with open(log_file, "a") as file:
        file.write("...\n")

    fmt = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    formatter = logging.Formatter(fmt)

    root = logging.getLogger()
    # Set root low enough so file handler can capture DEBUG
    root.setLevel(logging.DEBUG)

    # Add or update file handler for jla.log
    file_handler: Optional[logging.FileHandler] = None
    for h in list(root.handlers):
        if isinstance(h, logging.FileHandler):
            try:
                existing = pathlib.Path(h.baseFilename).resolve()
            except Exception:
                existing = None
            if existing == log_file.resolve():
                file_handler = h
                break

    if file_handler is None:
        fh = logging.FileHandler(str(log_file))
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        root.addHandler(fh)
    else:
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)

    # Add or update console handler (stdout) to WARNING+
    console_handler: Optional[logging.StreamHandler] = None
    for h in list(root.handlers):
        if isinstance(h, logging.StreamHandler) and getattr(h, "stream", None) is sys.stdout:
            console_handler = h
            break

    if console_handler is None:
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.WARNING)
        ch.setFormatter(formatter)
        root.addHandler(ch)
    else:
        console_handler.setLevel(logging.WARNING)
        console_handler.setFormatter(formatter)

    # Warn if the supplied level string was invalid
    if not isinstance(numeric_level, int):
        logging.getLogger(__name__).warning(
            "Invalid logging level '%s' supplied; using defaults.", level
        )
