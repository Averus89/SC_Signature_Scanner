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
import re
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

    # Base overlay window size at scale=1.0. The window resizes to
    # base × scale after each show so scaled content fits without clipping.
    # Sized for a single-mineral name on one line (real detections always
    # match exactly one mineral per signature). Placement mode adds ~50px
    # for the (30%-shrunk) SAVE/CANCEL toolbar.
    _OVERLAY_BASE_W = 272
    _OVERLAY_BASE_H = 152
    _OVERLAY_PLACEMENT_BASE_H = 200

    def __init__(self, scanner: Any, config: Config) -> None:
        self.scanner = scanner
        self.config = config
        self.monitor: Optional[ScreenshotMonitor] = None
        self._main_window: Optional[webview.Window] = None
        self._overlay_window: Optional[webview.Window] = None
        self._overlay_prev_pos: Optional[tuple[int, int]] = None
        # Tracked so live setting changes (scale/duration) can update the
        # currently-visible overlay without showing a hidden one.
        self._overlay_visible: bool = False
        # Last payload pushed to the overlay — re-pushed on scale changes so
        # the rendered card picks up the new zoom factor without a relaunch.
        self._overlay_last_payload: Optional[dict[str, Any]] = None

        # Apply persisted debug settings to the scanner now so saved state
        # takes effect immediately on next scan — without the user having
        # to re-touch Settings after every relaunch.
        if self.scanner is not None:
            cfg = self.config.load() or {}
            debug_dir = Path(cfg["debug_folder"]) if cfg.get("debug_folder") else None
            self.scanner.enable_debug(
                bool(cfg.get("debug_mode", False)),
                debug_dir,
            )

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

    @staticmethod
    def _short_version(full: str) -> str:
        """Trim to major.minor for the public display:
        '6.0.0' -> '6.0', '6.1.2' -> '6.1', '7.0' -> '7.0'."""
        parts = full.split(".")
        return ".".join(parts[:2]) if len(parts) >= 2 else full

    def get_initial_state(self) -> dict[str, Any]:
        """Return state for the React app to bootstrap with."""
        cfg = self.config.load() or {}
        # Public version drops the .devN suffix and any trailing .0 patch;
        # the full string stays for the About panel's top-right status pill.
        from version_checker import CURRENT_VERSION
        public_version = self._short_version(CURRENT_VERSION.split(".dev")[0])
        return {
            "screenshotFolder": cfg.get("screenshot_folder", ""),
            "monitoring": False,
            "version": public_version,
            "versionDev": CURRENT_VERSION,
            "ocrEngine": getattr(self.scanner, "engine_name", "—") if self.scanner else "—",
        }

    # ---- Folder picker ------------------------------------------------------

    def _start_dir(self, prefer: str) -> Optional[str]:
        """Return a sensible starting directory for a file dialog so the
        OS doesn't reuse the last-used folder across unrelated pickers
        (e.g. opening the screenshot picker from the debug-folder location).

        prefer: 'screenshot' or 'debug'.
        """
        cfg = self.config.load() or {}
        key = "screenshot_folder" if prefer == "screenshot" else "debug_folder"
        candidate = cfg.get(key) or ""
        if candidate and Path(candidate).is_dir():
            return str(candidate)
        return None

    def pick_screenshot_folder(self) -> Optional[str]:
        """Open the native folder dialog. Returns the selected path or None."""
        if not self._main_window:
            return None
        result = self._main_window.create_file_dialog(
            webview.FileDialog.FOLDER,
            directory=self._start_dir("screenshot") or "",
        )
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
        on the live overlay window (move when position changed; resize +
        re-push when scale changed and overlay is visible).
        """
        cfg = self.config.load() or {}

        # Track only ACTUAL value changes so we don't ping the overlay window
        # on every keystroke. React always sends the full settings dict, so
        # checking just for key presence would resize/move on every save.
        old_x = int(cfg.get("popup_position_x", 0))
        old_y = int(cfg.get("popup_position_y", 0))
        old_scale = float(cfg.get("popup_scale", 1.0))

        new_x = int(settings["popupX"]) if "popupX" in settings else old_x
        new_y = int(settings["popupY"]) if "popupY" in settings else old_y
        new_scale = (
            max(0.5, min(2.0, float(settings["scale"]) / 100.0))
            if "scale" in settings else old_scale
        )

        cfg["popup_position_x"] = new_x
        cfg["popup_position_y"] = new_y
        cfg["popup_scale"] = new_scale
        if "duration" in settings:
            cfg["popup_duration"] = max(1, int(settings["duration"]))
        if "debug" in settings:
            cfg["debug_mode"] = bool(settings["debug"])
        if "debugFolder" in settings:
            cfg["debug_folder"] = str(settings["debugFolder"])

        ok = self.config.save(cfg)

        if self.scanner is not None:
            debug_dir = Path(cfg["debug_folder"]) if cfg.get("debug_folder") else None
            self.scanner.enable_debug(bool(cfg.get("debug_mode", False)), debug_dir)

        position_changed = (new_x != old_x) or (new_y != old_y)
        scale_changed = abs(new_scale - old_scale) > 1e-6

        # Move only if X or Y actually changed AND we're not in placement mode
        # (placement uses an explicit drag flow). Calling move() unconditionally
        # was previously side-effecting hidden WebView2 windows into visibility.
        if (
            position_changed
            and self._overlay_window is not None
            and self._overlay_prev_pos is None
        ):
            try:
                self._overlay_window.move(new_x, new_y)
            except Exception as e:  # noqa: BLE001 — best effort, log only
                print(f"[bridge] overlay move failed: {e}")

        # Live scale propagation: when the scale slider moves, resize the
        # overlay window and re-push the last payload so React picks up the
        # new zoom factor without waiting for the next detection.
        if scale_changed and self._overlay_window is not None:
            if self._overlay_prev_pos is not None:
                # Placement mode is active — resize with toolbar height and
                # re-push the placement signal so React updates zoom too.
                self._resize_overlay(new_scale, with_toolbar=True)
                self._push_to_overlay(
                    "onPlacementMode", {"active": True, "scale": new_scale}
                )
            elif self._overlay_visible and self._overlay_last_payload is not None:
                self._resize_overlay(new_scale)
                refreshed = {**self._overlay_last_payload, "scale": new_scale}
                self._overlay_last_payload = refreshed
                self._push_to_overlay("onOverlayDetection", refreshed)

        return {"ok": ok}

    def pick_debug_folder(self) -> Optional[str]:
        """Open the native folder dialog for the debug output folder."""
        if not self._main_window:
            return None
        result = self._main_window.create_file_dialog(
            webview.FileDialog.FOLDER,
            directory=self._start_dir("debug") or "",
        )
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
            directory=self._start_dir("screenshot") or "",
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

    # ---- Updates ------------------------------------------------------------

    def check_for_updates(self) -> dict[str, Any]:
        """Hit GitHub's releases API to see if a newer version is published.

        Returns a JSON-friendly dict the About panel can render directly.
        """
        try:
            import version_checker
            result = version_checker.check_for_updates()
        except Exception as e:  # noqa: BLE001 — surfaced to UI as error string
            return {"ok": False, "error": f"Update check failed: {e}"}

        if not result:
            return {"ok": False, "error": "Update check returned no result."}

        is_newer, latest, html_url = result
        if latest is None:
            return {"ok": False, "error": "Could not reach the update endpoint."}

        return {
            "ok": True,
            "isNewer": bool(is_newer),
            "latestVersion": latest,
            "downloadUrl": html_url or "",
        }

    # ---- Signature database -------------------------------------------------

    def get_signature_db(self) -> dict[str, list[dict[str, Any]]]:
        """Return the loaded signature DB shaped for the React UI.

        Replaces the hardcoded JS tables in `data.jsx` so codex/index lookups
        and the reveal card's match/tier all use Python's source of truth.
        """
        scanner = self.scanner
        if scanner is None:
            return {"minerals": [], "ground": [], "salvage": []}

        minerals: list[dict[str, Any]] = []
        for sig, info in getattr(scanner, "minable_signatures", {}).items():
            minerals.append({
                "sig": int(sig),
                "name": info.get("mineral", info.get("name", "")),
                "tier": info.get("tier", "unknown"),
                "cat": "ship",
                "notes": "",
            })

        ground: list[dict[str, Any]] = []
        small_base = int(getattr(scanner, "ground_deposit_small_base", 0) or 0)
        large_base = int(getattr(scanner, "ground_deposit_large_base", 0) or 0)
        if small_base > 0:
            ground.append({
                "sig": small_base,
                "name": "Small Ground Deposit",
                "tier": "ground_s",
                "cat": "ground",
                "notes": "FPS / Hand mining",
            })
        if large_base > 0:
            ground.append({
                "sig": large_base,
                "name": "Large Ground Deposit",
                "tier": "ground_l",
                "cat": "ground",
                "notes": "ROC / Vehicle mining",
            })

        salvage: list[dict[str, Any]] = []
        per_panel = int(getattr(scanner, "salvage_per_panel", 0) or 0)
        if per_panel > 0:
            salvage.append({
                "sig": per_panel,
                "name": "Salvage Panel",
                "tier": "salvage",
                "cat": "salvage",
                "notes": "Per-panel base — multiples of this signal hull scrap",
            })
        for base_sig, debris_name in getattr(scanner, "salvage_debris_types", []):
            if int(base_sig) <= 0:
                continue
            salvage.append({
                "sig": int(base_sig),
                "name": debris_name,
                "tier": "salvage",
                "cat": "salvage",
                "notes": "Wreck debris base",
            })

        return {"minerals": minerals, "ground": ground, "salvage": salvage}

    # Strips a "(N×)" or "(Nx)" count suffix from scanner-side match names so
    # the bridge can rebuild them in "Name ×N" form.
    _COUNT_SUFFIX_RE = re.compile(r"\s*\(\d+[x×]\)\s*$")

    @staticmethod
    def _to_display_match(py_match: dict[str, Any]) -> dict[str, Any]:
        """Translate a scanner match dict into the React-side match shape."""
        category = py_match.get("category", "")
        tier = py_match.get("tier") or ""
        if not tier:
            if category in ("salvage", "salvage_debris"):
                tier = "salvage"
            elif category == "ground_deposits":
                variant = py_match.get("variant")
                tier = "ground_s" if variant == "small" else "ground_l" if variant == "large" else "unknown"
            else:
                tier = "unknown"

        if category == "ship_mining":
            cat = "ship"
        elif category in ("salvage", "salvage_debris"):
            cat = "salvage"
        elif category == "ground_deposits":
            cat = "ground"
        else:
            cat = ""

        # Build the display name. Goal: count-based matches all read
        # "{Base name} ×N", with ship_mining additionally surfacing a tier
        # subtitle the reveal card can render at a smaller size.
        #   ship_mining  → nameMain="Torite ×3" + nameSubtitle="(Uncommon)"
        #   salvage      → nameMain="Large Wreck Debris ×3", no subtitle
        #   ground       → nameMain="Small Ground Deposit ×3", no subtitle
        # `name` keeps the full single-line string for log/telemetry/overlay.
        full_name = py_match.get("name", "")
        name_main = full_name
        name_subtitle = ""
        count = int(py_match.get("count") or py_match.get("panels") or 1)

        if category == "ship_mining":
            mineral = py_match.get("mineral") or ""
            tier_raw = py_match.get("tier") or ""
            if mineral and tier_raw:
                count_part = f" ×{count}" if count > 1 else ""
                name_main = f"{mineral}{count_part}"
                name_subtitle = f"({tier_raw.capitalize()})"
                full_name = f"{name_main} {name_subtitle}".strip()
        elif category in ("salvage", "salvage_debris", "ground_deposits"):
            base_name = Bridge._COUNT_SUFFIX_RE.sub("", full_name)
            if count > 1:
                name_main = f"{base_name} ×{count}"
            else:
                name_main = base_name
            full_name = name_main

        # nameOnly = name without the count suffix, e.g. "Torite (Uncommon)"
        # for ship_mining, "Large Wreck Debris" for salvage/ground. Used by
        # the detection log's Classification column where Count has its own
        # cell.
        if name_subtitle:
            name_only = f"{py_match.get('mineral') or name_main} {name_subtitle}".strip()
        else:
            name_only = Bridge._COUNT_SUFFIX_RE.sub("", py_match.get("name", "")).strip()
            if not name_only:
                name_only = name_main

        return {
            "name": full_name,
            "nameMain": name_main,
            "nameSubtitle": name_subtitle,
            "nameOnly": name_only,
            "tier": tier,
            "cat": cat,
            "notes": py_match.get("mining_method") or "",
            "sig": int(py_match.get("signature") or 0),
            "count": int(py_match.get("count") or py_match.get("panels") or 1),
        }

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
            directory=self._start_dir("screenshot") or "",
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
                "name": "Gold (Rare)",
                "nameMain": "Gold",
                "nameSubtitle": "(Rare)",
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

        # Apply current scale so the user sees the actual size they're placing.
        scale = self._current_overlay_scale(cfg)

        self._push_to_overlay("onPlacementMode", {"active": True, "scale": scale})
        try:
            self._overlay_window.show()
            self._overlay_visible = True
        except Exception as e:  # noqa: BLE001 — best effort
            print(f"[bridge] overlay show failed: {e}")
        # resize must be called AFTER show — pywebview's resize() silently
        # no-ops on a hidden window in WebView2.
        self._resize_overlay(scale, with_toolbar=True)
        return {"ok": True}

    def hide_overlay(self) -> dict[str, bool]:
        """JS-callable hide. The overlay's React app calls this when its
        auto-hide setTimeout (driven by `popup_duration`) fires."""
        if self._overlay_window is None:
            return {"ok": False}
        # Don't hide while in placement mode — placement uses the explicit
        # confirm/cancel buttons.
        if self._overlay_prev_pos is not None:
            return {"ok": True}
        try:
            self._overlay_window.hide()
            self._overlay_visible = False
            self._overlay_last_payload = None
        except Exception as e:  # noqa: BLE001 — best effort
            print(f"[bridge] hide_overlay failed: {e}")
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
            self._overlay_visible = False
            self._overlay_last_payload = None
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
            self._overlay_visible = False
            self._overlay_last_payload = None
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
        raw_matches = result.get("matches", []) or []
        display_matches = [Bridge._to_display_match(m) for m in raw_matches]
        return {
            "time": ts,
            "file": filepath.name,
            "sig": result.get("signature"),
            "allSignatures": result.get("all_signatures", []),
            "matches": display_matches,
            "rawMatches": raw_matches,
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
                "nameMain": first.get("nameMain", ""),
                "nameSubtitle": first.get("nameSubtitle", ""),
                "cat": first.get("cat", ""),
                "notes": first.get("notes", ""),
            },
        }

    def _show_overlay(self, payload: dict[str, Any]) -> None:
        """Push a payload to the overlay and show it. Auto-hide is driven by
        the overlay's React app via setTimeout + a callback to hide_overlay,
        so the timing stays in sync with the progress-bar animation."""
        if self._overlay_window is None:
            return
        # Don't override placement mode with a detection.
        if self._overlay_prev_pos is not None:
            return

        cfg = self.config.load() or {}
        duration = max(
            1, int(cfg.get("popup_duration", self._SETTINGS_DEFAULTS["popup_duration"]))
        )
        scale = self._current_overlay_scale(cfg)

        enriched = {**payload, "duration": duration, "scale": scale}
        self._overlay_last_payload = enriched
        self._push_to_overlay("onOverlayDetection", enriched)
        try:
            self._overlay_window.show()
            self._overlay_visible = True
        except Exception as e:  # noqa: BLE001
            print(f"[bridge] overlay show failed: {e}")
        # resize must be called AFTER show — pywebview's resize() silently
        # no-ops on a hidden window in WebView2.
        self._resize_overlay(scale)

    def _current_overlay_scale(self, cfg: dict[str, Any]) -> float:
        return max(
            0.5,
            min(2.0, float(cfg.get("popup_scale", self._SETTINGS_DEFAULTS["popup_scale"]))),
        )

    def _resize_overlay(self, scale: float, with_toolbar: bool = False) -> None:
        if self._overlay_window is None:
            return
        base_h = self._OVERLAY_PLACEMENT_BASE_H if with_toolbar else self._OVERLAY_BASE_H
        try:
            self._overlay_window.resize(
                int(self._OVERLAY_BASE_W * scale),
                int(base_h * scale),
            )
        except Exception as e:  # noqa: BLE001 — best effort
            print(f"[bridge] overlay resize failed: {e}")

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
