"""Look-alike-digit substitution correction — recover misreads, refuse to guess.

At the ~20px digit height the SC HUD renders, EasyOCR confuses 6/8/9 etc., so a
steady on-screen signature is read differently frame to frame (16,960 → 18,960 /
18,680). _try_substitution_correction snaps a misread back to a valid signature
ONLY when exactly one valid signature is reachable by a single look-alike swap;
ambiguous misreads are refused so we never fabricate a false lock.
"""
from unittest.mock import MagicMock

import numpy as np

import paths
from scanner import SignatureScanner


def _scanner() -> SignatureScanner:
    return SignatureScanner(paths.get_base_path() / "data" / "combat_analyst_db.json")


def test_unique_substitution_recovers_signature():
    """A misread with exactly one valid look-alike neighbor is corrected."""
    s = _scanner()
    # 16,960 (Copper Common x4) is read as 18,960; 8->6 is the only swap that
    # lands on a valid signature.
    assert s._try_substitution_correction(18960) == 16960
    assert s._try_substitution_correction(25820) == 25620  # Iron Common x6
    assert s._try_substitution_correction(11585) == 11565  # Titanium Uncommon x3


def test_ambiguous_substitution_is_refused():
    """When two or more valid signatures are reachable, refuse rather than guess."""
    s = _scanner()
    # 29,620 -> 25,620 / 29,600 / 29,680 are all valid; ambiguous => None.
    assert s._try_substitution_correction(29620) is None
    # 16,980 -> 16,780 / 16,900 / 16,960 are all valid; ambiguous => None.
    assert s._try_substitution_correction(16980) is None


def test_unrecoverable_substitution_returns_none():
    """A misread with no valid single-swap neighbor (truth is >1 swap away)."""
    s = _scanner()
    # The real 16,960 is three substitutions from 18,880 — not recoverable.
    assert s._try_substitution_correction(18880) is None
    assert s._try_substitution_correction(18980) is None


def test_extract_applies_correction_to_misread():
    """End to end: a misread digit string yields the corrected signature."""
    s = _scanner()
    assert s._extract_signatures("18960") == [16960]
    assert s._extract_signatures("11585") == [11565]


def test_extract_keeps_valid_value_uncorrected():
    """A value that is already a valid exact multiple is returned unchanged."""
    s = _scanner()
    assert s._extract_signatures("16960") == [16960]
    assert s._extract_signatures("25620") == [25620]


def test_extract_drops_ambiguous_misread():
    """An ambiguous misread produces no signature (no false lock)."""
    s = _scanner()
    assert s._extract_signatures("29620") == []


def test_ocr_orders_signatures_by_confidence():
    """A low-confidence stray number must not beat the real reading."""
    s = _scanner()
    reader = MagicMock()
    reader.readtext.return_value = [
        (None, "74400", 0.20),  # stray / garbage read
        (None, "3540", 0.97),
    ]
    s._ocr_reader, s._ocr_initialized = reader, True
    signatures, _, _ = s._ocr_signature(np.zeros((10, 10), np.uint8))
    assert signatures[0] == 3540
