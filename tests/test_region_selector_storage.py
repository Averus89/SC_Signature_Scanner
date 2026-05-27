"""Window-relative scan_region_window.json — load/save/clear/is_configured."""
from pathlib import Path
from unittest.mock import patch

import region_selector


def _patch_config_path(tmp_path: Path):
    """Redirect WINDOW_CONFIG_FILE to tmp_path so tests don't touch real user data."""
    return patch.object(region_selector, "WINDOW_CONFIG_FILE", tmp_path / "scan_region_window.json")


def test_load_window_region_returns_none_when_missing(tmp_path: Path):
    with _patch_config_path(tmp_path):
        assert region_selector.load_window_region() is None
        assert region_selector.is_window_region_configured() is False


def test_save_and_load_window_region_roundtrip(tmp_path: Path):
    with _patch_config_path(tmp_path):
        region_selector.save_window_region(100, 200, 300, 240)
        assert region_selector.load_window_region() == (100, 200, 300, 240)
        assert region_selector.is_window_region_configured() is True


def test_clear_window_region(tmp_path: Path):
    with _patch_config_path(tmp_path):
        region_selector.save_window_region(0, 0, 10, 10)
        region_selector.clear_window_region()
        assert region_selector.load_window_region() is None
        assert region_selector.is_window_region_configured() is False


def test_load_window_region_returns_none_on_invalid_json(tmp_path: Path):
    target = tmp_path / "scan_region_window.json"
    target.write_text("not json", encoding="utf-8")
    with _patch_config_path(tmp_path):
        assert region_selector.load_window_region() is None
