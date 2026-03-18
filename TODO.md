# SC Signature Scanner - Status

## Application Version: 4.2.1
## Database Version: 4.7 (for Star Citizen 4.7)
## OCR Engine: EasyOCR (deep learning)

## Mining Categories

### Rare Asteroid Variants ✓ (NEW — SC 4.7)
Unique per-mineral signatures, 3540–3600 range. Confirmed 2026-03-18 Game2.xml.
| Mineral | Signature |
|---------|-----------|
| Beryl | 3540 |
| Taranite | 3555 |
| Borase | 3570 |
| Gold | 3585 |
| Bexalite | 3600 |

### Space Deposits (Asteroids) ✓
Ship mining only (Prospector, MOLE). Mixed mineral composition.
| Type | Signature |
|------|-----------|
| I-type | 4000 |
| C-type | 4700 |
| S-type | 4720 |
| P-type | 4750 |
| M-type | 4850 |
| Q-type | 4870 |
| E-type | 4900 |

### Surface Deposits ✓
Ship mining only (Prospector, MOLE). Mixed mineral composition.
**Note:** All surface deposits share signature 4000 (same as I-type Asteroid). Cannot distinguish by signature alone. CIG bug as of SC 4.6.
| Type | Signature |
|------|-----------|
| All types | 4000 |

### Ground Deposits ✓
ROC or FPS mining. 100% single mineral per cluster.
**Note:** Confirmed via SC 4.7 Game2.xml extraction (2026-03-18). Large ROC/GV rocks = 4000. Collides with I-type and surface deposits.

| Variant | Signature | Primary Method | Source |
|---------|-----------|----------------|--------|
| Small (FPS) | 3000 | FPS/Hand mining | 4.7 DCB ✓ |
| Large (GV/ROC) | 4000 | ROC/Vehicle mining | 4.7 DCB ✓ |

**Minerals:** Hadanite, Dolivine, Aphorite, Beradom, Glacosite, Feynmaline, Jaclium

**Cluster Rules:**
- Each cluster spawns only ONE mineral type at 100% purity
- A mineral spawns as either small OR large deposits, never both in same cluster
- Small deposits can be vehicle-mined with skill
- Large deposits can be FPS-mined collaboratively

### Subsurface Deposits
- Status: NOT IN GAME
- Expected: Late 2026-2027
- First ship: Consolidated Outland Pioneer

### Salvage ✓ (updated SC 4.7)
| Type | Signature | Notes |
|------|-----------|-------|
| Hull Panels / FPS Scrap | 2000 | Per panel — 2000 × N |
| Small Debris | 1700 | Avenger-class wreck + scrap cargo containers |
| Medium Debris | 1850 | Ares Inferno-class wreck |
| Large Debris | 2400 | C2 Hercules-class wreck |
| Capital Debris | 3000 | 890 Jump-class wreck — **COLLISION** with FPS ground deposit |

---

## Completed ✓
- [x] Database taxonomy finalized (v4.2)
- [x] All signature values verified from 2025 mining survey
- [x] Scanner updated for new ground deposit structure
- [x] PyInstaller build system configured
- [x] Path utilities for frozen exe
- [x] Test code removed
- [x] EasyOCR migration (replaced Tesseract)
- [x] Pillow 10.0.0+ compatibility (ANTIALIAS shim)
- [x] Overlay category matching fixed
- [x] Display names for asteroid types (C → "C-type Asteroid")
- [x] Regolith API integration (rock compositions from cache) — REMOVED in v4.2.0 (no longer needed)
- [x] Pricing integration reads from Regolith cache (single source of truth) — REMOVED in v4.2.0
- [x] Build script updated for PyInstaller _internal/ directory structure
- [x] Signature values updated for SC 4.5
- [x] Dead code cleanup (unused methods, unnecessary import guards)
- [x] Removed ship signatures (radar cross-section data) from database
- [x] Consolidated signature values to single source of truth (JSON database)
- [x] Removed hardcoded constants (KNOWN_BASE_SIGNATURES, ROCK_DISPLAY_NAMES, SIGNATURE_TO_ROCK_TYPE)
- [x] Minor cleanup: empty event handler, uninitialized attribute, local import

## In Progress
- [ ] Testing on fresh install

## Completed Recently
- [x] Removed Regolith API + UEX pricing system — v4.2.0 (SC 4.7 deposits are single-mineral, no composition needed)
- [x] Added salvage debris signatures (1700/1850/2400/3000) — v4.1.0
- [x] Modernized clean.py and build.py — Python 3.13, _internal/ layout
- [x] Version control setup (GitHub) - v3.0.0 pushed
- [x] Morphological filtering for OCR (removes commas/periods before scan)
- [x] Startup splash screen with loading status
- [x] Fixed overlay Tkinter crash (tuple pady)
- [x] Fixed NameError crash when easyocr import fails (type hint used `easyocr.Reader`)

## Known Issues
- Signature 4000 collides: Large Ground Deposits (ROC/GV) share 4000 with old generic surface entities — CIG-side
- Signature 3000 collides: FPS small ground deposits AND 890 Jump capital wreck debris — cannot resolve by scanner alone
- Vlk Pearls, Vlk Irradiated Pearls, Flowstone = signature 0 (undetectable by scanner)

## Future Work
- [ ] Add rare asteroid variants to overlay UI (they display generically now)
- [ ] In-game verification: confirm rare asteroid signatures are visible on HUD (3540-3600)
- [ ] GPU acceleration option for OCR (currently CPU-only)
- [ ] **Investigate Windows OCR (WinRT) as EasyOCR replacement**
  - Windows OCR is purpose-built for clean screen/UI text; EasyOCR is optimised for natural scene text (photos)
  - Expected benefits: faster startup (no 3–5s model load, no 115MB download), faster per-scan, potentially better digit accuracy on HUD fonts
  - App is already Windows-only so no portability penalty
  - Python access via `winrt` package (`winrt-Windows.Media.Ocr`)
  - Approach: implement as a second OCR backend, A/B test against EasyOCR on real SC screenshots before committing to a swap
- [ ] **Ship identification by size/performance class** — DEFERRED until SC scanner rework ships
  - Concept: use CS value to identify size class (Small/Medium/Large/XL/Capital), EM+IR ratio for performance class (Competition/Stealth/Military/Industrial)
  - Approach: one wide scan region captures all three HUD values (IR | EM | CS, left to right); EasyOCR bounding boxes identify which is which by horizontal position
  - Prerequisites: (1) extract ship CS vectors from Game2.dcb, (2) confirm size class clusters are well-separated, (3) validate with empirical multi-angle scans of known ships
  - Blocked by: upcoming SC scanner system rework — HUD layout, value ranges, and three-value structure may all change
  - Research file: ship_scan_test.md (data collection template ready)
- [x] Parse Game2.dcb for signature values — DONE (extract_all_signatures.py in sc_data_extractor)
  - Chain: Entity → SSP → RadarContactProperties → BSP → Single pool
  - All space asteroid values confirmed unchanged from SC 4.6
  - Surface deposits all confirmed 4000
  - FPS mining rocks confirmed 3000
  - ROC/GV mining rocks show 4000 (discrepancy with current DB value of 3000)

---

## Code Review Findings (15 Rules of Coding)

Findings from a comprehensive code review of all 14 source modules (~10,200 lines).
Organized by priority.

### Priority 1: Bugs / Critical

#### Thread Safety — Tkinter called from background thread
**Files:** `main.py:1285-1332` (`_on_new_screenshot`)
**Severity:** Bug — can cause UI crashes or corruption

The `_on_new_screenshot` callback is invoked by the watchdog file monitor on a **background
thread**. Inside it, `self._log()` directly modifies the `tk.Text` widget (enable → insert →
disable) and `self.stats_label.configure()` updates a label — both are tkinter operations.
Tkinter is **not thread-safe**; all widget modifications must happen on the main thread.

Only the overlay display correctly uses `self.root.after(0, ...)` (line 1320). The log writes
and stats updates do not, which means every screenshot processed is a potential crash.

**Fix:** Wrap all UI operations in `self.root.after(0, lambda: ...)` so they are scheduled on
the main thread, or refactor `_on_new_screenshot` to do processing on the background thread and
then dispatch all UI updates at the end via `root.after()`.

---

#### Multiple Tk() roots — OverlayPopup creates its own Tk instance
**Files:** `overlay.py:42`
**Severity:** Latent bug — works by accident today

`OverlayPopup.__init__` creates a brand new `tk.Tk()` root window every time it is
instantiated. Tkinter only supports **one** `Tk()` root per process; additional windows must be
`Toplevel`. This currently works because the splash screen's `Tk()` is destroyed before the
app's `Tk()` is created, and the overlay is created after that. But if the overlay is ever
instantiated differently (or if tkinter internals change), this will break with cryptic errors.

The `_test_overlay` in `main.py:1404` also creates a new `OverlayPopup`, meaning a **third**
`Tk()` root may be alive simultaneously.

**Fix:** Change `OverlayPopup` to accept an existing `Tk` root as a parameter (or use the
app's root) and create overlay windows as `Toplevel` children of that root. Remove the
`self._root = tk.Tk()` / `self._root.withdraw()` pattern entirely.

---

#### Bare except clauses — silently swallow all exceptions
**Files:** `overlay.py:55,448,457,462,466,468`, `splash.py:227`, `main.py:1661`
**Severity:** Bad practice — hides bugs, catches KeyboardInterrupt/SystemExit

There are 8+ bare `except:` clauses across the codebase that catch **everything**, including
`KeyboardInterrupt`, `SystemExit`, and `MemoryError`. This makes debugging extremely difficult
because real errors are silently discarded.

Examples:
```python
# overlay.py:55
try:
    self.window.after_cancel(self._after_id)
except:      # catches SystemExit, MemoryError, etc.
    pass

# splash.py:227
try:
    self.root.update()
    time.sleep(0.03)
except:      # if the splash breaks, you'll never know why
    break
```

**Fix:** Replace each bare `except:` with the specific exception it intends to catch:
- For tkinter cleanup: `except (tk.TclError, RuntimeError):`
- For splash animation: `except tk.TclError:`
- For window destroy: `except (tk.TclError, RuntimeError):`

---

#### os._exit(0) bypasses all cleanup
**Files:** `main.py:1663`
**Severity:** Dangerous — skips finally blocks, atexit handlers, file buffer flushes

In `exit_and_download()`, `os._exit(0)` is used to force-quit after opening the download URL.
This bypasses Python's entire shutdown sequence: `finally` blocks don't run, `atexit` handlers
are skipped, and file buffers (including the config file) may not be flushed.

**Fix:** Replace with `sys.exit(0)` or just `self.root.quit()` followed by `self.root.destroy()`.
If tkinter errors are the concern, catch them specifically rather than nuking the process.

---

### Priority 2: Architecture / Design

#### main.py is a monolith — 2,283 lines, God class
**Files:** `main.py` (entire file)
**Severity:** Maintainability problem

`SCSignatureScannerApp` handles: UI construction (1,080 lines in `_create_ui` alone), event
handling, config load/save, monitoring lifecycle, overlay management, API key validation with
retry logic, pricing initialization, update checking, and scan region management. This is at
least 5 distinct responsibilities in one class.

**Fix:** Split `_create_ui()` into dedicated methods:
- `_create_scanner_tab()` — Scanner tab UI + controls
- `_create_settings_tab()` — Settings tab UI + all setting sections
- `_create_about_tab()` — About tab UI + credits

Consider also extracting the API key validation flow (`_validate_api_key_startup`,
`_validate_key_with_retry`, `_show_api_key_dialog`) into a separate module or class, as it's
40+ lines of business logic embedded in the UI class.

---

#### ~~Scanner is coupled to pricing~~ — RESOLVED v4.2.0
`import pricing` and `_get_rock_value_and_composition()` removed from scanner.py. Scanner returns raw match data only.

---

#### DRY violations — repeated UI patterns and color constants
**Files:** `main.py:_create_ui`, `overlay.py:15-24 + 475-483`, `theme.py:328`
**Severity:** Code duplication

1. **Bordered section pattern** — The pattern of creating a border frame → inner frame → padding
   is repeated ~15 times in `_create_ui`. `RegolithTheme.create_card()` exists at `theme.py:328`
   for exactly this purpose but is **never used anywhere**.

2. **Color constants duplicated** — `OverlayPopup` (line 15-24) and `PositionAdjuster`
   (line 475-483) both redeclare the full color palette as class variables instead of referencing
   `RegolithTheme.COLORS`. If the theme changes, these won't update.

**Fix:**
- Use `RegolithTheme.create_card()` for the repeated bordered-section pattern in main.py.
- Replace color class variables in overlay.py with references to `RegolithTheme.COLORS`.

---

### Priority 3: Correctness / Data

#### ~~Stale epoch constant in regolith_api.py~~ — MOOT (regolith_api no longer called)

---

#### os.system() — potential command injection in debug folder open
**Files:** `main.py:1497-1499`
**Severity:** Low risk but bad practice

```python
elif platform.system() == 'Darwin':
    os.system(f'open "{debug_dir}"')
else:
    os.system(f'xdg-open "{debug_dir}"')
```

`os.system()` passes the string through the shell. If `debug_dir` ever contains shell
metacharacters (e.g., a path with `$`, backticks, or semicolons), this could execute arbitrary
commands. While the input is internally generated today, this is a habit worth fixing.

**Fix:** Use `subprocess.run(['open', str(debug_dir)])` on macOS and
`subprocess.run(['xdg-open', str(debug_dir)])` on Linux. These bypass the shell entirely.

---

### Priority 4: Quality / Maintainability

#### No tests — zero test coverage
**Files:** (none exist)
**Severity:** Quality gap

There are no test files and no test framework in `requirements.txt`. The most critical logic
that needs testing:

- `scanner.py:_extract_signatures()` — Regex-based parsing of noisy OCR output. This is where
  bugs most directly affect users. Test cases should cover: plain numbers ("4900"), comma-
  separated ("4,900"), period-separated ("4.900"), phantom digit correction ("49000" → "4900"),
  edge cases (too small, too large, leading zeros).
- `scanner.py:match_signature()` — Matching logic with multiple categories, confidence scoring,
  deduplication. Test exact matches, multiples, ground deposits, salvage panels, and ambiguous
  signatures (e.g., 4000 matching both I-type and surface).
- `scanner.py:_try_correct_signature()` — The digit-removal correction algorithm.
- ~~`pricing.py:calculate_rock_value()`~~ — pricing removed in v4.2.0
- `version_checker.py:_parse_version_tuple()` — Version comparison edge cases.

**Fix:** Add `pytest` to requirements.txt and create a `tests/` directory with at minimum
`test_scanner.py` covering the signature extraction and matching logic.

---

#### Magic numbers — undocumented numeric literals
**Files:** Various
**Severity:** Readability issue

Several numeric constants are used inline without named constants or sufficient context:

- `scanner.py:554` — `100 <= value <= 200000` (valid signature range)
- `scanner.py:568` — `1 <= count <= 100` (reasonable asteroid count)
- `scanner.py:313` — `min_area: int = 50` (connected component filter)
- `overlay.py:344,348` — `25000` and `10000` (ore price tier thresholds for color coding)
- `main.py:96-97` — `850, 850` (window dimensions)
- `monitor.py:55` — `5.0` (file write wait timeout)

**Fix:** Extract these to named constants at the class or module level. For example:
```python
MIN_SIGNATURE = 100
MAX_SIGNATURE = 200_000
MAX_ASTEROID_COUNT = 100
PREMIUM_ORE_PRICE_THRESHOLD = 25_000
MEDIUM_ORE_PRICE_THRESHOLD = 10_000
```

---

#### Update check uses tuple length to distinguish result types
**Files:** `main.py:1585`
**Severity:** Fragile code

```python
if len(result) == 4:  # error case
    ...
update_available, latest_version, download_url = result  # success case
```

The success and error paths return different tuple lengths (3 vs 4 elements). This is fragile
and confusing — a reader has to trace through `_check_for_updates` and `check_for_updates` to
understand what each tuple position means.

**Fix:** Use a dataclass or named tuple for the result, or have the error path return the same
3-tuple shape (e.g., `(False, None, None)` on error, which `check_for_updates` already does)
and remove the special 4-tuple error wrapper in `_check_for_updates`.

---

#### Dead code — unused functions and unreachable paths
**Files:** `paths.py:45`, `pricing.py:259,329,426`
**Severity:** Minor clutter

- `paths.py:get_asset_path()` — References an `assets/` directory that doesn't exist in the
  project. Nothing calls this function.
- `pricing.py` — Entire file is now unreferenced (no active imports). Candidate for deletion.
- `regolith_api.py` — Entire file is now unreferenced (no active imports). Candidate for deletion.

**Fix:** Remove unused functions, or if they're intended for future use, add a comment noting
that.
