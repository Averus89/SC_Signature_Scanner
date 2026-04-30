# Session Journal

A living journal that persists across compactions. Captures decisions, progress, and context.

## Current State
- **Focus:** webview UI migration on branch `feat/webview-migration`. Phases 1–4 committed. Phase 5 verified (Torite ×3, Large Wreck Debris ×3 both resolve correctly), in tree, ready to commit.
- **Blocked:** nothing.
- **Pickup for next session:** Phase 6 — packaging cleanup. Drop `main.py`, `theme.py`, `overlay.py`, `region_selector.py` (after confirming nothing else imports it), update PyInstaller `.spec` to point at `app_webview.py` and bundle `ui/main/` + `ui/overlay/`.

## Log

### 2026-04-30 — Completed: Phase 5 verification + display fixes
- Black-screen-on-PING root cause: `RevealCard` line 108 read `m.sig.toLocaleString()` but the new display match shape lacked `sig`. Fixed by adding `sig` (matched-target signature) to `_to_display_match`.
- Defensive `window.MINERALS/GROUND/SALVAGE/ALL_SIGNATURES = []` init in `data.jsx` so synchronous render-time reads can't crash before bootstrap hydrates.
- Display-name reformat: ship_mining `"Torite (Uncommon) ×3"` → `"Torite ×3 (Uncommon)"`. Surfaced as `nameMain`+`nameSubtitle` so the reveal card renders the tier qualifier at 70% font (new `.reveal-name-sub` class). Salvage debris + ground + salvage panels now use `Name ×N` consistently (was `Name (N×)` / `Name (Nx)`); regex `_COUNT_SUFFIX_RE` strips the legacy suffix.
- Verified: Torite ×3 (sig 11700, ship_mining), Large Wreck Debris ×3 (sig 7200, salvage_debris) both resolve correctly with right tier color in reveal card + overlay.

### 2026-04-30 — Completed: Phase 5 of webview UI migration (real signature DB)
- Architecture: B-full — hydrate JS tables from Python on bootstrap AND prefer Python's per-detection matches when present (with JS lookupSignature as fallback). Single source of truth = `SignatureScanner` in Python; React just renders.
- `bridge.py`: new `get_signature_db()` returns `{minerals, ground, salvage}` from `scanner.minable_signatures`, `ground_deposit_*_base`, `salvage_per_panel`, `salvage_debris_types`. New static `_to_display_match(py_match)` translates Python match dicts → React shape `{name, tier, cat, notes}`. `_build_detection_payload` now exposes display-shaped `matches` plus raw `rawMatches`.
- `ui/main/data.jsx`: gutted — hardcoded MINERALS/GROUND/SALVAGE/ALL_SIGNATURES/SAMPLE_STREAM arrays removed. TIERS (presentation metadata) + lookupSignature (fallback) remain. lookupSignature reads `window.ALL_SIGNATURES` at call time.
- `ui/main/app.jsx`: bootstrap fetches `get_signature_db()` and hydrates `window.MINERALS/GROUND/SALVAGE/ALL_SIGNATURES`. `ingestSig` rewritten to prefer `pythonMatches[0]` over `lookupSignature`.
- Version `5.1.0.dev4` → `5.1.0.dev5`. Cache buster `v=21` → `v=22`. DEVLOG updated. NOT yet committed.

### 2026-04-30 — Context: Phase 5 verification checklist (next session)
1. Launch `python app_webview.py`. Codex panel (currently disabled in nav) eventually wakes — but on bootstrap, `window.ALL_SIGNATURES` should be populated from Python. Sanity: open DevTools and check `window.MINERALS.length > 0`.
2. PING a screenshot of a ship-mining target (e.g., a Borase/Bexalite signature ~3570) — should match correctly with `RARE` tier and the right mineral name. Same as before.
3. PING a screenshot of a small ground deposit (signature ~3000 or a multiple like 6000/9000). The reveal card should show "Small Ground Deposit (Nx)" with tier `ground_s` (orange). This was the Phase 1 NO LOCK case.
4. PING a screenshot of salvage debris. Should resolve to the right debris-type name with `SALVAGE` tier.
5. Live monitoring: drop a real screenshot in the watched folder — same checks as PING but pushed via `onDetection`.
6. Overlay window: real-screenshot detections should also pop the overlay card with the correct tier color and name.

Known caveats to watch for:
- If `lookupSignature` ever fires for a signature that should be Python-matched, the fallback's flat-tolerance match might pick up a near-miss ship mineral when the truth is a ground deposit. Won't normally happen because the bridge always sends `matches`. But worth noting.
- Tier `ground_s` / `ground_l` colors are both amber-ish per `data.jsx::TIERS`. Visually similar to ship-mining "common". If hard to tell apart in the reveal card, may want distinct colors later.

### 2026-04-30 — Completed: Phase 4 verification + UX fixes
- User confirmed PICK REGION + tk modal flow works perfectly after two follow-up fixes:
  - **Auto-minimize main console while picker is active** so user can see the screenshot they're drawing on. First attempt minimized BEFORE the file dialog opened, leaving user staring at a tiny dialog on a blank desktop ("feels like the app crashed"). Fixed by minimizing only AFTER the screenshot is picked, when the fullscreen tk window actually opens.
  - **Swapped tk filedialog for pywebview's native `create_file_dialog`** for the screenshot picker, so we don't spawn an implicit tk root on the worker thread. The fullscreen `RegionSelector` still uses tk for its canvas (image scaling math is reused), but we pass the picked path directly via `selector.open(image_path=path)` so its internal filedialog branch never runs.
- `_restore_main_window` helper centralizes the `window.restore()` call. The whole flow is now: file dialog (no minimize) → minimize → tk modal blocks → finally restore.

### 2026-04-30 — Completed: Phase 4 of webview UI migration (region selector)
- Architecture: plan B — reused legacy tk `RegionSelector` rather than reimplementing in React. The tk class accepts `parent=None` and creates its own short-lived `tk.Tk()`, so no persistent root needed. Bridge call runs on pywebview's worker thread and blocks on `selector.open()` until the modal closes; tkinter-on-worker-thread works on Windows for short modal flows. Phase 6 will retire `region_selector.py` together with `main.py`.
- `bridge.py`: added `get_scan_region`, `pick_region` (returns `{ok, region}` or `{ok, cancelled}`), `clear_scan_region`. Module import `import region_selector`.
- `ui/main/module-panels.jsx`: `RegionPanel` rewritten as launcher — `[PICK REGION]` + `[CLEAR]` + `(x1,y1)/(x2,y2)/size/status` readouts. Fake-HUD-with-drag mock removed. `useRef` import dropped.
- `ui/main/app.jsx`: `region` state hydrated from `get_scan_region` on bootstrap; new `pickRegion`/`clearRegion` callbacks; `regionBusy` flag for in-flight picker; `MODULES.region.disabled` flag removed (nav enabled).
- Version `5.1.0.dev3` → `5.1.0.dev4`. Cache buster `v=20` → `v=21`. DEVLOG updated. NOT yet committed.

### 2026-04-30 — Context: Phase 4 verification checklist (next session)
1. Launch `python app_webview.py`. The radial-nav `REGION` button should now be enabled (no "Coming in a later phase" tooltip).
2. Click REGION. Panel renders with `[PICK REGION]` (amber primary) + `[CLEAR]` (greyed if no region saved) + four readouts showing `—`.
3. Click PICK REGION. A native file dialog should appear. Select a Star Citizen screenshot. A fullscreen tk window pops up with the screenshot — drag a rectangle around the signature value.
4. Click `✓ Save Region`. A "Saved" message box confirms; the tk window closes; React panel readouts update with the actual `(x1, y1) / (x2, y2)` and size.
5. Click CLEAR. Readouts reset to `—`; `scan_region.json` deleted from `paths.get_user_data_path()`.
6. Restart the app — if a region was saved before quit, the panel should re-hydrate with it on bootstrap.
7. While monitoring, drop a real screenshot in the watched folder — `scanner.py` should crop OCR to the picked region.

Known caveats to watch for:
- **Tkinter on worker thread** — pywebview dispatches JS bridge calls to a worker. `tk.Tk()` created on a non-main thread is technically unsupported but typically works on Windows. If it crashes, the fallback is wrapping the picker call in a `subprocess` (separate Python process — clean separation of GUI loops).
- **Modal blocks the bridge worker** — while the tk picker is open, no other JS API call can complete. Acceptable for a modal flow but worth knowing.

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
