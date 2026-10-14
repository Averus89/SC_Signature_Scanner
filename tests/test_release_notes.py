"""Tests for release_notes.extract_notes."""

import sys

import pytest

from release_notes import extract_notes, main

DEVLOG = """## Changelog

### 2026-10-14 — v6.2.11: Windows build

- Added the workflow.

### 2026-10-14 — v6.2.1: Older

- Older change.

## Development Timeline
"""


def test_extracts_only_the_requested_entry():
    notes = extract_notes(DEVLOG, "6.2.11")
    assert notes == "## 2026-10-14 — v6.2.11: Windows build\n\n- Added the workflow.\n"


def test_version_prefix_does_not_match_longer_version():
    # "6.2.1" must not pick up the v6.2.11 entry.
    assert "Older change." in extract_notes(DEVLOG, "6.2.1")
    assert "Added the workflow." not in extract_notes(DEVLOG, "6.2.1")


def test_last_entry_stops_at_next_section():
    assert "Development Timeline" not in extract_notes(DEVLOG, "6.2.1")


def test_missing_version_returns_empty():
    assert extract_notes(DEVLOG, "9.9.9") == ""


def test_cli_fails_when_entry_is_missing(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["release_notes.py", "0.0.0"])
    with pytest.raises(SystemExit, match="no changelog entry"):
        main()
