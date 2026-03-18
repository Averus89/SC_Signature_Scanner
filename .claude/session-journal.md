# Session Journal

A living journal that persists across compactions. Captures decisions, progress, and context.

## Current State
- **Focus:** v4.2.1 released — awaiting user feedback
- **Blocked:** nothing

## Log

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
