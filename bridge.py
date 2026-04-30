#!/usr/bin/env python3
"""
Bridge between the React UIs (ui/main, ui/overlay) and the Python core.

Public methods on Bridge are exposed to JavaScript as `pywebview.api.<name>`.
Methods prefixed with `_` are private and NOT exposed.

The main window receives detection log entries via `window.onDetection(...)`.
The overlay window receives match cards via `window.onOverlayDetection(...)`
and placement-mode toggles via `window.onPlacementMode(...)`.
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
import region_selector


class Bridge:
    """js_api class for the main pywebview window.

    All public (non-underscore) methods become callable from JavaScript as
    `pywebview.api.<method_name>(...)` and return Promises.
    """

    def __init__(self, scanner: Any, config: Config) -> None:
        self.scanner = scanner
        self.config = config
        self.monitor: Optional[ScreenshotMonitor] = None
        self._main_window: Optional[webview.Window] = None
        self._overlay_window: Optional[webview.Window] = None
        self._overlay_hide_timer: Optional[threading.Timer] = None
        self._overlay_prev_pos: Optional[tuple[int, int]] = None

    # ---- Private setup (not exposed to JS) ---------------------------------

    def _attach_windows(
        self,
        main: webview.Window,
        overlay: webview.Window,
    ) -> None:
        """Store references to both pywebview windows once they exist."""
        self._main_window = main
        self._overlay_window = overlay

    # ---- Initial state ------------------------------------------------------

    def get_initial_state(self) -> dict[str, Any]:
        """Return state for the React app to bootstrap with."""
        cfg = self.config.load() or {}
        return {
            "screenshotFolder": cfg.get("screenshot_folder", ""),
            "monitoring": False,
            "version": "5.1.0.dev4",
        }

    # ---- Folder picker ------------------------------------------------------

    def pick_screenshot_folder(self) -> Optional[str]:
        """Open the native folder dialog. Returns the selected path or None."""
        if not self._main_window:
            return None
        result = self._main_window.create_file_dialog(webview.FileDialog.FOLDER)
        if not result:
            return None
        path = result[0] if isinstance(result, (list, tuple)) else result
        self.config.set("screenshot_folder", str(path))
        return str(path)

    def set_screenshot_folder(self, path: str) -> bool:
        return self.config.set("screenshot_folder", path)

    # ---- Settings -----------------------------------------------------------

    # config.json (snake_case, scale as float) <-> React state (camelCase, scale as int %)
    _SETTINGS_DEFAULTS: dict[str, Any] = {
        "popup_position_x": 1920,
        "popup_position_y": 1080,
        "popup_duration": 10,
        "popup_scale": 1.0,
        "debug_mode": False,
        "debug_folder": "",
    }

    def get_settings(self) -> dict[str, Any]:
        """Return current settings translated for the React UI."""
        cfg = self.config.load() or {}
        return {
            "popupX": int(
                cfg.get("popup_position_x", self._SETTINGS_DEFAULTS["popup_position_x"])
            ),
            "popupY": int(
                cfg.get("popup_position_y", self._SETTINGS_DEFAULTS["popup_position_y"])
            ),
            "duration": int(
                cfg.get("popup_duration", self._SETTINGS_DEFAULTS["popup_duration"])
            ),
            "scale": int(
                round(
                    float(
                        cfg.get("popup_scale", self._SETTINGS_DEFAULTS["popup_scale"])
                    )
                    * 100
                )
            ),
            "debug": bool(cfg.get("debug_mode", self._SETTINGS_DEFAULTS["debug_mode"])),
            "debugFolder": str(
                cfg.get("debug_folder", self._SETTINGS_DEFAULTS["debug_folder"])
            ),
        }

    def save_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        """Persist UI settings into config.json (snake_case schema).

        Applies side effects on the live scanner (debug toggle/folder) and
        on the live overlay window (position when X/Y changed via the
        numeric inputs).
        """
        cfg = self.config.load() or {}
        position_changed = False
        if "popupX" in settings:
            cfg["popup_position_x"] = int(settings["popupX"])
            position_changed = True
        if "popupY" in settings:
            cfg["popup_position_y"] = int(settings["popupY"])
            position_changed = True
        if "duration" in settings:
            cfg["popup_duration"] = max(1, int(settings["duration"]))
        if "scale" in settings:
            cfg["popup_scale"] = max(0.5, min(2.0, float(settings["scale"]) / 100.0))
        if "debug" in settings:
            cfg["debug_mode"] = bool(settings["debug"])
        if "debugFolder" in settings:
            cfg["debug_folder"] = str(settings["debugFolder"])

        ok = self.config.save(cfg)

        # Apply live to the scanner so the next scan picks up the change
        if self.scanner is not None:
            debug_dir = Path(cfg["debug_folder"]) if cfg.get("debug_folder") else None
            self.scanner.enable_debug(bool(cfg.get("debug_mode", False)), debug_dir)

        # Move the overlay window live if its position was edited via numeric inputs.
        # Skipped while in placement mode so we don't fight the user's drag.
        if (
            position_changed
            and self._overlay_window is not None
            and self._overlay_prev_pos is None
        ):
            try:
                self._overlay_window.move(
                    int(cfg["popup_position_x"]),
                    int(cfg["popup_position_y"]),
                )
            except Exception as e:  # noqa: BLE001 — best effort, log only
                print(f"[bridge] overlay move failed: {e}")

        return {"ok": ok}

    def pick_debug_folder(self) -> Optional[str]:
        """Open the native folder dialog for the debug output folder."""
        if not self._main_window:
            return None
        result = self._main_window.create_file_dialog(webview.FileDialog.FOLDER)
        if not result:
            return None
        path = result[0] if isinstance(result, (list, tuple)) else result
        self.config.set("debug_folder", str(path))
        if self.scanner is not None:
            self.scanner.enable_debug(
                bool(self.config.get("debug_mode", False)),
                Path(str(path)),
            )
        return str(path)

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
        if self._main_window:
            self._main_window.minimize()

    def maximize_window(self) -> None:
        if self._main_window:
            self._main_window.toggle_fullscreen()

    def close_window(self) -> None:
        if self._main_window:
            self._main_window.destroy()

    # ---- Test detection -----------------------------------------------------

    def test_detection(self) -> dict[str, Any]:
        """Pick an image, scan it on a background thread, push result to JS."""
        if not self._main_window:
            return {"ok": False, "error": "Window not ready."}
        files = self._main_window.create_file_dialog(
            webview.FileDialog.OPEN,
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

    # ---- Scan region --------------------------------------------------------

    def get_scan_region(self) -> Optional[dict[str, int]]:
        """Return the saved OCR scan region or None if not configured."""
        region = region_selector.load_region()
        if region is None:
            return None
        x1, y1, x2, y2 = region
        return {
            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "width": x2 - x1, "height": y2 - y1,
        }

    def pick_region(self) -> dict[str, Any]:
        """Pick a screenshot, then open the legacy tk-based region selector
        on it. Blocks until the user clicks Save or Cancel. The selector
        writes through to scan_region.json on save; this method returns the
        new region (or None if cancelled).

        The main console stays visible during the screenshot picker (so the
        user has context), then minimizes once the fullscreen region selector
        opens, and restores when it closes.
        """
        if self._main_window is None:
            return {"ok": False, "error": "Window not ready."}

        files = self._main_window.create_file_dialog(
            webview.FileDialog.OPEN,
            allow_multiple=False,
            file_types=(
                "Image files (*.png;*.jpg;*.jpeg)",
                "All files (*.*)",
            ),
        )
        if not files:
            return {"ok": True, "cancelled": True, "region": None}
        image_path = Path(files[0] if isinstance(files, (list, tuple)) else files)

        captured: dict[str, int] = {}

        def _on_save(x1: int, y1: int, x2: int, y2: int) -> None:
            captured.update({"x1": x1, "y1": y1, "x2": x2, "y2": y2})

        try:
            self._main_window.minimize()
        except Exception as e:  # noqa: BLE001 — best effort
            print(f"[bridge] main minimize failed: {e}")

        try:
            selector = region_selector.RegionSelector(parent=None, on_save=_on_save)
            selector.open(image_path=image_path)
        except Exception as e:  # noqa: BLE001 — surface error string to UI
            return {"ok": False, "error": f"Region selector failed: {e}"}
        finally:
            self._restore_main_window()

        if not captured:
            return {"ok": True, "cancelled": True, "region": None}

        return {
            "ok": True,
            "region": {
                **captured,
                "width": captured["x2"] - captured["x1"],
                "height": captured["y2"] - captured["y1"],
            },
        }

    def _restore_main_window(self) -> None:
        """Bring the main console back from minimized."""
        if self._main_window is None:
            return
        try:
            self._main_window.restore()
        except Exception as e:  # noqa: BLE001 — best effort
            print(f"[bridge] main restore failed: {e}")

    def clear_scan_region(self) -> dict[str, bool]:
        """Delete the saved scan region."""
        region_selector.clear_region()
        return {"ok": True}

    # ---- Overlay ------------------------------------------------------------

    def test_overlay(self) -> dict[str, Any]:
        """Push a sample match payload to the overlay window."""
        sample = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "sig": 3585,
            "match": {
                "tier": "rare",
                "name": "Gold + Borase + Bexalite",
                "cat": "ship",
                "notes": "Mid-tier · sig 3585",
            },
        }
        self._show_overlay(sample)
        return {"ok": True}

    def enter_overlay_placement_mode(self) -> dict[str, Any]:
        """Show the overlay with a sample card, marked draggable."""
        if self._overlay_window is None:
            return {"ok": False, "error": "Overlay window not ready."}

        # Cancel any pending auto-hide so the placement card stays visible.
        self._cancel_overlay_hide()

        # Remember current position so cancel can revert.
        cfg = self.config.load() or {}
        self._overlay_prev_pos = (
            int(
                cfg.get("popup_position_x", self._SETTINGS_DEFAULTS["popup_position_x"])
            ),
            int(
                cfg.get("popup_position_y", self._SETTINGS_DEFAULTS["popup_position_y"])
            ),
        )

        self._push_to_overlay("onPlacementMode", True)
        try:
            self._overlay_window.show()
        except Exception as e:  # noqa: BLE001 — best effort
            print(f"[bridge] overlay show failed: {e}")
        return {"ok": True}

    def confirm_overlay_position(self) -> dict[str, Any]:
        """Read the overlay's live position, persist it, exit placement mode."""
        if self._overlay_window is None:
            return {"ok": False, "error": "Overlay window not ready."}

        try:
            x = int(self._overlay_window.x)
            y = int(self._overlay_window.y)
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": f"Failed to read window position: {e}"}

        cfg = self.config.load() or {}
        cfg["popup_position_x"] = x
        cfg["popup_position_y"] = y
        self.config.save(cfg)

        self._overlay_prev_pos = None
        self._push_to_overlay("onPlacementMode", False)
        self._push_to_main("onOverlayPositionSaved", {"popupX": x, "popupY": y})
        try:
            self._overlay_window.hide()
        except Exception as e:  # noqa: BLE001
            print(f"[bridge] overlay hide failed: {e}")

        return {"ok": True, "popupX": x, "popupY": y}

    def cancel_overlay_placement(self) -> dict[str, Any]:
        """Restore the previous overlay position and hide the window."""
        if self._overlay_window is None:
            return {"ok": False, "error": "Overlay window not ready."}

        if self._overlay_prev_pos is not None:
            try:
                self._overlay_window.move(*self._overlay_prev_pos)
            except Exception as e:  # noqa: BLE001
                print(f"[bridge] overlay revert move failed: {e}")
        self._overlay_prev_pos = None

        self._push_to_overlay("onPlacementMode", False)
        try:
            self._overlay_window.hide()
        except Exception as e:  # noqa: BLE001
            print(f"[bridge] overlay hide failed: {e}")
        return {"ok": True}

    # ---- Internals (not exposed) -------------------------------------------

    def _on_screenshot(self, filepath: Path) -> None:
        """Callback fired on the watchdog thread when a new file appears."""
        self._scan_and_push(filepath)

    def _scan_and_push(self, filepath: Path) -> None:
        """Run a scan and push the result to both windows."""
        try:
            result = self.scanner.scan_image(filepath) if self.scanner else None
        except Exception as e:  # noqa: BLE001 — surfaced to UI as error string
            result = {"error": f"Scan failed: {e}"}

        payload = self._build_detection_payload(filepath, result)
        self._push_to_main("onDetection", payload)

        # Show the overlay only when we have a real match — never for "NO LOCK"
        # or scan errors (the user doesn't want noise popups).
        if not payload.get("error") and payload.get("matches"):
            self._show_overlay(self._build_overlay_payload(payload))

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

    @staticmethod
    def _build_overlay_payload(detection: dict[str, Any]) -> dict[str, Any]:
        """Translate a main-window detection payload into the overlay's match shape."""
        matches = detection.get("matches") or []
        first = matches[0] if matches else {}
        return {
            "time": detection.get("time"),
            "sig": detection.get("sig"),
            "match": {
                "tier": first.get("tier", "unknown"),
                "name": first.get("name", ""),
                "cat": first.get("category", first.get("cat", "")),
                "notes": first.get("notes", ""),
            },
        }

    def _show_overlay(self, payload: dict[str, Any]) -> None:
        """Push a payload to the overlay, show it, and arm the auto-hide timer."""
        if self._overlay_window is None:
            return
        # Don't override placement mode with a detection.
        if self._overlay_prev_pos is not None:
            return

        self._push_to_overlay("onOverlayDetection", payload)
        try:
            self._overlay_window.show()
        except Exception as e:  # noqa: BLE001
            print(f"[bridge] overlay show failed: {e}")

        cfg = self.config.load() or {}
        duration = max(
            1, int(cfg.get("popup_duration", self._SETTINGS_DEFAULTS["popup_duration"]))
        )
        self._cancel_overlay_hide()
        self._overlay_hide_timer = threading.Timer(duration, self._hide_overlay)
        self._overlay_hide_timer.daemon = True
        self._overlay_hide_timer.start()

    def _hide_overlay(self) -> None:
        if self._overlay_window is None:
            return
        if self._overlay_prev_pos is not None:
            return  # Don't auto-hide while placing
        try:
            self._overlay_window.hide()
        except Exception as e:  # noqa: BLE001
            print(f"[bridge] overlay auto-hide failed: {e}")

    def _cancel_overlay_hide(self) -> None:
        if self._overlay_hide_timer is not None:
            self._overlay_hide_timer.cancel()
            self._overlay_hide_timer = None

    def _push_to_main(self, fn_name: str, payload: Any) -> None:
        self._evaluate(self._main_window, fn_name, payload)

    def _push_to_overlay(self, fn_name: str, payload: Any) -> None:
        self._evaluate(self._overlay_window, fn_name, payload)

    @staticmethod
    def _evaluate(window: Optional[webview.Window], fn_name: str, payload: Any) -> None:
        """Invoke `window.<fn_name>(payload)` in the renderer."""
        if window is None:
            return
        try:
            js = f"window.{fn_name} && window.{fn_name}({json.dumps(payload)})"
            window.evaluate_js(js)
        except Exception as e:  # noqa: BLE001 — best-effort UI push
            print(f"[bridge] evaluate_js failed: {e}")
