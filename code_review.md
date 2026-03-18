# SC Signature Scanner — Code Review

**Date:** 2026-03-18
**Reviewer:** Claude Code (claude-sonnet-4-6)
**Scope:** Full codebase (14 modules + data/combat_analyst_db.json)
**Version:** 3.4.0

---

## Executive Summary

The SC Signature Scanner is a well-structured, purposeful desktop application. The code is generally clean, readable, and shows clear intentionality behind design decisions. The architecture is reasonable for a single-developer tkinter project: one god class for the main window (`SCSignatureScannerApp` in `main.py`), thin service modules (`scanner.py`, `pricing.py`, `regolith_api.py`), and utility/widget modules. No security-critical vulnerabilities were found — this is a local-only desktop tool with no user-generated input that reaches a shell under normal use.

The two most significant issues are a **data inconsistency bug** in the database that will cause silent mis-identification of ground deposits (CRITICAL), and **cross-thread UI updates** that will crash on Windows under load (CRITICAL). Beyond those, the main themes are: broad exception suppression hiding real errors, a monolithic `main.py` (2,200+ lines) that will become difficult to maintain, and a handful of config persistence issues that affect frozen PyInstaller builds.

**Overall risk level: Medium** — the app is functional, but the ground-deposit bug will mislead users, and the threading issue will occasionally crash the scanner when it is most needed (during active play).

---

## Critical Findings

### C-1 — Database/code value mismatch for ground deposits
**File:** `data/combat_analyst_db.json` and `scanner.py` lines 424–427
**Severity:** CRITICAL

`combat_analyst_db.json` declares both small and large ground deposit `_base_signature` as `3000`. But the About tab and historic code comments reference values of `120` (small) and `620` (large). The scanner loads both as `3000`, so:
- A real small deposit with signature 3000 is correctly detected.
- A large deposit with signature 3000 is matched as both "small ground deposit" AND "large ground deposit" simultaneously.
- The About tab copy still displays `Small (120) = FPS/Hand mining` and `Large (620) = ROC/Vehicle` — this is stale and will confuse users.

**Recommended fix:** Confirm the correct SC 4.6 values. If they are truly unified at 3000, update the About tab copy. If they were intended to remain at 120/620, fix the JSON. Either way, make the JSON, the fallback defaults in scanner.py, and the About tab text all consistent.

---

### C-2 — Cross-thread UI update in `_on_new_screenshot`
**File:** `main.py` lines 1296–1298 and 1331–1332
**Severity:** CRITICAL

The watchdog `ScreenshotHandler.on_created` runs on a background thread and calls `self._on_new_screenshot(filepath)` directly. Inside that method, `self.stats_label.configure(...)` and `self._log(...)` (which modifies a `tk.Text` widget) are called directly from the non-main thread. Tkinter on Windows is not thread-safe; calling widget methods from non-main threads produces intermittent crashes and corrupted state.

The overlay display on line 1320 correctly uses `self.root.after(0, ...)` — that pattern must be applied consistently to all UI operations in the method.

**Recommended fix:** Wrap the entire UI-touching body of `_on_new_screenshot` in `self.root.after(0, lambda: ...)`, or use a thread-safe queue that the main thread drains on a timer.

---

## High Priority Findings

### H-1 — Broad `except:` suppression throughout overlay and splash
**Files:** `overlay.py` lines 55–56, 449, 458, 462, 467; `splash.py` line 226
**Severity:** HIGH

Multiple bare `except:` blocks silently swallow all exceptions including `KeyboardInterrupt`, `SystemExit`, and `MemoryError`. While these appear in teardown paths (intentionally suppressing widget-already-destroyed errors), they are scoped too broadly and will hide real programming errors.

```python
# overlay.py line 55
try:
    self.window.after_cancel(self._after_id)
except:      # should be except tk.TclError:
    pass
```

**Recommended fix:** Replace each bare `except:` with `except tk.TclError:` (the expected exception when operating on a destroyed tkinter window). One-line change per site.

---

### H-2 — API key stored in plaintext JSON
**File:** `config.py`, `main.py` line 1739
**Severity:** HIGH (contextual — acceptable for a local gaming tool, but should be documented)

The Regolith.rocks API key is saved to `config.json` in plaintext with no file-permission restrictions. On a shared machine or in a backup sync scenario this leaks the credential. The `clean.py` script correctly removes it on cleanup, but the risk is not documented anywhere in the UI or README.

**Recommended fix:** Add a brief note in the Settings tab tooltip and the README warning users not to share `config.json`. For a production-grade implementation, use the `keyring` library to store credentials in the OS credential store.

---

### H-3 — `_open_debug_folder` uses `os.system` with unsanitised path on macOS/Linux
**File:** `main.py` lines 1497–1499
**Severity:** HIGH

```python
elif platform.system() == 'Darwin':
    os.system(f'open "{debug_dir}"')
else:
    os.system(f'xdg-open "{debug_dir}"')
```

`debug_dir` comes from a user-editable text entry (`self.debug_folder_var`). On macOS/Linux, a path containing shell metacharacters (e.g., `"; rm -rf ~/;"`) would execute arbitrary shell commands. The Windows path uses `os.startfile` which is safe.

**Recommended fix:**
```python
subprocess.run(['open', str(debug_dir)])      # macOS
subprocess.run(['xdg-open', str(debug_dir)])  # Linux
```

---

### H-4 — `fetch_all_data` calls the API three times for the same dataset
**File:** `regolith_api.py` lines 210–216
**Severity:** HIGH

```python
for system in ["STANTON", "PYRO", "NYX"]:
    try:
        rock_data = self.fetch_survey_data("shipOreByRockClassProb")
        ...
    except RegolithAPIError:
        pass  # System might not have data
```

`fetch_survey_data` is not system-specific — it returns all systems in one response. Calling it once per iteration wastes API quota (API allows 3,600 requests/day) and triples the network latency. If any call fails, all remaining systems are silently skipped with no logged reason.

**Recommended fix:** Call `fetch_survey_data` once before the loop. Propagate or log the exception rather than silently suppressing it.

---

### H-5 — `_validate_api_key_startup` blocks the main thread with `time.sleep(3)`
**File:** `main.py` lines 2051
**Severity:** HIGH

`time.sleep(3)` is called from the main thread during startup API key validation. Tkinter renders nothing during a `sleep` — the UI freezes for 3 seconds per retry with no animation or progress indication.

**Recommended fix:** Move API validation to a background thread (the same pattern used by the update checker), and show a spinner or status message while validation is in progress.

---

## Medium Priority Findings

### M-1 — `main.py` is a 2,283-line god class
**File:** `main.py`
**Severity:** MEDIUM

`SCSignatureScannerApp` handles: UI construction (~900 lines in `_create_ui`), config management, pricing integration, API key management, update checking, overlay management, and all event handlers. This is at least 5 distinct responsibilities in one class.

**Recommended refactoring:**
- Break `_create_ui` into `_create_scanner_tab()`, `_create_settings_tab()`, `_create_about_tab()` methods
- Extract API key + Regolith validation flow into a `RegolithSetupController`
- Move config load/save logic into the existing `Config` class

---

### M-2 — `Config.get()` reads the JSON file on every call
**File:** `config.py` lines 39–44
**Severity:** MEDIUM

```python
def get(self, key: str, default: Any = None) -> Any:
    cfg = self.load()   # opens and parses JSON every call
    ...
```

`Config.get()` is called on the 200ms polling timer during startup. This is unnecessary repeated I/O.

**Recommended fix:** Add an in-memory cache: `self._cache: Optional[dict] = None`. Populate on first `load()`, clear on `save()`. This reduces repeated disk access to a single load at startup.

---

### M-3 — `OverlayPopup` creates its own `tk.Tk()` root
**File:** `overlay.py` lines 41–43
**Severity:** MEDIUM

```python
self._root = tk.Tk()
self._root.withdraw()
```

A tkinter app should have exactly one `Tk()` root. Creating a second one puts the overlay and main window into separate Tk hierarchies — `grab_set` and `transient` cannot cross that boundary, and theme/font registries are not shared.

**Recommended fix:** Accept the main application `root` as a parameter and use `tk.Toplevel(root)` for overlay windows instead of creating a second `Tk()` instance.

---

### M-4 — `PricingManager` data dir defaults to relative path
**File:** `pricing.py` line 55
**Severity:** MEDIUM

```python
def __init__(self, data_dir: str = "data"):
    self.data_dir = Path(data_dir)
```

The default `"data"` resolves relative to the current working directory. In a PyInstaller bundle this is the `_MEIPASS` temp dir, which is cleaned up on exit — so the UEX price cache is lost every run.

**Recommended fix:** Default to `paths.get_user_data_path() / "data"` to match the persistent user data location that `regolith_api.py` already uses correctly.

---

### M-5 — `region_selector.py` and `config.py` write configs relative to `__file__`
**Files:** `region_selector.py` line 15, `config.py` line 16
**Severity:** MEDIUM

```python
CONFIG_FILE = Path(__file__).parent / "scan_region.json"
```

In a frozen PyInstaller exe, `__file__` resolves to the `_MEIPASS` temp directory. That directory is cleaned up when the exe exits, so the scan region and app config are lost on every restart.

**Recommended fix:** Use `paths.get_user_data_path()` for both, consistent with how `regolith_api.py` handles its cache file.

---

### M-6 — `regolith_api.py` module-level singleton is technically a race condition
**File:** `regolith_api.py` lines 346–365
**Severity:** MEDIUM (low probability in practice)

The `get_api()` singleton initialiser is called from both the main thread (API key validation) and potentially from background threads. The check-then-set on `_instance` is not atomic.

**Recommended fix:** Guard with `threading.Lock()`, or initialise the singleton eagerly at module import time.

---

### M-7 — `_extract_signatures` uses a list for O(n) duplicate check
**File:** `scanner.py` lines 497–542
**Severity:** MEDIUM

```python
if self._is_valid_signature(value) and value not in raw_values:
    raw_values.append(value)
```

`value not in raw_values` is O(n) on a list. The `match_signature` method already uses a `seen` set correctly — this should be consistent.

**Recommended fix:** Use a `set` for the duplicate check, or an `OrderedDict` to preserve insertion order while keeping O(1) lookups.

---

### M-8 — Missing or incorrect type annotations on public methods
**Files:** `scanner.py`, `config.py`
**Severity:** MEDIUM (violates project standards from CLAUDE.md)

- `scanner.py` line 63: `on_model_download_start: Optional[callable]` — `callable` is not a valid type hint; use `Optional[Callable[[], None]]`
- `scanner.py` line 825: `output_dir: Path = None` — should be `output_dir: Optional[Path] = None`
- `config.py`: `get`/`set` return/accept `Any` — acceptable, but `get` could return `T` using `TypeVar` for caller ergonomics

---

## Low Priority Findings

### L-1 — Stale About tab signature values
**File:** `main.py` lines 1110–1111
**Severity:** LOW

The About tab still shows `Small (120) = FPS/Hand mining` and `Large (620) = ROC/Vehicle` from older versions. These should be updated to match the current database values (3000) or read from the database dynamically.

---

### L-2 — `_wait_for_file` times out silently
**File:** `monitor.py` lines 55–70
**Severity:** LOW

When `_wait_for_file` times out it returns silently, and the callback proceeds on a potentially incomplete file. No log message indicates the timeout path was taken.

**Recommended fix:** Return `bool` from `_wait_for_file` and log a warning in `on_created` if it returns `False`.

---

### L-3 — `build.py` uses `os.chdir` globally
**File:** `build.py` line 59
**Severity:** LOW

`os.chdir` changes the working directory for the entire process. While fine for a standalone build script, it would cause subtle issues if `build.py` were ever imported. Prefer passing `cwd=project_dir` to subprocess calls.

---

### L-4 — Hot-path imports inside methods
**File:** `scanner.py` lines 289, 223
**Severity:** LOW

`import cv2` appears inside `_enhance_for_ocr` and `_remove_small_components`, both called on every screenshot scan. Python caches imports after the first call, but the pattern is misleading — it looks like a conditional/optional import.

**Recommended fix:** Move `cv2` to module-level imports alongside other image-processing libraries, guarded by a `HAS_CV2` flag if cv2 might be absent.

---

### L-5 — Magic numbers for deposit count limits
**File:** `scanner.py` lines 662–684
**Severity:** LOW

```python
if 1 <= count <= 50:  # Reasonable cluster size
if 1 <= count <= 30:  # Reasonable cluster size for large deposits
```

These should be named constants (`MAX_SMALL_DEPOSIT_CLUSTER = 50`, `MAX_LARGE_DEPOSIT_CLUSTER = 30`) at the top of the module.

---

### L-6 — `os._exit(0)` bypasses all cleanup
**File:** `main.py` line 1663
**Severity:** LOW

`os._exit(0)` in `exit_and_download()` skips all `finally` blocks, `atexit` handlers, and file buffer flushes. If the config file has an unflushed write, it may be left in a corrupt state.

**Recommended fix:** Replace with `sys.exit(0)`, which triggers the normal Python shutdown sequence.

---

## Positive Observations

- **Splash screen + threaded OCR load** is a thoughtful UX solution. Loading EasyOCR (115MB model, several seconds to initialise) in a background thread while keeping the splash animated is well-executed.
- **Lazy OCR initialisation** in `scanner.py` (`_get_ocr_reader`) correctly handles the "first scan triggers model download" flow with proper UI callback hooks.
- **`paths.py`** cleanly abstracts the PyInstaller `_MEIPASS` vs development path distinction. The pattern is right — it just needs to be applied consistently across all config files.
- **`_try_correct_signature`** is a thoughtful algorithm for fixing OCR phantom digits. The minimum-count heuristic as a tiebreaker is clever and domain-aware.
- **`monitor.py` `_wait_for_file`** prevents scanning half-written files — a common source of false negatives in screenshot monitors.
- **`regolith_api.py` error handling** is specific and informative — HTTP 401, 403, 429, and 5xx are each handled separately with user-readable messages.
- **`PricingManager.set_refinery_yield`** clamps input (`max(0.0, min(1.0, yield_factor))`) — simple but correct defensive programming.
- **`OverlayPopup.show`** correctly uses `window.after()` for auto-hide, avoiding raw threading in the overlay.
- **`UpdateBanner`** handles the update flow gracefully — both the "exit and download" and "continue on old version" paths are correctly implemented.
- **`clean.py`** is thorough and well-documented, including optional EasyOCR model removal.

---

## Recommended Action Plan

In priority order:

| # | Finding | Effort | Impact |
|---|---------|--------|--------|
| 1 | **C-1** Resolve ground deposit `_base_signature` mismatch in JSON vs About tab | Small | Users see wrong deposit identification |
| 2 | **C-2** Fix cross-thread `stats_label.configure` and `_log` calls in `_on_new_screenshot` | Small | Prevents intermittent UI crashes during scanning |
| 3 | **H-3** Replace `os.system` with `subprocess.run` for debug folder open | Trivial | Eliminates shell injection vector |
| 4 | **H-4** Fix `fetch_all_data` to call API once, not three times | Small | Reduces API quota usage, fixes silent error suppression |
| 5 | **H-1** Replace bare `except:` with `except tk.TclError:` in overlay/splash | Trivial | Stops masking real errors |
| 6 | **H-5** Move `time.sleep(3)` out of the main thread | Medium | Keeps UI responsive during API validation |
| 7 | **M-7** Fix `region_selector.py` and `config.py` paths to use `paths.get_user_data_path()` | Small | Fixes config loss on frozen exe restart |
| 8 | **M-4** Fix `PricingManager` data dir default | Small | Fixes price cache loss on frozen exe restart |
| 9 | **M-3** Pass main `root` into `OverlayPopup`, eliminate second `tk.Tk()` | Medium | Correct tkinter architecture |
| 10 | **L-6** Replace `os._exit(0)` with `sys.exit(0)` | Trivial | Safe shutdown sequence |
| 11 | **M-1** Extract `_create_ui` into tab-building methods | Large | Reduces god-class complexity |

---

*Generated by Claude Code — full codebase review of 14 source modules (~10,500 lines)*
