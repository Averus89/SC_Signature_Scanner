# Session Journal

A living journal that persists across compactions. Captures decisions, progress, and context.

## Current State
- **Focus:** webview UI migration on branch `feat/webview-migration`. Phase 1 done; tkinter `main.py` still parallel until full migration completes.
- **Blocked:** nothing; Phase 1 verified, awaiting decision to commit and start Phase 2 (Settings panel).

## Log

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
