# SC Signature Scanner - Development Log

**Project:** SC Signature Scanner  
**Location:** `C:\Users\larse\PycharmProjects\AREA52\SC_Signature_Scanner\`  
**Developer:** Mallachi  
**Current Version:** v5.0.0
**Development Period:** January 8, 2026 - ongoing

---

## Project Overview

The SC Signature Scanner is a real-time target identification tool for Star Citizen. It monitors screenshots and uses OCR to detect signature values from the in-game HUD, then matches them against a database to identify asteroids, deposits, and salvage targets.

---

## Development Rules

### 1. Devlog as Source of Truth

The development log shall serve as the authoritative project state document. It must be complete enough that any AI can read it and immediately understand: (a) current project status, (b) what has been implemented, (c) what remains to be done, (d) why key decisions were made.

### 2. Session Start Protocol

At the start of each development session, Claude shall review previous chat history to identify and document any unlogged events, decisions, or changes before proceeding with new work.

### 3. Session End Protocol

At session end, if substantial work was completed, the devlog shall be updated with: work completed, problems encountered and solutions, any new decisions or deferrals, and updated status of pending items.

### 4. Decision Documentation

Technical decisions shall be recorded with rationale. "We chose X" is insufficient - "We chose X because Y, and rejected Z because W" enables future AI to understand context and avoid revisiting settled questions.

### 5. Current State Clarity

The devlog shall always contain a clear "Current Status" or "Next Steps" section so any AI knows exactly where to resume work.

---

### Core Features
- Screenshot folder monitoring with automatic signature detection
- OCR-based signature value extraction from game HUD
- Database matching for asteroids, surface deposits, ground deposits, salvage, and wreck debris
- Tobii Eye Tracker 5 integration (optional, deferred)
- Manual scan region configuration (fallback)

---

## Changelog

### 2026-04-30 — v5.1.0.dev2: Webview UI migration · Phase 2 (Settings panel)

Branch `feat/webview-migration`. The Settings panel is now wired end-to-end through the bridge to the existing `config.json`. The `SETTINGS` radial nav button is enabled.

**Schema translation in the bridge:**
React UI uses camelCase + integer percent scale; `config.json` uses snake_case + float scale (kept compatible with the running tkinter `main.py`). Mapping applied in both directions in `bridge.py`:

| `config.json` (snake_case) | React state (camelCase) |
|---|---|
| `popup_position_x` | `popupX` |
| `popup_position_y` | `popupY` |
| `popup_duration` | `duration` |
| `popup_scale` (float, e.g. `1.3`) | `scale` (int %, e.g. `130`) |
| `debug_mode` | `debug` |
| `debug_folder` | `debugFolder` |

**Files modified:**
- `bridge.py` — added `get_settings`, `save_settings`, `pick_debug_folder`. `save_settings` writes through `Config.save()` and applies `scanner.enable_debug(...)` so the next OCR scan picks up changes immediately.
- `ui/main/app.jsx` — bootstrap now fetches `get_settings` alongside `get_initial_state`; new `persistSettings` callback updates state immediately and debounces a `save_settings` call by 200 ms; new `browseDebugFolder` callback; `SETTINGS` enabled in `MODULES`.
- `ui/main/module-panels.jsx` — `SettingsPanel` props extended with `browseDebugFolder` + `bridgeReady`; debug folder is now an editable input with a BROWSE button (mirrors the scanner panel pattern); the unwired `sound` toggle removed; the fake "SCREENSHOTS PROCESSED 142" readout removed; the `TEST OVERLAY` button placeholder added but disabled with a Phase-3 tooltip.
- `ui/main/index.html` — cache busters bumped on every `script src` and the stylesheet (`v=17` → `v=18`) so WebView2 always picks up new JSX/CSS on relaunch.
- `version_checker.py` — `5.1.0.dev1` → `5.1.0.dev2`.

**Deferred from Phase 2 (need overlay window or live tk root):**
- "Test overlay" button — requires an `OverlayPopup` instance, but no `tk.Tk()` root is alive once the splash closes. Wires up in Phase 3.
- "Pick position" via in-game draggable adjuster — same constraint. The in-UI drag-on-thumbnail still works for entering popup X/Y by hand.

**Verified manually:**
SETTINGS panel renders with values from existing `config.json`; dragging the screen-thumbnail updates X/Y; sliders update duration/scale; toggling debug flips `debug_mode` in `config.json` and applies live to the scanner; BROWSE picks a debug folder via native dialog; CENTER button resets to 1920/1080; TEST OVERLAY is correctly disabled with a Phase-3 tooltip.

---

### 2026-04-30 — v5.1.0.dev1: Webview UI migration · Phase 1 (scaffold + scanner)

Branch `feat/webview-migration`. Migration from tkinter to a React desktop UI hosted in pywebview, executed in six vertical-slice phases. Phase 1 establishes the scaffold and ports the scanner panel only; tkinter `main.py` remains runnable in parallel.

**Architecture decision — option B2 (full webview):**
Reviewed three options before starting: (A) restyle tkinter as a design reference only, (B1) hybrid main-window-webview + keep-tkinter-overlay, (B2) full webview for main + overlay + region selector, (C) PyQt rewrite. Selected B2 because it lets Designer's full sci-fi console aesthetic land 1:1 from the JSX prototype. Trade-offs accepted: Microsoft Edge WebView2 becomes a runtime requirement (preinstalled on Win10/11); pywebview adds ~600 KB to the venv; some webview Windows quirks (transparency, click-through) deferred until phases 3–4.

**Bundling — babel-standalone in the browser:**
No Node toolchain, no build step. Future Designer JSX iterations drop in cleanly. ~1–2 s startup compile cost is masked by the existing tkinter splash. If types/source-maps/npm packages become important later, a Vite migration is mechanical.

**Files added:**
- `app_webview.py` — frameless 1020×800 entry. Tkinter splash → loads OCR/scanner/monitor → opens pywebview window pointing at `ui/main/index.html`.
- `bridge.py` — `Bridge` class exposed via pywebview `js_api`. Public surface: `get_initial_state`, `pick_screenshot_folder`, `set_screenshot_folder`, `start_monitoring`, `stop_monitoring`, `test_detection`, `minimize_window`, `maximize_window`, `close_window`. Private setup `_attach_window()`. Detection events pushed to JS via `window.evaluate_js("window.onDetection(...)")`.
- `ui/main/` — Designer's React 18 + babel-standalone JSX moved out of `Project Rockfinder/`. The latter retains only the design-archive screenshots in `ref/` and `_check/`.

**Files modified:**
- `requirements.txt` — added `pywebview>=6.2.0`.
- `version_checker.py` — `CURRENT_VERSION` bumped `5.0.0` → `5.1.0.dev1`.
- `ui/main/app.jsx` — TWEAK_DEFAULTS / `useTweaks` / `TweaksUI` removed; non-scanner radial nav buttons (`INDEX`, `HUD`, `REGION`, `SETTINGS`) gated with `disabled: true` and a "Coming in a later phase" tooltip; bridge-ready hook + bootstrap state from `get_initial_state`; `window.onDetection` receives Python pushes; folder browse + monitoring + ping all routed through `pywebview.api.*`; `WindowControls` component (—, ×) calling `bridge.minimize_window` / `bridge.close_window`; `pywebview-drag-region` class on `brand-block`.
- `ui/main/scanner-panel.jsx` — props renamed to `toggleMonitoring`, `browseFolder`, `bridgeReady`; buttons gain `disabled={!bridgeReady}` until JS bridge is up.
- `ui/main/styles.css` — removed `body::before` vignette overlay (z-index 2 over content was washing the UI to <100% opacity); added `.pywebview-drag-region` (cursor grab/grabbing), `.win-controls`, `.win-btn` / `.win-btn.close`, and `.rn-item.disabled` styling.
- `ui/main/index.html` — dropped `tweaks-panel.jsx` script tag; cache buster `v=16` → `v=17`.

**Files dropped:** `tweaks-panel.jsx` (Designer-only debug controls).

**Verified manually:**
Splash → console handoff; brand-area drag works; min/× window controls work; BROWSE opens native folder picker and persists to `config.json`; ENGAGE without folder yields error popup; with valid folder switches to MONITORING; dropping a real Star Citizen screenshot into the watched folder produces a live detection log entry; PING opens file dialog and runs OCR against the chosen screenshot; HALT returns to STANDBY; window resizes cleanly down to the `min_size=(960, 700)` floor.

**Known limitations of phase 1:**
- Match names/tiers in the React UI come from the JS-side mock `data.jsx`, not the real Python signature DB. Ship-mining minerals match correctly because their signatures align; ground deposits (count × base_signature) and salvage debris show "NO LOCK" in the reveal card even when Python correctly identified them. Phase 5 wires the real DB into JS.
- `INDEX`, `HUD`, `REGION`, `SETTINGS` panels exist in the JSX but are gated off the radial nav.
- No live OCR confidence / debug folder display in the React UI yet.

**Remaining migration phases:** 2 — Settings panel · 3 — Overlay window · 4 — Region selector · 5 — Index/codex panel · 6 — Packaging (remove tkinter `main.py`, update `.spec`).

---

### 2026-04-08 — v5.0.0: Security hardening and quality pass

Full red-team + code review + post-review pipeline. All findings addressed.

**Security fixes (red team F-001 → F-005):**
- `version_checker.py`: Added `_validate_release_url()` — rejects any `html_url` from GitHub API that isn't `https?://…github.com`. Narrows `except Exception` to `urllib.error.URLError`, `TimeoutError`, `json.JSONDecodeError`, `KeyError`, `ValueError`
- `theme.py:UpdateBanner._open_download`: Added URL validation before `webbrowser.open()` (defence-in-depth)
- `main.py:exit_and_download`: Added URL validation before `webbrowser.open()` (defence-in-depth)
- `main.py:_start_monitoring`: Rejects screenshot folders that are symlinks or Windows directory junctions (`FILE_ATTRIBUTE_REPARSE_POINT`)
- `main.py:_browse_debug_folder`: Same reparse point guard for debug output folder
- `scanner.py:_load_image`: Added 50 MB file size cap and `img.load()` (forces eager read, closes OS file handle)
- `requirements.txt`: Removed unused `requests>=2.31.0` — dead code from removed `regolith_api.py`

**Crash fixes (code review B-001, B-002):**
- `main.py`: Added missing `import os` — `os.startfile()` in `_open_debug_folder` was raising `NameError` on every click
- `main.py:_test_screenshot`: Wrapped `_on_new_screenshot` call in `threading.Thread` — OCR scan was blocking the main thread and freezing the GUI for several seconds

**Correctness fixes:**
- `main.py:_check_for_updates`: Split error into separate `_update_check_error` attribute — eliminates fragile 4-tuple/3-tuple length sniffing at `_poll_update_result`
- `main.py:_start_monitoring`: Existing-file enumeration now includes `.webp` and `.bmp` to match `ScreenshotHandler.VALID_EXTENSIONS`

**Quality cleanup:**
- `scanner.py`: Extracted `MIN_SIGNATURE`, `MAX_SIGNATURE`, `MIN_OCR_DIMENSION`, `MIN_COMPONENT_AREA`, `MAX_CLUSTER_COUNT`, `MAX_IMAGE_FILE_SIZE` as module-level constants; replaced all inline literals
- `scanner.py`: Removed dead `HAS_CV2` try/except guard — `cv2` is a hard dependency already in `requirements.txt`; the guard masked `ImportError` as silent degradation
- `monitor.py`: Extracted `_FILE_WRITE_TIMEOUT` and `_FILE_POLL_INTERVAL` constants
- `overlay.py`: Both `OverlayPopup` and `PositionAdjuster` color class attributes now derive from `RegolithTheme.COLORS` — palette changes propagate automatically
- `theme.py`: Removed dead `create_card()` classmethod (never called)
- `paths.py`: Removed dead `get_asset_path()` function (never called, referenced non-existent `assets/` directory)
- Deleted `pricing.py` and `regolith_api.py` — confirmed no active imports anywhere

---

### 2026-03-18 — v4.2.1 patch: UI polish + build fix (post-release)

**Changes after initial v4.2.1 release:**
- `overlay.py`: Target name in popup header now always green (`#3fb950`)
- `overlay.py`: Removed redundant "Dominant mineral:" label (name already shown in header)
- `main.py`: Test popup updated to SC 4.7 example — Torite (Uncommon) sig 3900
- `main.py`: Added memorial label in header: "✦ In memory of Regolith.Rocks — The Industrial Community"
- `build.py`: Fixed `UnicodeEncodeError` crash on Windows CP1252 console — added `sys.stdout.reconfigure(encoding='utf-8')` at startup
- `build.py`: Removed stale Regolith API references from runtime file summary

**Released:** v4.2.1 pushed to GitHub, exe attached to release.

---

### 2026-03-18 — v4.2.1: Overlay label corrections (PTU data reconciliation)

In-game testing revealed the overlay was displaying "100% pure mineral: Torite" for ship mining matches. PTU composition data (`mining_data-4.7.0-ptu.11450623.json`) confirmed rocks have a dominant mineral (40–80%) plus secondary minerals (5–20%) — they are NOT guaranteed 100% pure.

**Changes made to `overlay.py`:**
- Ship mining confirmed mineral label: `"100% pure mineral:"` → `"Dominant mineral:"`
- Ground deposit small method label: `"💎 Hand Mining (100% single mineral)"` → `"💎 Hand Mining"`
- Ground deposit large method label: `"🚗 ROC Mining (100% single mineral)"` → `"🚗 ROC Mining"`
- Ground deposit unknown mineral list label: `"100% purity - one of:"` → `"Possible mineral:"`

**Also added in this session:**
- `SignatureValue.md`: Full rewrite for SC 4.7. Per-mineral signature system documented with secondary mineral columns from PTU data. Old I/C/S/P/M/Q/E content removed.
- `data/mining_data-4.7.0-ptu.11450623.json`: PTU composition source file added to data folder.
- `combat_analyst_db.json`: `composition` and `_description` fields updated to reflect dominant mineral language.
- `TODO.md`: Added Windows OCR (WinRT) investigation item; added deferred ship ID feature entry.
- `ship_scan_test.md`: Data collection template for empirical ship CS scanning (deferred pending SC scanner rework).

**Note:** Ground deposits are still 100% single-mineral per cluster — the cluster rules are accurate. The correction applies only to ship-mining rocks which have mixed composition.

---

### 2026-03-18 — v4.2.0: Removed pricing/API system

SC 4.7 deposits are 100% single-mineral per cluster (no mixed composition), making value estimation from composition data unnecessary. The Regolith.rocks API and UEX pricing integrations were removed entirely.

**Removed from main.py:**
- `row3` UI block: REFINERY METHOD dropdown + DATA SOURCES status panel
- 12 methods: `_init_pricing`, `_on_method_changed`, `_get_current_yield`, `_refresh_pricing`, `_change_api_key`, `_refresh_all_data`, `_update_api_status`, `_update_pricing_status`, `_validate_api_key_startup`, `_validate_key_with_retry`, `_check_regolith_cache`, `_show_api_key_dialog`
- Startup API key validation gate
- Config load/save: `refinery_method` field
- `import time` (only used in retry method)

**Removed from scanner.py** (done in prior session): `import pricing`, `_get_rock_value_and_composition`, `est_value`/`composition` fields from matches.

**Removed from overlay.py** (done in prior session): `est_value` display, composition table, `est_price_per_scu`.

**Note:** `pricing.py` and `regolith_api.py` kept on disk but no longer imported anywhere.

---

### 2026-03-18 — v4.1.0: SC 4.7 salvage debris signatures

SC 4.7 added new salvage gameplay with sized wreck debris entities that have distinct signatures.

**New salvage signatures extracted from Game2.xml:**
- 1700 = Small Wreck Debris (Avenger-class hull pieces + scrap cargo containers)
- 1850 = Medium Wreck Debris (Ares Inferno-class hull pieces)
- 2000 = Salvage Panels / FPS Active Scrap (unchanged)
- 2400 = Large Wreck Debris (C2 Hercules-class hull pieces)
- 3000 = Capital Wreck Debris (890 Jump-class hull pieces) — **COLLISION** with FPS ground deposit small

**New collision noted:** 3000 now collides between FPS small ground deposits and 890 Jump capital wreck debris. Both matches will be shown when 3000 is scanned. Context-dependent (space = likely debris, planet = likely ground deposit).

**Changes made:**
- `combat_analyst_db.json`: Updated `salvage` section to new structure (panels + debris dict). Added 1700, 1850, 2400 to `signature_lookup`. Updated 3000 entry with collision note.
- `scanner.py:_build_lookups`: Loads `salvage.panels._base_signature` and all `salvage.debris` entries into `salvage_debris_types` list. All debris sigs added to `known_base_signatures` for OCR correction.
- `scanner.py:match_signature`: Added debris check loop after panels check. Produces `salvage_debris` type matches.
- `overlay.py`: Added `salvage_debris` handling — screwdriver icon, "Wreck Debris — Tractor Beam / Collect" method label.
- `main.py`: About tab updated with full salvage signature table.
- `version_checker.py`: Bumped to v4.1.0.
- `clean.py` / `build.py`: Updated shebangs to `python`, added Python 3.13 guard in build, tool cache cleanup, `nul` artifact cleanup.
- `.gitignore`: Rewritten UTF-8, added tool caches, `nul`, data cache files.

**Also investigated (no changes):** Ship cross-section signatures — confirmed standardised per model (3D vector, not a single HUD value, dynamic — not suitable for static lookup).

---

### 2026-03-18 — v4.0.0: SC 4.7 per-mineral signature system (breaking change)

**The SC 4.7 mining system is completely different from 4.6.**

The old I/C/S/P/M/Q/E asteroid type system is REMOVED in SC 4.7. The new system uses per-mineral signatures: each mineral has a unique signature value that directly identifies it, whether it appears in an asteroid or a surface rock.

**New signature architecture (SC 4.7):**
- Legendary tier (3170-3200): Quantainium, Stileron, Savrilium
- Epic tier (3370-3400): Ouratite, Riccite, Lindinium
- Rare tier (3540-3600): Beryl, Taranite, Borase, Gold, Bexalite
- Uncommon tier (3825-3900): Laranite, Aslarite, Titanium, Tungsten, Agricium, Torite
- Common tier (4180-4300): Hephaestanite, Tin, Quartz, Corundum, Copper, Silicon, Iron, Aluminum, Ice
- Ground FPS (3000) and GV/ROC (4000) unchanged
- Salvage (2000) unchanged

**Changes made:**
- `combat_analyst_db.json`: Complete restructure. Removed `space_deposits`, `surface_deposits`, `rare_asteroids`. New `ship_mining` section with tiered mineral entries.
- `scanner.py:_build_lookups`: Now reads tiered mineral structure. Each sig maps directly to a known mineral.
- `scanner.py:match_signature`: Ship-mining matches now include `mineral`, `tier`, and per-SCU price. No Regolith composition lookup needed (rock is 100% single mineral).
- `overlay.py`: New `ship_mining` category handling with tier-based colour coding (red=legendary/epic, purple=rare, orange=uncommon, grey=common). Confirmed mineral shown definitively, not as a "possible list".
- `main.py`: About tab updated to show new tier ranges.
- Version: 3.5.0 → 4.0.0

**Version 4.0.0 rationale:** Major breaking change — all old type-based signatures (4700-4900) are invalid in SC 4.7.

---

### 2026-03-18 — v3.5.0: SC 4.7 signature database update + C-1 fix

**Source:** `Game2.xml` extracted via unp4k-suite v3.13.66 from SC 4.7 Data.p4k

**C-1 resolved:** Ground deposit large (ROC/GV) base signature was **incorrectly 3000** in the DB. Confirmed via 4.7 DCB as **4000**. Updated `combat_analyst_db.json` and `scanner.py` fallback defaults.

**All existing values confirmed unchanged in SC 4.7:**
- Space: I=4000, C=4700, S=4720, P=4750, M=4850, Q=4870, E=4900
- Surface deposits: 4000 (all types)
- FPS small ground: 3000
- Salvage panels: 2000

**NEW — Rare asteroid mineral variants (not in previous DB):**
- Beryl: 3540, Taranite: 3555, Borase: 3570, Gold: 3585, Bexalite: 3600
- These have unique sub-4000 signatures distinguishable from standard types

**NEW — Undetectable items confirmed:**
- Vlk Pearls, Vlk Irradiated Pearls, Flowstone = signature 0

**NEW — Ground deposit minerals:**
- Added Sadaryx, Janalite, Saldynium, Carinite to minerals list (found in DCB, not in previous survey)

**L-1 fixed:** About tab now shows `Small (3000)` and `Large (4000)` instead of stale `120`/`620` values.

**Version bumped:** 3.4.0 → 3.5.0

**Files changed:** `data/combat_analyst_db.json`, `scanner.py`, `main.py`, `version_checker.py`, `TODO.md`

---

### 2026-03-18 — Fix: code review findings H-1 through M-8

Batch fix for all findings from code_review.md that are independent of the C-1 signature value verification.

**H-1 — Bare `except:` blocks → `except tk.TclError:`**
- `overlay.py`: 5 occurrences in `show()`, `_hide()`, `destroy()` teardown paths
- `splash.py`: 2 occurrences in `pump()` and `close()`

**H-3 — `os.system` shell injection → `subprocess.run`**
- `main.py:_open_debug_folder`: macOS and Linux paths now use list-form subprocess, bypassing shell

**H-4 — Triple Regolith API call reduced to one**
- `regolith_api.py:fetch_all_data`: single `fetch_survey_data` call, loop over response keys
- Error now stored in `result["_rock_composition_error"]` instead of silently discarded

**H-5 — `time.sleep(3)` on main thread → event-loop pump**
- `main.py:_validate_key_with_retry`: replaced with a 3-second deadline loop calling `root.update()` every 50ms — UI stays responsive during retry wait

**L-6 — `os._exit(0)` → `sys.exit(0)`**
- `main.py:exit_and_download`: replaced `os._exit` (bypasses cleanup) with `root.quit()` + `sys.exit(0)`

**M-3 — `OverlayPopup` second `tk.Tk()` eliminated**
- `overlay.py`: constructor now accepts `root: tk.Tk`; no longer creates its own hidden root
- `main.py`: all three call sites updated to pass `root=self.root`
- `destroy()` no longer calls `self._root.destroy()` (does not own the root)

**M-2 — `Config.get()` repeated file reads → in-memory cache**
- `config.py`: added `self._cache`; `load()` returns cached copy on repeat calls; `save()` updates cache

**M-5 — Config and region paths now use `paths.get_user_data_path()`**
- `config.py`: default config path now `paths.get_user_data_path() / "config.json"`
- `region_selector.py`: `CONFIG_FILE` now `paths.get_user_data_path() / "scan_region.json"`
- Both configs now persist correctly in PyInstaller frozen builds

**M-4 — `PricingManager` data dir default fixed**
- `pricing.py`: default `data_dir` now `paths.get_user_data_path() / "data"`; UEX cache persists across frozen exe restarts

**M-6 — Singleton race condition in `regolith_api.get_api()`**
- `regolith_api.py`: added `threading.Lock()` guarding `_instance` creation

**M-7 — O(n) list dedup in `_extract_signatures` → O(1) set**
- `scanner.py`: replaced `raw_values` list membership check with a `seen: set[int]`

**M-8 — Type annotation corrections**
- `scanner.py`: `Optional[callable]` → `Optional[Callable[[], None]]` for download callbacks
- `scanner.py`: `output_dir: Path = None` → `output_dir: Optional[Path] = None`

**L-4 — Hot-path `import cv2` inside methods → module-level**
- `scanner.py`: `cv2` now imported at module level with `HAS_CV2` flag; inline imports removed

**CURRENT_EPOCH updated**
- `regolith_api.py`: `"4.4"` → `"4.6"` to match app version and database

**Files changed:** `main.py`, `overlay.py`, `splash.py`, `regolith_api.py`, `config.py`, `region_selector.py`, `pricing.py`, `scanner.py`

---

### 2026-03-18 — Fix: thread-safe UI updates in `_on_new_screenshot` (C-2)

**Problem:** `_on_new_screenshot` is called by the watchdog file monitor on a background thread.
Multiple calls to `self._log()` (modifying a `tk.Text` widget) and `self.stats_label.configure()`
were made directly from that thread. Tkinter is not thread-safe on Windows; these off-thread widget
calls cause intermittent UI corruption and crashes during active screenshot scanning.

**Fix:** Refactored `_on_new_screenshot` so the OCR scan (`scanner.scan_image`) continues running
on the background thread (it is the expensive work and must not block the main loop), but all
collected log lines, the stats counter increment, and any overlay display are dispatched to the
main thread in a single `self.root.after(0, _ui_update)` call. The overlay display was already
correctly deferred — this fix makes the log and stats consistent with that pattern.

**Files:** `main.py:1285–1340`

---

## Development Timeline

### Phase 1: Project Inception (January 8, 2026)

**Initial Concept:**
The project originated from an idea to enhance Wingman AI (a Star Citizen AI assistant) with Tobii Eye Tracker integration. The concept was to allow players to look at something in-game and ask "What is that?" with the AI analyzing the focused area.

**Key Decisions:**
- Standalone tool rather than Wingman AI skill (simpler distribution)
- Screenshot-based capture (using SC's native screenshot function)
- Folder monitoring approach (watchdog library)
- Overlay popup for results display

**Project Structure Created:**
```
SC_Signature_Scanner/
├── main.py           # Main application with tkinter UI
├── scanner.py        # OCR and signature matching
├── overlay.py        # Popup overlay display
├── monitor.py        # Screenshot folder watcher
├── config.py         # Configuration management
├── clean.py          # Cache cleanup utility
├── requirements.txt  # Python dependencies
└── data/
    └── combat_analyst_db.json  # Signature database
```

---

### Phase 2: Database Extraction (January 8-9, 2026)

**Data.p4k Mining:**
Used `scdatatools` and `unp4k` to extract signature data directly from Star Citizen's game files. This provided:
- Ship cross-section dimensions (CS values)
- Asteroid type signatures
- Deposit signatures
- Mining rock compositions

**Key Discovery - Signature Formula:**
```
Total Signature = Count × Base Signature
```
Example: Signature 3400 = 2× C-type asteroids (base 1700 each)

**Database Version 4.0 Created:**
| Category | Types | Signature Range |
|----------|-------|-----------------|
| Space Deposits (Asteroids) | I, C, S, P, M, Q, E | 1660-1900 |
| Surface Deposits | Shale, Felsic, Obsidian, Atacamite, Quartzite, Gneiss, Granite, Igneous | 1730-1950 |
| Ground Deposits (Small) | FPS/Hand mining | 120 base |
| Ground Deposits (Large) | ROC/Vehicle mining | 620 base |
| Salvage | Per panel | 2000 base |

---

### Phase 3: Detection Algorithm Evolution (January 9-10, 2026)

**Attempt 1: Naive OCR**
- Simple text search for "SIG:" label
- Failed: Label not always present, position varies

**Attempt 2: Gradient Bar Detection**
- Find two vertical gradient bars (always present when scanning)
- Calculate bar angle → rotate image to vertical
- Signature position = midpoint between bar tops
- Problem: Angle calculation returned -178.8° (picking up wrong elements)

**Attempt 3: Icon Triangle Detection**
- Find cone icon (left) and signal icon (right)
- Calculate equilateral triangle
- OCR at apex
- Problem: Too many similar-colored elements causing false matches

**Attempt 4: HUD Circle Detection**
- Find the targeting reticle using color saturation + Hough circles
- Calculate signature position relative to circle center
- Problem: Complex, unreliable across different HUD palettes

**Final Solution: Fixed Region + Manual Calibration**
- User defines scan region once via GUI tool
- OCR that fixed region on every screenshot
- Simple, reliable, works across all HUD styles

---

### Phase 4: Pricing Integration (January 9, 2026)

**UEX Corp API Integration:**
- Fetches live ore prices from `api.uexcorp.uk`
- 30-minute cache TTL
- Calculates estimated rock values using:
  - Rock composition data (from Regolith.rocks)
  - Current ore prices (from UEX)
  - Refinery yield setting (user configurable)

**Value Calculation Formula:**
```
mineral_mass = deposit_mass × mineral_percentage
mineral_volume = mineral_mass / density
value = mineral_volume × price × refinery_yield
```

**Mineral Composition Display:**
Each rock type now shows probable mineral spawns with:
- Spawn probability (%)
- Median percentage when present
- Individual mineral value
- Price per SCU

---

### Phase 5: Tobii Integration (January 10-11, 2026)

**Research Phase:**
- Tobii Eye Tracker 5 (consumer) has no official SDK
- Tobii 5L (commercial) requires €1495/year license
- Solution: PyEyetracker project (Apache-2.0 license)

**Implementation:**
- GazeServer.exe provides WebSocket interface on localhost:8765
- Returns gaze coordinates in normalized (0-1) format
- SC Signature Scanner connects and converts to pixel coordinates

**Tobii Tab Features:**
- Connection status indicator
- Download button for GazeServer.exe
- Test connection functionality
- Automatic fallback to fixed region if Tobii unavailable

**Decision (January 12):**
Tobii support removed from v1.1.0 release - too complex for initial tester distribution. Fixed region approach is sufficient. Tobii can be re-added later.

---

### Phase 6: UI Development (January 10-11, 2026)

**Theme: Regolith.rocks Inspired**
- Dark background (#1a1a2e)
- Orange accent (#f4a259)
- Cyan success (#4ecca3)
- Professional mining tool aesthetic

**Main Window Tabs:**
1. **Scanner** - Start/stop monitoring, activity log, results display
2. **Settings** - Screenshot folder, overlay options, debug mode, pricing
3. **Tobii Tracker** - Connection status, region configuration
4. **About** - Version info, credits

**Region Selector Tool:**
- Opens fullscreen with screenshot
- Click and drag to define scan region
- Escape to cancel
- Save/Clear/Cancel buttons

---

### Phase 7: Regolith.rocks API Integration (January 11-12, 2026)

**Partnership:**
Collaboration with Regolith.rocks team for:
- Rock composition survey data
- Mining location bonuses
- Authoritative mineral spawn rates

**API Features:**
- API key authentication (required)
- Profile validation on startup
- Rock composition queries per system
- Local cache with manual refresh

**Startup Flow:**
1. Check for saved API key
2. Validate against Regolith.rocks
3. If invalid → prompt for new key
4. If user cancels → exit app
5. Cache composition data locally

---

### Phase 8: OCR Improvements (January 12, 2026)

**Problem Identified:**
Original OCR pipeline was over-processing images:
1. Grayscale conversion (lost orange color info)
2. Fixed threshold at 80 (caught background noise)
3. Binary output (destroyed anti-aliasing)
4. 4x upscale on binary (blocky artifacts)

Result: "1,850" read as "1950"

**Solution: Hybrid OCR Mode**

**Mode 1: Raw (Minimal Processing)**
- Just grayscale conversion
- Preserves anti-aliasing
- Better for clean HUD text

**Mode 2: Adaptive (OpenCV)**
- Adaptive thresholding with Gaussian method
- Handles uneven backgrounds
- Better for cluttered scenes

**Mode 3: Hybrid (Default)**
- Try raw first
- If no signatures found, try adaptive
- Best of both worlds

**Implementation:**
```python
self.ocr_mode = 'hybrid'  # Options: 'raw', 'adaptive', 'hybrid'
```

---

### Phase 9: Build & Distribution (January 11-12, 2026)

**PyInstaller Configuration:**
- Single-folder distribution
- Bundled database and assets
- Hidden imports handled (cv2, scipy, etc.)

**Build Output:**
```
dist/SC_Signature_Scanner/
├── SC_Signature_Scanner.exe
├── data/
│   └── combat_analyst_db.json
└── [runtime dependencies]
```

**Runtime Files (created on first use):**
- `config.json` - User settings + API key
- `scan_region.json` - Defined scan region
- `SignatureScannerBugreport/` - Debug output folder

**Tester Distribution:**
- Debug mode with timestamp-prefixed files
- Configurable debug output folder
- Clean.py utility for resetting state

---

### Phase 10: OCR Engine Migration (January 14, 2026)

**Problem with Tesseract:**
The pytesseract/Tesseract OCR dependency was causing distribution headaches:
- External binary required (tesseract.exe)
- PATH configuration issues on user machines
- Inconsistent versions across installations
- Complex PyInstaller bundling
- Users reporting "tesseract not found" errors

**Solution: EasyOCR**
Migrated to EasyOCR, a deep learning-based OCR engine:
- Pure Python package (pip install)
- No external binaries
- Models download automatically on first use (~115MB)
- Runs entirely offline after initial download
- Better accuracy on styled game text

**Implementation Details:**

| Component | Change |
|-----------|--------|
| `scanner.py` | Complete rewrite of OCR pipeline |
| `requirements.txt` | Added easyocr, torch, torchvision; removed pytesseract |
| `SC_Signature_Scanner.spec` | Added EasyOCR hidden imports + data files |

**Key Design Decisions:**

1. **Lazy Initialization**: OCR reader created on first scan, not at startup
   - Faster app launch
   - Model download happens when actually needed
   - UI can show progress during download

2. **CPU-Only Mode**: `gpu=False` by default
   - Works on all machines
   - Avoids CUDA dependency complexity
   - GPU auto-detected if available

3. **Digit Allowlist**: `allowlist='0123456789,.'`
   - Maximum accuracy for signature values
   - Prevents letter/digit confusion (O vs 0, l vs 1)

4. **Simplified Preprocessing**: 
   - EasyOCR handles most preprocessing internally
   - Only upscale small regions for better detection
   - Removed complex threshold/binary conversion pipeline

**Model Download Flow:**
```
First OCR use:
1. Check ~/.EasyOCR/model/ for cached models
2. If missing, download from EasyOCR servers (~115MB)
3. Load models into memory
4. All subsequent runs use local cache
```

**Files Modified:**
- `scanner.py` - New EasyOCR-based implementation
- `requirements.txt` - Updated dependencies
- `SC_Signature_Scanner.spec` - PyInstaller config for EasyOCR

**Removed:**
- Hybrid OCR mode (raw/adaptive) - no longer needed
- Complex image preprocessing pipeline
- Tesseract binary dependency

---

## Version History

### v3.4.0 (February 6, 2026)
*Remove ship signatures, consolidate signature data to single source of truth*

- **REMOVE:** Ship radar cross-section data (252 ships) from `combat_analyst_db.json` — unused dead data
- **REMOVE:** `ship_lookup` builder from `scanner.py` — was building a lookup table that nothing consumed
- **REFACTOR:** Consolidated signature values to single source of truth (`combat_analyst_db.json`)
- Removed hardcoded module-level constants: `KNOWN_BASE_SIGNATURES`, `ROCK_DISPLAY_NAMES`, `SIGNATURE_TO_ROCK_TYPE`
- All three are now derived from the JSON database in `_build_lookups()`
- Salvage `signature_per_panel` now read from JSON instead of hardcoded `2000`
- **CLEANUP:** Removed empty `_on_release()` method and unused event binding in `region_selector.py`
- **CLEANUP:** Moved `import time` from local scope to module level in `splash.py`
- **CLEANUP:** Initialized `_test_overlay` in `__init__` in `main.py`, removed `hasattr` guard
- **RATIONALE:** Single source of truth means updating signature values only requires editing the JSON file — no code changes needed

### v3.3.0 (February 6, 2026)
*Signature value update for SC 4.5 + dead code cleanup*

- **UPDATE:** All asteroid signature values updated (I-type 4000, C-type 4700, S-type 4720, P-type 4750, M-type 4850, Q-type 4870, E-type 4900)
- **UPDATE:** All surface deposit signatures now 4000 (CIG bug — collides with I-type Asteroid)
- **UPDATE:** Ground deposit signatures changed from 120/620 to 3000 for both variants (CIG bug)
- **REMOVE:** Surface deposit entries from SIGNATURE_TO_ROCK_TYPE — cannot map individually when all share 4000
- **CLEANUP:** Removed dead code: `_add_match_row()` in overlay.py, `_get_rock_value()` in scanner.py
- **CLEANUP:** Removed unnecessary import guards: `HAS_PRICING`, `HAS_REGION_SELECTOR` (same-project modules, always present)
- **CLEANUP:** Removed unused `get_release_notes()` from version_checker.py
- **CLEANUP:** Removed `packaging` module fallback in version_checker.py — tuple comparison is sufficient
- **CLEANUP:** Removed commented-out deferred dependencies from requirements.txt
- **KNOWN ISSUE:** Signature 4000 collision means scanner cannot distinguish I-type asteroids from surface deposits
- **NOTE:** Signature values may be corrected by CIG in SC 4.7 patch

### v3.2.0 (January 20, 2026)
*UI improvements for refinery methods and tab styling*

- **IMPROVE:** Refinery method dropdown now shows yield, speed, and cost info
- Format: `Dinyx Solventation (Yield 52.93% - Speed: Slowest - Price: Low$)`
- **IMPROVE:** Tab styling - selected tab now larger and bolder than unselected tabs
- Selected: 11pt bold with accent color; Unselected: 9pt regular with muted color
- **DOCS:** Updated claude.md with Regolith API refinery method documentation

### v3.1.2 (January 16, 2026)
*Scipy bundling fix for PyInstaller*

- **FIX:** Removed scipy excludes from PyInstaller spec - partial scipy exclusion breaks C extension imports
- **ROOT CAUSE:** EasyOCR requires scipy.ndimage, but excluding other scipy modules broke the shared binary loader
- **NOTE:** Build size will increase ~50-100MB but scipy now works correctly in frozen builds

### v3.1.1 (January 16, 2026)
*EasyOCR type hint fix*

- **FIX:** Changed type hints from `easyocr.Reader` to `Any` in scanner.py
- **ROOT CAUSE:** Type hints evaluate at class definition time; if import fails, the type hint crashes

### v3.0.0 (January 14, 2026)
*Regolith API integration complete - Ready for testing*

- **FIX:** pricing.py now reads rock compositions from Regolith cache (was looking for separate rock_types.json)
- **CHANGE:** Single source of truth - regolith_cache.json contains all rock composition data
- **REMOVE:** Dependency on static data/rock_types.json file
- **FIX:** Build script verification updated for PyInstaller _internal/ directory structure
- **READY:** Build complete, ready for testing and version control setup

### v1.0.0 (January 11, 2026)
- Initial tester release
- Fixed region scanning
- Basic OCR with threshold
- Pricing integration
- Regolith.rocks API

### v2.1.2 (January 14, 2026)
*Display name improvements*

- **FIX:** Asteroid display names now show full names ("C" → "C-type Asteroid")
- **FIX:** Added count suffix for multiples ("C-type Asteroid (x4)" for 4 asteroids)
- **NOTE:** Composition table requires Regolith cache (rock_types.json) - if missing, only basic info shown

### v2.1.1 (January 14, 2026)
*Bug fixes for EasyOCR integration*

- **FIX:** Pillow 10.0.0+ compatibility - added ANTIALIAS shim (EasyOCR uses deprecated constant)
- **FIX:** Overlay category mismatch - scanner returns `space_deposit`/`surface_deposit`/`ground_deposit`, overlay was checking for old names (`asteroid`/`deposit`/`fps_mining`)
- **FIX:** Ground deposit display now shows possible minerals list instead of "Unknown"
- **IMPROVE:** clean.py updated with `--ocr` flag to optionally remove EasyOCR models (~115MB)

### v2.1.0 (January 14, 2026) - Pre-release
*Major OCR engine migration*

- **BREAKING:** Replaced pytesseract/Tesseract with EasyOCR (deep learning OCR)
- **NEW:** Automatic model download on first use (~115MB, then offline)
- **NEW:** Lazy OCR initialization (faster startup)
- **NEW:** UI callbacks for model download progress
- **REMOVE:** Hybrid OCR mode (no longer needed with EasyOCR)
- **REMOVE:** Tesseract binary dependency
- **IMPROVE:** Simplified image preprocessing pipeline
- **IMPROVE:** Digit allowlist for maximum signature accuracy

### v2.0.0 (January 14, 2026) - Pre-release
*Designated for tester review before public release*

- **CHANGE:** Startup order - API key validation now happens first, before loading signature database and pricing
- **ADD:** "Thanks To" section in About tab acknowledging testers
- **FIX:** About tab left panel background color (was light gray, now matches dark theme)
- **IMPROVE:** clean.py - now removes deprecated files automatically
- **IMPROVE:** build.py - added pre-build verification checks
- **DOCS:** Added Development Rules to DEVLOG for AI continuity
- **DOCS:** Added Current Status section to DEVLOG

### v1.1.0 (January 12, 2026)
- **NEW:** Hybrid OCR mode (raw + adaptive)
- **FIX:** OCR misreading digits (1850 → 1950)
- **FIX:** Region selector buttons accessibility in fullscreen
- **ADD:** OpenCV dependency for adaptive thresholding
- **REMOVE:** Tobii support (deferred to future release)
- **IMPROVE:** Debug output with per-mode images

---

## Technical Decisions Log

| Decision | Rationale |
|----------|-----------|
| Fixed region over auto-detection | Reliability across HUD variants |
| EasyOCR over Tesseract | No external binary, pure Python, better accuracy on game text |
| Regolith API mandatory | Ensures data quality, supports partner |
| Screenshot-based over live capture | Works with any display mode |
| Tkinter over Qt | Lighter weight, sufficient for needs |
| Local database over API-only | Offline capability, faster lookups |
| Lazy OCR init over eager | Faster startup, download only when needed |
| CPU-only OCR default | Universal compatibility, avoids CUDA complexity |
| Comma removed from OCR allowlist | Was causing misreads like "7,480" → "7,4480"; plain digit parsing is more reliable |
| Layer 3 signature validation | OCR reads commas/periods as digits; validation + correction against known bases fixes this |
| Morphological punctuation filtering | Commas/periods are ~5-20px vs digits 100+px; remove small connected components before OCR |
| Prefer lowest count in correction | 7400 = 4× M-type is more realistic than 7440 = 62× small ground deposit |
| Startup splash screen | Torch/EasyOCR takes 15-20s to load; users need visual feedback that app is working |
| Use `Any` for easyocr type hints | Type hints evaluate at class definition; if import fails, `easyocr.Reader` crashes |
| Full scipy bundling over partial | Excluding scipy submodules breaks C extension loader; ~50-100MB size increase is acceptable for reliability |
| JSON as single source of truth for signatures | Hardcoded Python constants duplicated JSON data and could drift; deriving from JSON means only one file to update |

---

## Known Issues / Future Work

### Deferred to Future Releases
- [ ] Tobii Eye Tracker integration
- [ ] Ship signature matching (removed in v3.4.0 — re-evaluate if needed)
- [ ] Auto-detection as fallback to fixed region
- [ ] Multi-monitor support testing
- [ ] Localization for non-English clients

### Database Maintenance
- All signatures need re-verification after SC 4.7 patch (CIG may fix 4000 collision and ground deposit values)
- New deposit types may be added with SC patches
- Ship signatures removed in v3.4.0 — re-add if demand arises

---

## External Dependencies

| Dependency | Purpose | License |
|------------|---------|---------|
| easyocr | Deep learning OCR engine | Apache 2.0 |
| torch | PyTorch (EasyOCR backend) | BSD |
| torchvision | PyTorch vision utilities | BSD |
| Pillow | Image processing | HPND |
| opencv-python | Image preprocessing | Apache 2.0 |
| watchdog | Folder monitoring | Apache 2.0 |
| requests | API calls | Apache 2.0 |
| numpy | Array operations | BSD |

**Note:** First run downloads ~115MB of EasyOCR model files to `~/.EasyOCR/model/`. Subsequent runs are fully offline.

---

## Current Status / Next Steps

**Status:** v3.4.0 - Removed ship signatures, consolidated signature data to single source of truth

**Immediate priorities:**
1. ~~Fix About tab background color issue~~ ✓ (completed Jan 14)
2. ~~Update clean.py and build.py~~ ✓ (completed Jan 14)
3. ~~Change startup order (API validation first)~~ ✓ (completed Jan 14)
4. ~~Add "Thanks To" section for testers~~ ✓ (completed Jan 14)
5. ~~Migrate from pytesseract to EasyOCR~~ ✓ (completed Jan 14)
6. ~~Fix Pillow ANTIALIAS compatibility~~ ✓ (completed Jan 14)
7. ~~Fix overlay category mismatch~~ ✓ (completed Jan 14)
8. ~~Fix asteroid display names~~ ✓ (completed Jan 14)
9. ~~Connect pricing.py to Regolith cache~~ ✓ (completed Jan 14)
10. ~~Fix build script for PyInstaller _internal/ structure~~ ✓ (completed Jan 14)
11. ~~Version control setup (GitHub)~~ ✓ (completed Jan 14)
12. ~~Fix OCR comma/period misreading~~ ✓ (completed Jan 15)
13. ~~Add startup splash screen~~ ✓ (completed Jan 15)
14. ~~Fix easyocr import NameError crash~~ ✓ (completed Jan 16)
15. Testing on fresh install

**Blocking issues:**
- Signature 4000 collision (I-type + all surface deposits) — CIG-side, awaiting SC 4.7 fix

**Ready for:** Fresh install testing, distribution to testers

**Session Log - February 11, 2026 (Sessions 14-15): Game2.dcb Signature Extraction**

**Phase 1: P4K Search (Session 14)**
- SC patch dropped today (Data.p4k grew ~1GB). Created `search_mining_data.py` to search for changed mining signature values.
- Searched 1,287,040 files in Data.p4k: 11,710 mining-related files, 8,894 readable files extracted.
- **FINDING:** Mining signature values are NOT in loose XML/JSON files — compiled into `Game2.dcb` (DataCore Binary, 298MB decompressed).

**Phase 2: DCB Parsing (Session 15)**
- Built custom Game2.dcb parser from scratch using StarBreaker C# source as reference.
- Key technical corrections from initial v1 parser:
  - DataType enum values corrected (e.g., Single=0x0B not 0x0F)
  - Struct/property names use string table 2, not table 1
  - Value pool file order differs from header order (Boolean after UInt64)
  - Record definitions are 32 bytes, not 36
  - DataMapping-based offset calculation for data section

**Phase 3: Signature Value Discovery**
- Entity-to-signature chain traced through 4 struct layers:
  1. EntityClassDefinition → Components (StrongPointer array in strong pool)
  2. SSCSignatureSystemParams → radarProperties (inline StrongPointer @ byte 4)
  3. SSCRadarContactProperites → baseSignatureParams (inline StrongPointer @ byte 20)
  4. SSCSignatureSystemBaseSignatureParams → signatures (SimpleArray into Single pool)
- Signature value is at index 4 of an 8-element float32 array in the Single value pool.
- Key insight: BSP instances have ZERO StrongPointer pool entries (not accessed via pointers). They're accessed through inline StrongPointers in the struct data chain.

**Phase 4: Results**
- Successfully extracted signatures for 301 mineable/salvage entities.
- **SPACE ASTEROIDS — ALL UNCHANGED:**
  - I=4000, C=4700, S=4720, P=4750, M=4850, Q=4870, E=4900
- **SURFACE DEPOSITS — UNCHANGED:** All types (Atacamite, Felsic, Gneiss, Granite, Igneous, Obsidian, Quartzite, Shale) = 4000
- **FPS MINING ROCKS — UNCHANGED:** All types (Hadanite, Dolivine, Aphorite, etc.) = 3000
- **SALVAGE PANELS — UNCHANGED:** SalvageLock/SalvageScrap = 2000
- **CAVE DEPOSITS:** 4000 (same as surface)
- **ROC/GV MINING ROCKS — DISCREPANCY:** All 6 GroundVehicle entities = 4000 (DB says 3000)
  - `MineableRock_GroundVehicle_Carinite/Beradom/Feynmaline/Glacosite` + variants
  - Cannot determine if this changed in this patch or was always 4000
  - Needs in-game verification

**Additional Findings:**
- Salvageable ship wrecks have varying signatures by hull size (1700-3000)
- Harvestable mineral pickups (1-hand) retain old signature of 120
- Flowstone and VlkMineablePearls have 0 signature (special items)
- 8-element signature array channels: [EM(?), IR(?), ?, ?, CrossSection, ?, ?, ?]

**Scripts Created (in sc_data_extractor project):**
- `parse_dcb_v2.py` — Corrected DCB parser with StarBreaker-accurate format
- `extract_signatures.py` — Targeted BSP instance extraction
- `trace_mining_signatures.py` — Entity→component chain tracer
- `dump_all_signatures.py` — Full BSP instance dump
- `debug_entity_mapping.py` — Entity→BSP mapping diagnostics
- `debug_bsp_refs.py` — BSP reference mechanism discovery
- `extract_all_signatures.py` — Final production extraction script

**OUTPUT:** `extracted_shops/mining_signatures_extracted.json` — complete entity-to-signature mapping

**Session Log - February 6, 2026 (Session 13):**
- **REMOVE:** Ship radar cross-section data (252 entries) from `combat_analyst_db.json` — dead data, never used in matching
- **REMOVE:** `ship_lookup` builder in `scanner.py` — built a lookup table that was never queried
- **REFACTOR:** Consolidated all signature values to single source of truth (`combat_analyst_db.json`)
- Removed `KNOWN_BASE_SIGNATURES`, `ROCK_DISPLAY_NAMES`, `SIGNATURE_TO_ROCK_TYPE` module-level constants
- Now derived dynamically from JSON in `_build_lookups()`
- Salvage per-panel value now read from JSON instead of hardcoded
- **CLEANUP:** Removed empty `_on_release()` + binding in `region_selector.py`
- **CLEANUP:** Moved `import time` to module level in `splash.py`
- **CLEANUP:** Initialized `_test_overlay` in `__init__`, simplified guard in `main.py`
- **VERSION:** Bumped to v3.4.0 (also fixed version_checker.py which was still at 3.2.0)

**Session Log - February 6, 2026 (Session 12):**
- **UPDATE:** All signature values updated for SC 4.5 game changes
- Asteroids: I=4000, C=4700, S=4720, P=4750, M=4850, Q=4870, E=4900
- Surface deposits: All types now 4000 (collides with I-type — CIG bug)
- Ground deposits: Both small and large now 3000 (were 120/620 — CIG bug)
- Updated both `scanner.py` constants and `combat_analyst_db.json`
- **CLEANUP:** Removed dead code across codebase
- `overlay.py`: Removed unused `_add_match_row()` (~85 lines)
- `scanner.py`: Removed unused `_get_rock_value()` (~11 lines)
- `scanner.py`: Removed `HAS_PRICING`/`HAS_REGION_SELECTOR` import guards — direct imports for same-project modules
- `version_checker.py`: Removed unused `get_release_notes()`, removed `packaging` module fallback
- `requirements.txt`: Removed commented-out deferred dependencies (Tobii, systray, hotkeys)
- **NOTE:** Signature values may be corrected in SC 4.7 — full re-verification needed when patch drops

**Session Log - January 20, 2026 (Session 11):**
- **IMPROVE:** Refinery method dropdown now displays yield, speed, and cost information
- Old format: `Dinyx Solventation (52.93%)`
- New format: `Dinyx Solventation (Yield 52.93% - Speed: Slowest - Price: Low$)`
- Widened combobox from 28 to 62 characters to fit new format
- **IMPROVE:** Tab styling updated - selected tab now visually larger than unselected
- Unselected tabs: 9pt font, muted color, less padding
- Selected tab: 11pt bold font, accent color, more padding
- **DOCS:** Reviewed and verified claude.md refinery method data against web sources
- Confirmed yield tiers, speed categories, and cost multipliers are accurate
- **VERSION:** Bumped to v3.2.0

**Session Log - January 17, 2026 (Session 10):**
- **FEATURE:** Added "Buy Me a Coffee" button to About tab
- Position: Below Signature Types in right column
- Includes flavor text explaining the software is free and inviting support
- Links to buymeacoffee.com/Mallachi
- Yellow button (#FFDD00) with coffee emoji, wider styling
- No version bump (v3.1.2 not yet released to testers)

**Session Log - January 16, 2026 (Session 9):**
- **BUG REPORT:** Tester error: `scipy install seems to be broken (extension modules cannot be imported)`
- **ROOT CAUSE:** PyInstaller spec excluded scipy modules to reduce build size, but partial exclusion breaks scipy's shared C extension loader
- **FIX:** Removed scipy excludes from SC_Signature_Scanner.spec - full scipy now bundled
- **TRADE-OFF:** Build size increases ~50-100MB, but scipy works correctly
- Bumped version to v3.1.2

**Session Log - January 16, 2026 (Session 8):**
- **BUG REPORT:** Tester crash on startup: `NameError: name 'easyocr' is not defined`
- **ROOT CAUSE:** Type hints `Optional[easyocr.Reader]` evaluated at class definition time
- When `import easyocr` fails, the name `easyocr` doesn't exist, so the type hint crashes
- **FIX:** Changed type hints from `easyocr.Reader` to `Any` in scanner.py
- Affected: `self._ocr_reader` attribute and `_get_ocr_reader()` return type
- Now app loads even if easyocr import fails (shows proper error instead of crash)
- Bumped version to v3.1.1

**Session Log - January 15, 2026 (Session 7):**
- **BUG:** Overlay crash `TclError: bad screen distance "5 0"` when showing ground deposit popup
- **ROOT CAUSE:** Tkinter Label constructor doesn't accept tuple `pady=(5, 0)` — only `.pack()` does
- **FIX:** Moved tuple pady from Label constructor to `.pack(pady=(5, 0))` in overlay.py
- **BUG:** Signature correction picked wrong value: `74400` → `7440` instead of `7400`
- **ROOT CAUSE:** `max(candidates)` picked larger value; 7440 = 62× small ground (120) vs 7400 = 4× M-type (1850)
- **FIX:** Changed `_try_correct_signature()` to prefer lowest count: `min(candidates, key=min_count)`
- **IMPROVEMENT:** Implemented morphological filtering to remove commas/periods BEFORE OCR
- **RATIONALE:** Commas are ~5-20 pixels, digits are 100+ pixels — size-based filtering is reliable
- **NEW:** Added `_remove_small_components()` method using OpenCV connected components
- Removes components < 50 pixels, fills with background color
- Debug mode saves `04a_removed_components.png` showing removed pixels in red
- **BUG:** 20-second startup with no feedback — users think app is frozen
- **FIX:** Added splash.py with animated loading screen shown immediately
- Status messages: "Loading core modules...", "Loading OCR engine...", "Loading UI components...", "Loading pricing data..."
- Splash closes before main window appears (only one Tk root allowed)
- **TESTED:** Comma filtering works — `7,400` now correctly read as `7400`
- Bumped version to v3.1.0

**Session Log - January 14, 2026 (Session 6):**
- Investigated OCR failure: `7,480` misread as `7,4480` → parsed as `[7448, 4480]` → no match
- Root cause: Comma in allowlist causing EasyOCR to interpolate extra digits around comma position
- **FIX:** Removed comma from OCR allowlist (`'0123456789,.'` → `'0123456789.'`)
- Pattern 2 in `_extract_signatures` handles plain digit sequences, so comma removal is safe
- Tested with tighter scan region: OCR read `1850` with 0.89 confidence ✓
- **BUG:** Threading crash when showing overlay - watchdog callback runs in background thread, Tkinter requires main thread
- **FIX:** Changed `overlay.show()` to use `root.after(0, lambda: self._show_overlay(...))` for thread-safe GUI update
- Added `_show_overlay()` helper method to main.py
- **BUG:** `6.000` parsed but returned empty (period pattern worked, but value not matched)
- **FIX:** Added Pattern 2 for period-separated numbers (`\d{1,3}\.\d{3}`)
- **BUG:** `7,400` read as `74400` (comma read as digit `4` when not in allowlist)
- **ROOT CAUSE:** Both comma and period can be read as digits by OCR - no allowlist config solves this
- **FIX:** Implemented Layer 3 signature validation:
  - Added `KNOWN_BASE_SIGNATURES` constant with all valid base values
  - Added `_is_exact_multiple()` to check if value divides cleanly by any known base
  - Added `_try_correct_signature()` to fix phantom digit insertion
  - Updated `_extract_signatures()` to validate and auto-correct signatures
- Example: `74400` → not valid → try removing digits → `7400` ÷ 1850 = 4 ✓ → corrected to 7400

**Session Log - January 14, 2026 (Session 5):**
- Identified disconnect: regolith_api.py saves to regolith_cache.json, pricing.py was loading from data/rock_types.json
- Fixed pricing.py to import regolith_api and read rock_compositions from cache
- Removed rock_types_file reference from PricingManager
- Fixed build.py verification path (PyInstaller now uses _internal/ subdirectory)
- Bumped version to v3.0.0
- Build successful, ready for testing
- Tested EasyOCR on full scan results panel (standalone test) - works but accuracy limited by image quality; signature scanner's focused region approach is better suited
- **GIT:** Pushed to GitHub - encountered 100MB file limit on dist zip (221MB)
- **FIX:** Rewrote git history to remove large files from commits (`git filter-branch`)
- **FIX:** Updated .gitignore to exclude build/, dist/, *.zip
- Successfully pushed v3.0.0 to GitHub

**Session Log - January 14, 2026 (Session 4):**
- Added ROCK_DISPLAY_NAMES mapping for short asteroid codes
- Scanner now shows "C-type Asteroid" instead of just "C"
- Added count suffix for multiples: "C-type Asteroid (x4)"
- Identified missing rock_types.json as cause of empty composition table
- Bumped version to v2.1.2

**Session Log - January 14, 2026 (Session 3):**
- Fixed Pillow 10.0.0+ compatibility (ANTIALIAS constant removed, added shim)
- Fixed overlay category mismatch (scanner uses space_deposit/surface_deposit/ground_deposit)
- Fixed ground deposit mineral display (shows possible_minerals list)
- Updated clean.py with --ocr flag and --help
- Bumped version to v2.1.1

**Session Log - January 14, 2026 (Session 2):**
- **MAJOR:** Migrated OCR engine from pytesseract to EasyOCR
- Rewrote scanner.py with EasyOCR implementation
- Updated requirements.txt (easyocr, torch, torchvision)
- Updated SC_Signature_Scanner.spec with EasyOCR hidden imports and data files
- Removed hybrid OCR mode (raw/adaptive) - no longer needed
- Added lazy OCR initialization with UI callback hooks
- Added digit allowlist for maximum signature accuracy
- Bumped version to v2.1.0 (Pre-release)

**Session Log - January 14, 2026 (Session 1):**
- Fixed About tab background color (missing bg parameter)
- Added Development Rules section to DEVLOG
- Added Current Status section to DEVLOG
- Updated clean.py: now removes deprecated files (hud_calibration.py, identifier_window.py, tobii_tracker.py)
- Updated build.py: added pre-build checks, better formatting, deprecated file warnings
- Changed startup order: API key validation now happens before signature database and pricing loads
- Added "Thanks To" section in About tab
- Bumped version to v2.0.0 (Pre-release)
- Designated v2.0.0 for tester review

---

## Credits

- **Developer:** Mallachi
- **Data Sources:** 
  - Star Citizen game files (Data.p4k)
  - UEX Corp API (pricing)
  - Regolith.rocks (rock compositions)
- **Inspiration:** Wingman AI project
- **Testing:** Regolith.rocks community testers

---

## Current File Reference

*Updated: January 15, 2026*

```
SC_Signature_Scanner/
├── main.py              # Main application, tkinter UI, startup flow
├── splash.py            # Startup splash screen with loading status
├── scanner.py           # EasyOCR engine, signature matching, component filtering
├── overlay.py           # Results popup display, position adjuster
├── monitor.py           # Screenshot folder watcher (watchdog)
├── config.py            # Configuration persistence (JSON)
├── paths.py             # Path utilities for frozen exe support
├── pricing.py           # UEX API integration, value calculations
├── theme.py             # RegolithTheme, UI colors/fonts
├── region_selector.py   # Scan region definition tool
├── regolith_api.py      # Regolith.rocks API client
├── version_checker.py   # GitHub release checker
├── clean.py             # Cache/pycache cleanup utility
├── build.py             # PyInstaller build script
├── requirements.txt     # Python dependencies
├── run_scanner.bat      # Windows launch script
├── SC_Signature_Scanner.spec  # PyInstaller spec file
├── README.md            # User documentation
├── TODO.md              # Signature database reference
├── DEVLOG.md            # This file
├── data/
│   ├── combat_analyst_db.json  # Signature database
│   └── uex_prices.json         # UEX cache (runtime)
├── assets/              # UI assets (if any)
├── build/               # PyInstaller build output
├── dist/                # Distribution packages
└── screenshots/         # Test screenshots
```

**Runtime files (created on first use):**
- `config.json` — User settings, API key
- `scan_region.json` — Defined scan region coordinates
- `regolith_cache.json` — Regolith.rocks rock composition data (in user data folder)
- `SignatureScannerBugreport/` — Debug output folder (configurable)

---

*Document generated: January 12, 2026*  
*Last updated: February 6, 2026 - v3.4.0 Remove ship signatures, consolidate to single source of truth*
