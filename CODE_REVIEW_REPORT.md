# Code Review — SC Signature Scanner v4.2.1

**Reviewer**: Claude (fresh-eyes review)
**Date**: 2026-04-08
**Files reviewed**: main.py, scanner.py, overlay.py, theme.py, monitor.py, splash.py, paths.py, version_checker.py, config.py, region_selector.py, pricing.py, regolith_api.py, requirements.txt

**Verdict**: REQUEST CHANGES (2 blocking issues)

---

## Blocking Issues (must fix before release)

### [B-001] `os.startfile` called without importing `os` — crashes on use

**File**: main.py:1316
**Issue**: `_open_debug_folder()` calls `os.startfile(debug_dir)` but `os` is never imported anywhere in main.py. This will raise a `NameError` every time a user clicks the "Open" button next to debug mode on Windows.
**Fix**: Add `import os` to the imports at the top of main.py (around line 23), or replace with `subprocess.Popen(['explorer', str(debug_dir)])` for consistency with the other platform branches already in the function.

### [B-002] `_test_screenshot` calls `_on_new_screenshot` on the main thread — OCR blocks the UI

**File**: main.py:1196-1207
**Issue**: `_test_screenshot()` calls `self._on_new_screenshot(Path(filepath))` directly from the main thread. `_on_new_screenshot` runs the OCR scan synchronously (line 1136: `self.scanner.scan_image(filepath)`), then posts results via `root.after()`. When called from the watchdog thread this is correct — the OCR runs off-thread. But when called from the UI button, the entire OCR scan (potentially several seconds) freezes the GUI.
**Fix**: Wrap the call in a background thread, similar to how the watchdog handler invokes it:
```python
def _test_screenshot(self):
    filepath = filedialog.askopenfilename(...)
    if filepath:
        threading.Thread(
            target=self._on_new_screenshot,
            args=(Path(filepath),),
            daemon=True
        ).start()
```

---

## Suggestions (author decides)

### [S-001] `HAS_CV2` checked but never guarded — crash if OpenCV missing

**File**: scanner.py:23-26, 329
**Issue**: `HAS_CV2` is set to `False` when `cv2` import fails, but `_remove_small_components()` (line 329) and `_enhance_for_ocr()` (line 311) call `cv2.cvtColor`, `cv2.threshold`, and `cv2.connectedComponentsWithStats` unconditionally. If OpenCV is not installed, the scanner crashes with `NameError: name 'cv2' is not defined` on the first scan.
**Fix**: Either remove the `HAS_CV2` guard entirely (OpenCV is a hard dependency — it's in requirements.txt) or add a check in `_enhance_for_ocr` that returns the raw array when `HAS_CV2` is False.

### [S-002] `_processing` set in `ScreenshotHandler` grows unbounded

**File**: monitor.py:24, 44, 53
**Issue**: Files are added to `self._processing` on creation and removed in `finally`, but if `_wait_for_file` raises an unexpected exception (e.g., permission error during `stat()`), or if the `callback` raises, the `finally` block does run — so this is actually fine for cleanup. However, `self.ignore_files` (line 23) is populated with the full set of existing files at monitoring start (main.py:1080-1082) and is never cleared. For a very active screenshot folder this set could grow large over a long session, though it's unlikely to cause real problems.
**Fix**: Consider using a bounded `collections.deque` or TTL-based expiry for `_processing` if long-running sessions are a concern. Low priority.

### [S-003] Splash screen creates its own `Tk()` root — two roots in process lifetime

**File**: splash.py:27, main.py:19-23, main.py:82
**Issue**: `SplashScreen.__init__` creates `self.root = tk.Tk()` (splash.py:27). After it's destroyed in `main()` (main.py:1623), `SCSignatureScannerApp.__init__` creates a second `self.root = tk.Tk()` (main.py:82). While this works in practice on CPython because the first root is fully destroyed before the second is created, creating multiple `Tk()` instances is explicitly unsupported by Tcl/Tk and can cause subtle issues (leaked Tcl interpreters, font/image caching problems). Some Tk builds may crash.
**Fix**: Create the `Tk()` root once in `main()`, pass it to both `SplashScreen` (as a withdrawn root) and the app. Or use `Toplevel` for the splash and keep the root hidden until the app is ready.

### [S-004] Version check 4-tuple / 3-tuple disambiguation is fragile

**File**: main.py:1348-1376
**Issue**: The `check()` inner function (line 1348) wraps exceptions into a 4-tuple `(False, None, None, str(e))`, while `version_checker.check_for_updates()` returns a 3-tuple. The disambiguation at line 1373 (`if len(result) == 4`) works but is brittle — if the upstream API ever adds a fourth return value, error handling breaks silently.
**Fix**: Use a dedicated exception or a named result type instead of tuple length sniffing:
```python
def check():
    try:
        self._update_check_result = version_checker.check_for_updates()
        self._update_check_error = None
    except Exception as e:
        self._update_check_result = None
        self._update_check_error = str(e)
```

### [S-005] Color constants duplicated across overlay.py and theme.py

**File**: overlay.py:14-24 (OverlayPopup), overlay.py:343-351 (PositionAdjuster), theme.py:15-44
**Issue**: Both `OverlayPopup` and `PositionAdjuster` define their own color constants (`BG_COLOR`, `ACCENT_COLOR`, `FG_COLOR`, etc.) that duplicate values from `RegolithTheme.COLORS`. If the theme palette changes, these overlays won't update.
**Fix**: Import and reference `RegolithTheme.COLORS` instead of local constants. The overlay classes already have a comment "Colors - matching RegolithTheme" acknowledging this.

### [S-006] `RegolithTheme.create_card()` exists but is never used

**File**: theme.py:328-342
**Issue**: The card creation pattern (bordered frame with inner padding) is repeated ~15 times manually in main.py `_create_ui()`. `create_card()` implements this exact pattern but is never called.
**Fix**: Either adopt `create_card()` in `_create_ui()` to reduce the 60+ lines of boilerplate, or remove it if you've decided against using it. Currently it's dead code.

### [S-007] `_load_image` does not close the image file handle

**File**: scanner.py:777-779
**Issue**: `Image.open(image_path)` opens the file lazily but keeps the file handle open until the image is garbage collected. During monitoring, rapid screenshots could hit file-in-use errors on Windows (the OS locks the file). The method also has no error handling — a corrupt image will crash the caller even though `scan_image` wraps it in a try/except.
**Fix**: Load the image eagerly and close the handle:
```python
def _load_image(self, image_path: Path) -> Optional[Image.Image]:
    try:
        img = Image.open(image_path)
        img.load()  # Force read into memory, releases file handle
        return img
    except Exception:
        return None
```

### [S-008] Magic numbers throughout the codebase

**Files**: scanner.py:298 (`64`), scanner.py:575 (`100`, `200000`), scanner.py:589 (`100`), scanner.py:694 (`50`), scanner.py:711 (`30`), scanner.py:735 (`100`), overlay.py:46 (`0.5`, `2.0`), main.py:90-91 (`850`, `850`), monitor.py:55 (`5.0`), monitor.py:70 (`0.2`)
**Issue**: Numerous literal values are used without named constants, making them hard to find, understand, and tune.
**Fix**: Extract to module-level or class-level constants. Priority ones:
- `MIN_SIGNATURE = 100`, `MAX_SIGNATURE = 200_000`
- `MIN_OCR_DIMENSION = 64`
- `MAX_CLUSTER_COUNT_SMALL = 50`, `MAX_CLUSTER_COUNT_LARGE = 30`
- `FILE_WRITE_TIMEOUT = 5.0`

### [S-009] `scan_image` returns `None` when region not configured but also returns error dict

**File**: scanner.py:147-191
**Issue**: The return type is `Optional[Dict[str, Any]]` but the function returns three different "failure" shapes: `{'error': ...}` for OCR unavailable, `{'error': ...}` for no signature in region, and `{'error': ...}` for no region configured. The caller in main.py (line 1146) checks `result.get("error")` — which works, but a `None` return from `_scan_with_fixed_region` at line 181 then falls through to the "No scan region configured" error at line 190, which is incorrect (the region IS configured, the scan just found nothing). Wait — actually line 187 handles that case with its own error. This is correct on closer inspection. No fix needed, but the control flow would be clearer with early returns.

### [S-010] `requests` in requirements.txt is unused by active code

**File**: requirements.txt:25
**Issue**: `requests>=2.31.0` is listed as a dependency but only used by `regolith_api.py`, which is dead code (confirmed: no active module imports it). This adds ~2MB of unnecessary dependencies to the distribution.
**Fix**: Remove `requests>=2.31.0` from requirements.txt. If `regolith_api.py` is revived later, add it back then.

---

## Confirmed Prior Findings (still present)

| ID | Finding | Status |
|----|---------|--------|
| Prior-1 | Update check 4-tuple/3-tuple disambiguation at main.py:1373 | **Still present** — see S-004 |
| Prior-2 | Dead files: pricing.py, regolith_api.py | **Confirmed dead** — pricing.py imports regolith_api; neither is imported by any active module |
| Prior-3 | Dead function: paths.py:get_asset_path() | **Confirmed unused** — only referenced in TODO.md |
| Prior-4 | Magic numbers throughout | **Still present** — see S-008 |
| Prior-5 | Color constants duplicated in overlay.py vs RegolithTheme | **Still present** — see S-005 |
| Prior-6 | RegolithTheme.create_card() never used | **Still present** — see S-006 |
| Prior-7 | Zero test coverage | **Still zero** — no tests/ directory exists |

## Confirmed Red-Team Findings (still present, not re-flagged)

| ID | Finding | File:Line |
|----|---------|-----------|
| F-001 | `webbrowser.open(download_url)` no URL validation | main.py:1444, theme.py:411 |
| F-002 | Reparse point check missing on folder selection | main.py:1047 |
| F-003 | No file size guard before PIL load | scanner.py:779 |
| F-004 | Dead `requests` in requirements.txt | requirements.txt:25 |
| F-005 | Broad `except Exception` in version_checker.py:81 | version_checker.py:81 |

---

## Minor Notes

- **splash.py:209**: `random.choice` in `_animate_data` is cosmetic only but `random` is not seeded — fine for visual flair, just noting it's non-deterministic output.
- **overlay.py:266**: Empty `if mineral_known: pass` block — the intent is to skip the section when the mineral is already shown in the name, but an explicit comment or inverted condition would be clearer.
- **config.py:31**: `Config.load()` catches broad `Exception` and prints to stdout. For a GUI app, these errors are invisible to the user. Consider logging or surfacing to the UI.
- **region_selector.py:260**: `self.root.mainloop()` is called inside `open()`, which means this method blocks. This is intentional (modal behavior) but unusual — typically Toplevel windows use `grab_set()` + `wait_window()` instead of a nested mainloop. The current approach works but can cause issues if the parent root's mainloop is already running.
- **scanner.py:264**: `primary_sig = max(signatures)` picks the largest signature value as the primary match. This is a design choice, but in cases where OCR returns both a real signature and a spurious large number, the spurious one wins. Consider using the value with the highest OCR confidence instead.
- **main.py:1080-1082**: Existing file enumeration uses three separate `glob()` calls for `.png`, `.jpg`, `.jpeg`. Missing `.webp` and `.bmp` which are in `ScreenshotHandler.VALID_EXTENSIONS` (monitor.py:18). If a user has existing `.webp` screenshots, they would be re-processed on start.
- **monitor.py:55-70**: `_wait_for_file` busy-loops with `time.sleep(0.2)` on the watchdog thread. This is fine for the use case but the 5-second timeout means a deleted-before-written file will block the thread for 5 seconds. The watchdog thread is shared across all handlers, so this could delay detection of subsequent screenshots.
