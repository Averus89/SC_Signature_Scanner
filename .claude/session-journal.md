# Session Journal

A living journal that persists across compactions. Captures decisions, progress, and context.

## Current State
- **Focus:** v5.0.0 released as pre-release — awaiting real-world testing before promoting to full release
- **Blocked:** nothing; Phase 9 (GitHub Pages) and fresh-install smoke test remain open

## Log

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
