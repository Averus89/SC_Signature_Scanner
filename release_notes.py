"""Extract one version's changelog entry from DEVLOG.md for a GitHub Release.

Usage: python release_notes.py 6.2.11 > notes.md

Author: Mallachi
"""

import re
import sys
from pathlib import Path

DEVLOG_PATH = Path(__file__).parent / "DEVLOG.md"


def extract_notes(devlog: str, version: str) -> str:
    """Return the body of the ``### <date> — v<version>: <title>`` entry.

    Args:
        devlog: Full DEVLOG.md text.
        version: Version without the leading "v", e.g. "6.2.11".

    Returns:
        The entry's title line as a heading plus its body, or an empty
        string when DEVLOG has no entry for that version.
    """
    heading = re.compile(rf"^### .*\bv{re.escape(version)}\b[^\n]*$", re.MULTILINE)
    match = heading.search(devlog)
    if not match:
        return ""
    # The entry ends at the next changelog entry or the next top-level section.
    end = re.compile(r"^#{2,3} ", re.MULTILINE).search(devlog, match.end())
    body = devlog[match.end() : end.start() if end else len(devlog)]
    title = match.group(0).removeprefix("### ").strip()
    return f"## {title}\n\n{body.strip()}\n"


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: release_notes.py <version>")
    version = sys.argv[1]
    notes = extract_notes(DEVLOG_PATH.read_text(encoding="utf-8"), version)
    # A release without its changelog entry is a missed DEVLOG update; fail loudly.
    if not notes:
        sys.exit(f"DEVLOG.md has no changelog entry for v{version}")
    sys.stdout.reconfigure(encoding="utf-8")
    print(notes, end="")


if __name__ == "__main__":
    main()
