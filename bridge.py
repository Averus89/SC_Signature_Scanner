#!/usr/bin/env python3
"""
Bridge between the React UI (ui/main/) and the Python core.

Public methods on Bridge are exposed to JavaScript as `pywebview.api.<name>`.
Methods prefixed with `_` are private and NOT exposed.

Slow operations (OCR scans) run on background threads and push results to JS
via `window.<callback>(payload)` using pywebview's evaluate_js.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import webview

from config import Config
from monitor import ScreenshotMonitor


class Bridge:
    """js_api class for the main pywebview window.

    All public (non-underscore) methods become callable from JavaScript as
    `pywebview.api.<method_name>(...)` and return Promises.
    """

    def __init__(self, scanner: Any, config: Config) -> None:
        self.scanner = scanner
        self.config = config
        self.monitor: Optional[ScreenshotMonitor] = None
        self._window: Optional[webview.Window] = None

    # ---- Private setup (not exposed to JS) ---------------------------------

    def _attach_window(self, window: webview.Window) -> None:
        """Store the webview window reference once it has been created."""
        self._window = window

    # ---- Initial state ------------------------------------------------------

    def get_initial_state(self) -> dict[str, Any]:
        """Return state for the React app to bootstrap with."""
        cfg = self.config.load() or {}
        return {
            "screenshotFolder": cfg.get("screenshot_folder", ""),
            "monitoring": False,
            "version": "5.0.0-webview",
        }

    # ---- Folder picker ------------------------------------------------------

    def pick_screenshot_folder(self) -> Optional[str]:
        """Open the native folder dialog. Returns the selected path or None."""
        if not self._window:
            return None
        result = self._window.create_file_dialog(webview.FOLDER_DIALOG)
        if not result:
            return None
        path = result[0] if isinstance(result, (list, tuple)) else result
        self.config.set("screenshot_folder", str(path))
        return str(path)

    def set_screenshot_folder(self, path: str) -> bool:
        return self.config.set("screenshot_folder", path)

    # ---- Monitoring ---------------------------------------------------------

    def start_monitoring(self) -> dict[str, Any]:
        cfg = self.config.load() or {}
        folder = cfg.get("screenshot_folder", "")
        if not folder or not Path(folder).is_dir():
            return {
                "ok": False,
                "error": "Screenshot folder is not set or does not exist.",
            }
        if self.monitor and self.monitor.is_running:
            return {"ok": True, "alreadyRunning": True}

        self.monitor = ScreenshotMonitor(
            folder=folder,
            callback=self._on_screenshot,
        )
        self.monitor.start()
        return {"ok": True}

    def stop_monitoring(self) -> dict[str, Any]:
        if self.monitor:
            self.monitor.stop()
            self.monitor = None
        return {"ok": True}

    # ---- Window controls (frameless mode) -----------------------------------

    def minimize_window(self) -> None:
        if self._window:
            self._window.minimize()

    def maximize_window(self) -> None:
        if self._window:
            self._window.toggle_fullscreen()

    def close_window(self) -> None:
        if self._window:
            self._window.destroy()

    # ---- Test detection -----------------------------------------------------

    def test_detection(self) -> dict[str, Any]:
        """Pick an image, scan it on a background thread, push result to JS."""
        if not self._window:
            return {"ok": False, "error": "Window not ready."}
        files = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=False,
            file_types=(
                "Image files (*.png;*.jpg;*.jpeg;*.webp;*.bmp)",
                "All files (*.*)",
            ),
        )
        if not files:
            return {"ok": True, "cancelled": True}
        path_str = files[0] if isinstance(files, (list, tuple)) else files
        threading.Thread(
            target=self._scan_and_push,
            args=(Path(path_str),),
            daemon=True,
        ).start()
        return {"ok": True}

    # ---- Internals (not exposed) -------------------------------------------

    def _on_screenshot(self, filepath: Path) -> None:
        """Callback fired on the watchdog thread when a new file appears."""
        self._scan_and_push(filepath)

    def _scan_and_push(self, filepath: Path) -> None:
        """Run a scan and push the result to the JS layer."""
        try:
            result = self.scanner.scan_image(filepath) if self.scanner else None
        except Exception as e:  # noqa: BLE001 — surfaced to UI as error string
            result = {"error": f"Scan failed: {e}"}

        payload = self._build_detection_payload(filepath, result)
        self._push_to_js("onDetection", payload)

    @staticmethod
    def _build_detection_payload(
        filepath: Path,
        result: Optional[dict[str, Any]],
    ) -> dict[str, Any]:
        ts = datetime.now().strftime("%H:%M:%S")
        if result is None:
            return {
                "time": ts,
                "file": filepath.name,
                "sig": None,
                "matches": [],
                "error": "No signature detected",
            }
        if result.get("error"):
            return {
                "time": ts,
                "file": filepath.name,
                "sig": None,
                "matches": [],
                "error": result["error"],
            }
        return {
            "time": ts,
            "file": filepath.name,
            "sig": result.get("signature"),
            "allSignatures": result.get("all_signatures", []),
            "matches": result.get("matches", []),
            "method": result.get("method"),
            "ocrConfidence": result.get("ocr_confidence"),
            "error": None,
        }

    def _push_to_js(self, fn_name: str, payload: Any) -> None:
        """Invoke `window.<fn_name>(payload)` in the renderer."""
        if not self._window:
            return
        try:
            js = f"window.{fn_name} && window.{fn_name}({json.dumps(payload)})"
            self._window.evaluate_js(js)
        except Exception as e:  # noqa: BLE001 — best-effort UI push
            print(f"[bridge] evaluate_js failed: {e}")
