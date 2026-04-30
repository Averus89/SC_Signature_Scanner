# Session Journal

A living journal that persists across compactions. Captures decisions, progress, and context.

## Current State
- **Focus:** webview UI migration on branch `feat/webview-migration`. Phase 3 verified and ready to commit.
- **Blocked:** nothing. PLACE OVERLAY + TEST OVERLAY confirmed working by user. Pending: commit Phase 3, then plan Phase 4 (region selector).
- **Pickup for next session:** Plan Phase 4 — wire `region_selector.py`'s screenshot+bounding-box flow into the React UI's `REGION` panel (currently disabled in nav). Phase 5 is the JS-side `data.jsx` mock → real Python DB swap (Phase 1 known limitation: ground/salvage/collision matches show NO LOCK in reveal card despite Python identifying them correctly).

## Log

### 2026-04-30 — Completed: Phase 3 verification + Settings cleanup
- User confirmed PLACE OVERLAY drag flow + TEST OVERLAY auto-hide both work flawlessly after two follow-up fixes:
  - Overlay window was 240px tall; toolbar (~70px) was getting clipped behind the bottom edge → bumped to 380×340.
  - Forgot `js_api=bridge` on the overlay window → SAVE/CANCEL buttons would have been silent no-ops even when visible. Added.
- Removed redundant in-Settings viewport thumbnail (fake screen + draggable card mock) since real PLACE OVERLAY supersedes it. JSX trimmed to instructions + X/Y readouts + CENTER + PLACE OVERLAY. `stageRef`/`dragging`/`onCardDown`/the mouse-tracking `useEffect` all gone. Orphaned CSS pruned: `.settings-screen`, `.screen-label`, `.screen-grid`, `.screen-handle`, `.screen-handle-card`, `.shc-*`, `.screen-overlay-handle`, `.overlay-mini`, `.settings-hint`. `useEffect` import dropped from `module-panels.jsx`.
- Cache buster `v=19` → `v=20`.

### 2026-04-30 — Completed: Phase 3 of webview UI migration (overlay window)
- New files: `ui/overlay/{index.html,overlay.jsx,styles.css}` — standalone match card page, no shared deps with `ui/main`.
- `bridge.py`: `_attach_window` → `_attach_windows(main, overlay)`. New JS-exposed methods: `test_overlay`, `enter_overlay_placement_mode`, `confirm_overlay_position`, `cancel_overlay_placement`. `_scan_and_push` now pushes log to main + match card to overlay (skipped on errors/no-match). Auto-hide via `threading.Timer(duration)`, rearmed on each new detection. `save_settings` moves overlay live when X/Y change via numeric inputs (skipped during placement mode).
- `app_webview.py`: second `webview.create_window` for overlay — `frameless=True, on_top=True, transparent=True, easy_drag=False, hidden=True`, sized 360×240, positioned at saved x/y.
- `ui/main/app.jsx`: `placeOverlay` + `testOverlay` callbacks; `window.onOverlayPositionSaved` listener keeps Settings X/Y in sync after a confirmed drag.
- `ui/main/module-panels.jsx`: PLACE OVERLAY button added; TEST OVERLAY enabled; both wired to bridge.
- Drag mechanism: `pywebview-drag-region` class toggled on card body during placement; native WebView2 drag — no JS plumbing.
- Version: `5.1.0.dev2` → `5.1.0.dev3`. DEVLOG entry added. NOT yet committed (awaiting smoke test).

### 2026-04-30 — Context: Phase 3 verification checklist (next session)
Manual tests to run after launching `python app_webview.py`:
1. Open SETTINGS → click PLACE OVERLAY. Overlay window should appear at saved x/y with sample "Gold + Borase + Bexalite, rare, sig 3585" card + green ✓ SAVE / red ✗ CANCEL footer.
2. Drag the card body across the desktop (over a running game ideally). Click ✓ SAVE → overlay hides; SETTINGS X/Y readouts should update to the new position; `config.json` `popup_position_x/y` should be updated.
3. Click PLACE OVERLAY again, drag, click ✗ CANCEL → overlay returns to previous saved position and hides.
4. Click TEST OVERLAY → sample card appears for `popup_duration` seconds then auto-hides.
5. ENGAGE monitoring with a real screenshot folder; drop a real SC screenshot in. Main window log AND overlay card should both update; overlay auto-hides after `popup_duration`.
6. While NOT in placement mode, edit X/Y inputs in SETTINGS — overlay should jump to the new position live.
7. NO LOCK / scan errors must NOT pop the overlay (only main-window log entry).

Known caveats to watch for during testing:
- `pywebview.Window.x` / `.y` — confirm they read live position on WebView2 (Windows). If they return launch-time x/y instead of current, fall back to a JS bridge that reads `window.screenX/screenY` (likely 0,0 in webview hosts) or implement drag tracking via mouse events + `move()`.
- `transparent=True` on WebView2 — if the card has a black/grey background instead of being floating-on-game, the WebView2 transparent flag may not be honored on this Windows build; fallback is `transparent=False, background_color="#0a0e14"` and accept an opaque pill.

### 2026-04-30 — Context: Phase 3 ramp (overlay window) — pickup notes
What the existing code already assumes for Phase 3 (do not re-design these from scratch):
- The overlay is intended to be a **second pywebview window** (`webview.create_window(...)`), NOT a tkinter `Toplevel`. Two deferred bridge methods (`pick_overlay_position`, `test_overlay`) are blocked on this — no live `tk.Tk()` root remains after splash closes.
- React side of the overlay already exists in JSX: `OverlayCard` + `OverlayPreview` in `ui/main/module-panels.jsx` (lines ~205–256). They render a tier-aware match card. The Phase-3 task is mainly to spin them out into their own page (`ui/overlay/index.html`) and host that in a separate frameless+topmost+transparent webview window.
- Settings already in `config.json` for the overlay: `popup_position_x`, `popup_position_y`, `popup_duration`, `popup_scale`. Bridge `save_settings` already applies them.
- Detection-push path (`window.evaluate_js("window.onDetection(...)")`) needs to be split: the **main window** still gets the log entry; the **overlay window** gets the same payload to render the match card. Two `evaluate_js` calls per detection, one per window.
- Designer's reference for the overlay is `Project Rockfinder/ref/TestPopup.png` (kept locally, gitignored).
- Window flags to use: `frameless=True, on_top=True, transparent=True, easy_drag=False` and absolute (x, y) from saved settings. Click-through is NOT required (current overlay auto-hides; new one will too).
- Auto-hide: easiest implementation is a Python-side `threading.Timer(duration, hide_overlay)`, calling `window.hide()` after the configured seconds. Re-show on each new detection.

### 2026-04-30 — Completed: Phase 2 of webview UI migration (Settings panel)
- Bridge gained `get_settings`, `save_settings`, `pick_debug_folder`. Schema translation: React `camelCase`/`scale%` ↔ config.json `snake_case`/`float`. Compatibility with tkinter `main.py`'s schema preserved.
- `save_settings` writes through `Config.save()` AND applies `scanner.enable_debug(...)` live so the next OCR scan picks up the change without needing a relaunch.
- React side: `persistSettings` updates state immediately, debounces save by 200 ms; `browseDebugFolder` for native folder pick; `SETTINGS` nav button enabled.
- Removed unwired `sound` toggle (no backend) and the fake "SCREENSHOTS PROCESSED 142" readout. Added `TEST OVERLAY` placeholder button, disabled with Phase 3 tooltip.
- Index.html: cache-busted every script + stylesheet so WebView2 picks up JSX/CSS edits on relaunch.
- Deferred to Phase 3: `pick_overlay_position` and `test_overlay` — both require an `OverlayPopup` instance, but no live tk root remains after the splash closes.
- Version: `5.1.0.dev1` → `5.1.0.dev2`.

### 2026-04-30 — Completed: Phase 1 of webview UI migration
- New branch `feat/webview-migration` from master.
- Decision: option B2 from architecture discussion — both main UI and (later) overlay become webview windows. Babel-standalone (no build step), keep tkinter splash, drop Designer's tweaks panel.
- Designer's "Project Rockfinder" JSX moved to `ui/main/`; tweaks-panel.jsx dropped; `pywebview-drag-region` added to brand-block; window controls (—, ×) added; non-scanner radial nav buttons disabled.
- New: `app_webview.py` (frameless 1020×800 entry), `bridge.py` (`Bridge` js_api class — get_initial_state, pick_screenshot_folder, set_screenshot_folder, start/stop_monitoring, test_detection, minimize/close_window). Detections pushed to JS via `window.evaluate_js("window.onDetection(...)")`.
- Removed `body::before` vignette in styles.css (was overlaying content at z-index 2 → washed-out look).
- pywebview 6.2.1 added to requirements.txt; uses WebView2 on Windows.
- Verified: splash → console handoff, BROWSE picker, ENGAGE/HALT, PING, real screenshot drop into watched folder updates the React log live.
- Known: ground-deposit / salvage matches show "NO LOCK" in the reveal card because JS-side `lookupSignature` uses mock data.jsx; phase 5 wires the real Python DB.

### 2026-04-08 — Completed: v5.0.0 security hardening + quality pass released
- Full red-team + code review + post-review pipeline completed
- Security: URL validation (download_url), reparse point guards (screenshot/debug folders), 50 MB image cap
- Crash fixes: added missing `import os`, `_test_screenshot` now runs OCR on background thread
- Quality: extracted named constants, removed dead code (pricing.py, regolith_api.py, create_card, get_asset_path), overlay colors reference RegolithTheme.COLORS
- Correctness: 4-tuple/3-tuple update check eliminated via `_update_check_error`, .webp/.bmp added to file enumeration
- README rewritten; GitHub release v5.0.0 created (pre-release)
- Open: exe smoke test, in-game verification, promote to full release, GitHub Pages (Phase 9)

### 2026-03-18 — Completed: v4.2.1 released to GitHub
- Exe built (38.9 MB, PyInstaller 6.19), attached to GitHub release tag v4.2.1
- Build script fixed: UTF-8 stdout reconfigure to prevent Windows CP1252 crash
- Regolith.Rocks memorial added to app header
- Green name labels in overlay, redundant "Dominant mineral:" label removed
- Test popup updated to SC 4.7 Torite example

### 2026-03-18 — Completed: v4.2.1 overlay label corrections
- Fixed "100% pure mineral" overlay labels for ship mining (PTU data: dominant mineral 40-80%, not guaranteed pure)
- Fixed ground deposit method labels (removed "(100% single mineral)" annotation)
- Bumped version 4.2.0 → 4.2.1; updated DEVLOG and TODO headers
- Added SignatureValue.md, data/mining_data-4.7.0-ptu.11450623.json, ship_scan_test.md

### 2026-03-18 — Completed: SC 4.7 full upgrade (v3.2.0 → v4.2.0)
- v3.5.0: Fixed ROC/GV ground deposit sig (3000→4000 from Game2.dcb)
- v4.0.0: SC 4.7 per-mineral signature system — old I/C/S/P/M/Q/E type system removed
- v4.1.0: Added salvage debris signatures (1700/1850/2400/3000 for wreck size classes)
- v4.2.0: Removed Regolith API + UEX pricing (SC 4.7 single-mineral makes composition lookup unnecessary)
- Investigated ship CS identification — deferred (3D vector, dynamic, awaiting scanner rework)
