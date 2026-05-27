"""Locate the running Star Citizen window and return its client-area rect.

Used by live_capture to point mss.grab at the correct absolute screen rect.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Optional

import psutil
import win32con
import win32gui
import win32process


SC_PROCESS_NAME = "starcitizen.exe"
SC_TITLE_PREFIX = "star citizen"  # case-insensitive substring match


@dataclass(frozen=True)
class WindowInfo:
    """Immutable snapshot of the SC window's geometry at the moment of lookup."""

    hwnd: int
    client_rect: tuple[int, int, int, int]  # (x, y, w, h) in screen coords
    is_minimized: bool
    is_foreground: bool


def _iter_top_level_windows() -> Iterator[tuple[int, dict]]:
    """Yield (hwnd, info) for each visible top-level window.

    `info` keys: process_name (str | None), title (str), client_rect, is_minimized, is_foreground.
    """
    hwnds: list[int] = []

    def collect(hwnd: int, _: object) -> bool:
        if win32gui.IsWindowVisible(hwnd):
            hwnds.append(hwnd)
        return True

    win32gui.EnumWindows(collect, None)
    fg = win32gui.GetForegroundWindow()

    for hwnd in hwnds:
        title = win32gui.GetWindowText(hwnd) or ""

        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            process_name = psutil.Process(pid).name() if pid else None
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            process_name = None

        # GetClientRect returns (0,0,w,h); ClientToScreen translates to screen coords.
        try:
            left, top, right, bottom = win32gui.GetClientRect(hwnd)
            sx, sy = win32gui.ClientToScreen(hwnd, (left, top))
            client_rect = (sx, sy, right - left, bottom - top)
        except Exception:
            continue

        try:
            placement = win32gui.GetWindowPlacement(hwnd)
            is_minimized = placement[1] == win32con.SW_SHOWMINIMIZED
        except Exception:
            is_minimized = False

        yield hwnd, {
            "process_name": process_name,
            "title": title,
            "client_rect": client_rect,
            "is_minimized": is_minimized,
            "is_foreground": hwnd == fg,
        }


def find_sc_window() -> Optional[WindowInfo]:
    """Locate Star Citizen's top-level window.

    Match by process name first (starcitizen.exe, case-insensitive). Fall back
    to window-title match when psutil can't read the process (rare; happens on
    elevated processes the current user doesn't own).

    Returns None if no match found.
    """
    title_fallback: Optional[tuple[int, dict]] = None

    for hwnd, info in _iter_top_level_windows():
        proc = (info.get("process_name") or "").lower()
        if proc == SC_PROCESS_NAME:
            return WindowInfo(
                hwnd=hwnd,
                client_rect=info["client_rect"],
                is_minimized=info["is_minimized"],
                is_foreground=info["is_foreground"],
            )
        title = (info.get("title") or "").lower()
        if SC_TITLE_PREFIX in title and title_fallback is None:
            title_fallback = (hwnd, info)

    if title_fallback is not None:
        hwnd, info = title_fallback
        return WindowInfo(
            hwnd=hwnd,
            client_rect=info["client_rect"],
            is_minimized=info["is_minimized"],
            is_foreground=info["is_foreground"],
        )

    return None
