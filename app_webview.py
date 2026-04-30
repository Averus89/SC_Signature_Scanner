#!/usr/bin/env python3
"""
SC Signature Scanner — webview entry point.

Hosts the React UI (ui/main/index.html) inside a pywebview window backed by
WebView2 on Windows. The Python core (scanner, monitor, config) is exposed
to JavaScript via the Bridge class as `pywebview.api.*`.

Runs the existing tkinter splash screen during heavy imports, then hands off
to pywebview's event loop. The legacy `main.py` (full tkinter app) remains
runnable in parallel until the migration is complete.
"""

from __future__ import annotations

# Show splash immediately, before any heavy imports
from splash import show_splash
_splash = show_splash()

_splash.set_status("Loading core modules...")
import sys
import threading
from pathlib import Path

import paths
_splash.pump(10)

_splash.set_status("Loading OCR engine...")

# Load OCR (the heavy import) on a background thread so the splash keeps animating
_scanner_module = None
_scanner_error: BaseException | None = None


def _load_scanner() -> None:
    global _scanner_module, _scanner_error
    try:
        import scanner as _mod
        _scanner_module = _mod
    except Exception as e:  # noqa: BLE001 — re-raised on the main thread below
        _scanner_error = e


_loader_thread = threading.Thread(target=_load_scanner, daemon=True)
_loader_thread.start()
while _loader_thread.is_alive():
    _splash.pump(5)
_loader_thread.join()

if _scanner_error:
    _splash.close()
    raise _scanner_error

SignatureScanner = _scanner_module.SignatureScanner
_splash.pump(10)

_splash.set_status("Loading UI components...")
import webview
from config import Config
from bridge import Bridge
_splash.pump(5)


def _build_window_url() -> str:
    """Return a file:// URL for ui/main/index.html."""
    ui_path = (paths.get_base_path() / "ui" / "main" / "index.html").resolve()
    if not ui_path.exists():
        raise FileNotFoundError(f"UI entry point not found: {ui_path}")
    return ui_path.as_uri()


def _build_overlay_url() -> str:
    """Return a file:// URL for ui/overlay/index.html."""
    ui_path = (paths.get_base_path() / "ui" / "overlay" / "index.html").resolve()
    if not ui_path.exists():
        raise FileNotFoundError(f"Overlay entry point not found: {ui_path}")
    return ui_path.as_uri()


def _build_scanner() -> object | None:
    """Construct the SignatureScanner with the project's database."""
    db_path = paths.get_data_path() / "combat_analyst_db.json"
    if not db_path.exists():
        print(f"[app_webview] Signature database missing: {db_path}", file=sys.stderr)
        return None
    return SignatureScanner(db_path)


def main() -> None:
    _splash.set_status("Building bridge...")
    config = Config()
    scanner = _build_scanner()
    bridge = Bridge(scanner=scanner, config=config)
    _splash.pump(5)

    _splash.set_status("Opening console...")

    # Center the main window using screen dims from the live splash tk root.
    main_w, main_h = 1020, 800
    screen_w = _splash.root.winfo_screenwidth()
    screen_h = _splash.root.winfo_screenheight()
    main_x = max(0, (screen_w - main_w) // 2)
    main_y = max(0, (screen_h - main_h) // 2)

    main_window = webview.create_window(
        title="SC Signature Scanner",
        url=_build_window_url(),
        js_api=bridge,
        width=main_w,
        height=main_h,
        x=main_x,
        y=main_y,
        min_size=(960, 700),
        resizable=True,
        frameless=True,
        easy_drag=False,
        background_color="#0a0e14",
    )

    # Overlay window — hidden by default, shown only on detection / test / placement.
    # Position from saved settings; sized to fit the card with a little margin
    # (overlay.jsx's #root pads + cards autosize).
    cfg = config.load() or {}
    overlay_x = int(cfg.get("popup_position_x", 1920))
    overlay_y = int(cfg.get("popup_position_y", 1080))
    overlay_window = webview.create_window(
        title="SC Signature Scanner — Overlay",
        url=_build_overlay_url(),
        js_api=bridge,
        width=380,
        height=340,
        x=overlay_x,
        y=overlay_y,
        frameless=True,
        on_top=True,
        easy_drag=False,
        resizable=False,
        hidden=True,
        # Solid dark background matching the card's bottom-gradient color so
        # window edges blend with the card. Dropping `transparent=True`
        # removed the see-through effect but also removed the WebView2
        # composition artifacts that caused the "dislocation" backdrop.
        background_color="#0a0e14",
    )

    bridge._attach_windows(main_window, overlay_window)
    _splash.pump(5)

    _splash.close()
    webview.start(debug=False)


if __name__ == "__main__":
    main()
