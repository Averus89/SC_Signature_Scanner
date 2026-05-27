import pytest
from unittest.mock import patch

import window_finder


def test_window_info_is_immutable_dataclass():
    info = window_finder.WindowInfo(
        hwnd=12345,
        client_rect=(100, 200, 1920, 1080),
        is_minimized=False,
        is_foreground=True,
    )
    assert info.hwnd == 12345
    assert info.client_rect == (100, 200, 1920, 1080)
    # Frozen — assignment should raise
    with pytest.raises(Exception):
        info.hwnd = 1  # type: ignore[misc]


def _fake_enum_returning(hwnds_with_titles):
    """Build a fake win32gui.EnumWindows that yields the given (hwnd, title) pairs."""
    def fake_enum_windows(callback, _):
        for hwnd, _title in hwnds_with_titles:
            callback(hwnd, None)
    return fake_enum_windows


def test_find_sc_window_returns_none_when_no_match():
    with patch.object(window_finder, "_iter_top_level_windows", return_value=iter([])):
        assert window_finder.find_sc_window() is None


def test_find_sc_window_matches_by_process_name():
    fake = {
        9999: {
            "process_name": "starcitizen.exe",
            "title": "Star Citizen",
            "client_rect": (10, 20, 1920, 1080),
            "is_minimized": False,
            "is_foreground": True,
        }
    }
    with patch.object(window_finder, "_iter_top_level_windows", return_value=iter(fake.items())):
        info = window_finder.find_sc_window()
    assert info is not None
    assert info.hwnd == 9999
    assert info.client_rect == (10, 20, 1920, 1080)
    assert info.is_minimized is False


def test_find_sc_window_matches_case_insensitive_process_name():
    fake = {
        7: {
            "process_name": "StarCitizen.EXE",
            "title": "Star Citizen",
            "client_rect": (0, 0, 800, 600),
            "is_minimized": False,
            "is_foreground": False,
        }
    }
    with patch.object(window_finder, "_iter_top_level_windows", return_value=iter(fake.items())):
        info = window_finder.find_sc_window()
    assert info is not None
    assert info.hwnd == 7


def test_find_sc_window_falls_back_to_title_when_process_lookup_fails():
    """psutil may raise on a foreign process — title fallback must still match."""
    fake = {
        42: {
            "process_name": None,  # simulate psutil failure
            "title": "Star Citizen",
            "client_rect": (0, 0, 800, 600),
            "is_minimized": False,
            "is_foreground": False,
        }
    }
    with patch.object(window_finder, "_iter_top_level_windows", return_value=iter(fake.items())):
        info = window_finder.find_sc_window()
    assert info is not None
    assert info.hwnd == 42
