# Live Window Capture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the PrintScreen + folder-watch workflow with optional live capture of the calibrated signature region directly from the running `starcitizen.exe` window at ~30 Hz, gated by a byte-hash + N-frame stability counter so OCR fires only on stable, changed content.

**Architecture:** Two new pure-Python modules (`window_finder.py`, `live_capture.py`) plus targeted additions to `scanner.py`, `region_selector.py`, `bridge.py`, the React UI, and the PyInstaller spec. Live mode coexists with folder-watch mode behind a Scanner-module toggle; both feed the same downstream `bridge._scan_and_push` pipeline.

**Tech Stack:** Python 3.10+, `mss` (screen capture), `pywin32` (window enumeration / client-rect geometry), `psutil` (PID → process name), `hashlib.blake2b` (cheap byte hashing), existing `EasyOCR` / `cv2` / `Pillow` / `pywebview` / React stack.

**Spec:** [`docs/superpowers/specs/2026-05-27-live-window-capture-design.md`](../specs/2026-05-27-live-window-capture-design.md)

**Dependencies between tasks:** Tasks 2, 3, 4, 5, 6 are independent. Task 7 (live_capture orchestration) depends on 2, 3, 5, 6. Task 8 depends on 4. Task 9 depends on 4, 7, 8. Task 10 depends on 9. Tasks 11, 12 stand alone.

---

## File structure

**Create:**
- `window_finder.py` — locate the SC window; return `WindowInfo` dataclass
- `live_capture.py` — `StabilityTracker` + `compute_abs_capture_rect` + `LiveCapture` thread
- `tests/__init__.py` — marker file
- `tests/conftest.py` — shared fixtures
- `tests/test_window_finder.py`
- `tests/test_scanner_pil.py`
- `tests/test_region_selector_storage.py`
- `tests/test_live_capture_stability.py`
- `tests/test_live_capture_geometry.py`
- `tests/test_live_capture_loop.py`
- `pytest.ini` — pytest config
- `requirements-dev.txt` — pytest only (kept separate from runtime deps)
- `docs/manual-test-live-capture.md` — release-time manual checklist

**Modify:**
- `scanner.py` — split `scan_image` into a thin loader + a new `scan_pil_image` entry point that accepts a `PIL.Image` directly with an optional explicit `region` kwarg
- `region_selector.py` — add `load_window_region` / `save_window_region` / `clear_window_region` / `is_window_region_configured`; refactor `RegionSelector.open` so it can be opened with an in-memory `PIL.Image`
- `bridge.py` — add `get_scan_mode`, `set_scan_mode`, `calibrate_region_live`, `find_sc_window_status`; refactor `start_monitoring` → mode-dispatched `start_engagement` (keep `start_monitoring` as an alias for backwards-compat with existing JS until UI migrates); add `_scan_pil_and_push` parallel to `_scan_and_push`
- `ui/main/app.jsx` — Scanner module mode toggle (FOLDER / LIVE); REGION module "Calibrate from live frame" button; status pill in live mode
- `requirements.txt` — add `mss`, `pywin32`, `psutil` runtime deps
- `SC_Signature_Scanner.spec` — add the three new packages to `hiddenimports` and `collect_submodules`

---

## Task 1: Test infrastructure

**Files:**
- Create: `requirements-dev.txt`
- Create: `pytest.ini`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

This project has no `tests/` directory today. We need pytest set up before any TDD task can run. This task is short and produces a baseline: a single placeholder test that passes.

- [ ] **Step 1: Create `requirements-dev.txt`**

```
pytest>=8.0.0
```

- [ ] **Step 2: Create `pytest.ini` at repo root**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_functions = test_*
addopts = -v --tb=short
```

- [ ] **Step 3: Create `tests/__init__.py` (empty)**

```python
```

- [ ] **Step 4: Create `tests/conftest.py`**

```python
"""Shared pytest fixtures."""
import sys
from pathlib import Path

# Make the project root importable so tests can `import scanner`, `import live_capture`, etc.
sys.path.insert(0, str(Path(__file__).parent.parent))
```

- [ ] **Step 5: Create a smoke test `tests/test_smoke.py` to confirm collection works**

```python
def test_pytest_runs():
    assert 1 + 1 == 2
```

- [ ] **Step 6: Install dev deps and run pytest**

```bash
pip install -r requirements-dev.txt
pytest
```
Expected: `1 passed`.

- [ ] **Step 7: Commit**

```bash
git add requirements-dev.txt pytest.ini tests/
git commit -m "test: bootstrap pytest infrastructure"
```

---

## Task 2: `window_finder.py` — locate the SC window

**Files:**
- Create: `window_finder.py`
- Create: `tests/test_window_finder.py`

Returns a `WindowInfo` describing the SC client area's screen rectangle, or `None` if `starcitizen.exe` isn't a top-level window. Used by `live_capture` every probe tick.

- [ ] **Step 1: Write the failing test for the `WindowInfo` dataclass shape**

`tests/test_window_finder.py`:
```python
import pytest
from unittest.mock import patch

import window_finder


def test_window_info_is_immutable_dataclass():
    info = window_finder.WindowInfo(
        hwnd=12345,
        client_rect=(100, 200, 1920, 1080),
        is_minimized=False,
        is_foreground=True,
    )
    assert info.hwnd == 12345
    assert info.client_rect == (100, 200, 1920, 1080)
    # Frozen — assignment should raise
    with pytest.raises(Exception):
        info.hwnd = 1  # type: ignore[misc]
```

- [ ] **Step 2: Run test, expect failure**

```bash
pytest tests/test_window_finder.py::test_window_info_is_immutable_dataclass -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'window_finder'`.

- [ ] **Step 3: Create `window_finder.py` with just the dataclass**

```python
"""Locate the running Star Citizen window and return its client-area rect.

Used by live_capture to point mss.grab at the correct absolute screen rect.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class WindowInfo:
    """Immutable snapshot of the SC window's geometry at the moment of lookup."""

    hwnd: int
    client_rect: tuple[int, int, int, int]  # (x, y, w, h) in screen coords
    is_minimized: bool
    is_foreground: bool


def find_sc_window() -> Optional[WindowInfo]:
    """Locate Star Citizen's top-level window.

    Returns None if no matching window is found.
    """
    raise NotImplementedError
```

- [ ] **Step 4: Run test, expect pass**

```bash
pytest tests/test_window_finder.py::test_window_info_is_immutable_dataclass -v
```
Expected: PASS.

- [ ] **Step 5: Write failing tests for `find_sc_window` happy path + miss path**

Append to `tests/test_window_finder.py`:
```python
def _fake_enum_returning(hwnds_with_titles):
    """Build a fake win32gui.EnumWindows that yields the given (hwnd, title) pairs."""
    def fake_enum_windows(callback, _):
        for hwnd, _title in hwnds_with_titles:
            callback(hwnd, None)
    return fake_enum_windows


def test_find_sc_window_returns_none_when_no_match():
    with patch.object(window_finder, "_iter_top_level_windows", return_value=iter([])):
        assert window_finder.find_sc_window() is None


def test_find_sc_window_matches_by_process_name():
    fake = {
        9999: {
            "process_name": "starcitizen.exe",
            "title": "Star Citizen",
            "client_rect": (10, 20, 1920, 1080),
            "is_minimized": False,
            "is_foreground": True,
        }
    }
    with patch.object(window_finder, "_iter_top_level_windows", return_value=iter(fake.items())):
        info = window_finder.find_sc_window()
    assert info is not None
    assert info.hwnd == 9999
    assert info.client_rect == (10, 20, 1920, 1080)
    assert info.is_minimized is False


def test_find_sc_window_matches_case_insensitive_process_name():
    fake = {
        7: {
            "process_name": "StarCitizen.EXE",
            "title": "Star Citizen",
            "client_rect": (0, 0, 800, 600),
            "is_minimized": False,
            "is_foreground": False,
        }
    }
    with patch.object(window_finder, "_iter_top_level_windows", return_value=iter(fake.items())):
        info = window_finder.find_sc_window()
    assert info is not None
    assert info.hwnd == 7


def test_find_sc_window_falls_back_to_title_when_process_lookup_fails():
    """psutil may raise on a foreign process — title fallback must still match."""
    fake = {
        42: {
            "process_name": None,  # simulate psutil failure
            "title": "Star Citizen",
            "client_rect": (0, 0, 800, 600),
            "is_minimized": False,
            "is_foreground": False,
        }
    }
    with patch.object(window_finder, "_iter_top_level_windows", return_value=iter(fake.items())):
        info = window_finder.find_sc_window()
    assert info is not None
    assert info.hwnd == 42
```

- [ ] **Step 6: Run tests, expect failures**

```bash
pytest tests/test_window_finder.py -v
```
Expected: FAILs (the function still raises `NotImplementedError`).

- [ ] **Step 7: Implement `_iter_top_level_windows` and `find_sc_window`**

Replace the body of `window_finder.py` with:
```python
"""Locate the running Star Citizen window and return its client-area rect.

Used by live_capture to point mss.grab at the correct absolute screen rect.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Optional

import psutil
import win32con
import win32gui
import win32process


SC_PROCESS_NAME = "starcitizen.exe"
SC_TITLE_PREFIX = "star citizen"  # case-insensitive substring match


@dataclass(frozen=True)
class WindowInfo:
    """Immutable snapshot of the SC window's geometry at the moment of lookup."""

    hwnd: int
    client_rect: tuple[int, int, int, int]  # (x, y, w, h) in screen coords
    is_minimized: bool
    is_foreground: bool


def _iter_top_level_windows() -> Iterator[tuple[int, dict]]:
    """Yield (hwnd, info) for each visible top-level window.

    `info` keys: process_name (str | None), title (str), client_rect, is_minimized, is_foreground.
    """
    hwnds: list[int] = []

    def collect(hwnd: int, _: object) -> bool:
        if win32gui.IsWindowVisible(hwnd):
            hwnds.append(hwnd)
        return True

    win32gui.EnumWindows(collect, None)
    fg = win32gui.GetForegroundWindow()

    for hwnd in hwnds:
        title = win32gui.GetWindowText(hwnd) or ""

        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            process_name = psutil.Process(pid).name() if pid else None
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            process_name = None

        # GetClientRect returns (0,0,w,h); ClientToScreen translates to screen coords.
        try:
            left, top, right, bottom = win32gui.GetClientRect(hwnd)
            sx, sy = win32gui.ClientToScreen(hwnd, (left, top))
            client_rect = (sx, sy, right - left, bottom - top)
        except Exception:
            continue

        try:
            placement = win32gui.GetWindowPlacement(hwnd)
            is_minimized = placement[1] == win32con.SW_SHOWMINIMIZED
        except Exception:
            is_minimized = False

        yield hwnd, {
            "process_name": process_name,
            "title": title,
            "client_rect": client_rect,
            "is_minimized": is_minimized,
            "is_foreground": hwnd == fg,
        }


def find_sc_window() -> Optional[WindowInfo]:
    """Locate Star Citizen's top-level window.

    Match by process name first (starcitizen.exe, case-insensitive). Fall back
    to window-title match when psutil can't read the process (rare; happens on
    elevated processes the current user doesn't own).

    Returns None if no match found.
    """
    title_fallback: Optional[tuple[int, dict]] = None

    for hwnd, info in _iter_top_level_windows():
        proc = (info.get("process_name") or "").lower()
        if proc == SC_PROCESS_NAME:
            return WindowInfo(
                hwnd=hwnd,
                client_rect=info["client_rect"],
                is_minimized=info["is_minimized"],
                is_foreground=info["is_foreground"],
            )
        title = (info.get("title") or "").lower()
        if SC_TITLE_PREFIX in title and title_fallback is None:
            title_fallback = (hwnd, info)

    if title_fallback is not None:
        hwnd, info = title_fallback
        return WindowInfo(
            hwnd=hwnd,
            client_rect=info["client_rect"],
            is_minimized=info["is_minimized"],
            is_foreground=info["is_foreground"],
        )

    return None
```

- [ ] **Step 8: Run all window_finder tests, expect pass**

```bash
pytest tests/test_window_finder.py -v
```
Expected: 4 passed.

- [ ] **Step 9: Commit**

```bash
git add window_finder.py tests/test_window_finder.py
git commit -m "feat: locate the Star Citizen window for live capture"
```

---

## Task 3: `scanner.py` refactor — `scan_pil_image` entry point

**Files:**
- Modify: `scanner.py:160-215` (the `scan_image` method)
- Create: `tests/test_scanner_pil.py`

Split `scan_image(path)` so live mode can pass an in-memory `PIL.Image` directly. `scan_image` keeps working unchanged for the folder-watch path.

- [ ] **Step 1: Write a failing test for `scan_pil_image` accepting an explicit region**

`tests/test_scanner_pil.py`:
```python
"""scan_pil_image entry point — accepts an in-memory PIL Image with optional explicit region."""
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw, ImageFont

import paths
from scanner import SignatureScanner


def _make_signature_image(value: str, size=(220, 60)) -> Image.Image:
    """Render a synthetic SC-style signature image — black background, white digits."""
    img = Image.new("RGB", size, color=(0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Use the default bitmap font; pixel dimensions are deterministic across systems.
    draw.text((10, 10), value, fill=(255, 255, 255))
    return img


def test_scan_pil_image_accepts_explicit_region_and_extracts_signature():
    """Given an image and an explicit region covering the digits, signature is extracted."""
    db_path = paths.get_base_path() / "data" / "combat_analyst_db.json"
    scanner = SignatureScanner(db_path)

    img = _make_signature_image("3540")  # Beryl (Rare)

    # Stub OCR so the test doesn't depend on EasyOCR being initialized.
    with patch.object(
        scanner, "_ocr_signature", return_value=([3540], "3540", 0.95)
    ):
        result = scanner.scan_pil_image(img, region=(0, 0, img.width, img.height))

    assert result is not None
    assert result.get("signature") == 3540
    assert result.get("method") == "fixed"
    assert any(m.get("mineral", "").lower() == "beryl" for m in result.get("matches", []))


def test_scan_pil_image_returns_none_on_no_signatures():
    db_path = paths.get_base_path() / "data" / "combat_analyst_db.json"
    scanner = SignatureScanner(db_path)
    img = Image.new("RGB", (100, 30), color=(0, 0, 0))
    with patch.object(scanner, "_ocr_signature", return_value=([], "", 0.0)):
        result = scanner.scan_pil_image(img, region=(0, 0, 100, 30))
    assert result is None


def test_scan_image_still_works_via_scan_pil_image(tmp_path: Path):
    """Existing scan_image API must keep working — it now delegates to scan_pil_image."""
    db_path = paths.get_base_path() / "data" / "combat_analyst_db.json"
    scanner = SignatureScanner(db_path)

    img = _make_signature_image("3540")
    img_path = tmp_path / "shot.png"
    img.save(img_path)

    # Provide a configured region so scan_image takes the fixed-region branch.
    with patch("scanner.region_selector") as mock_rs, \
         patch.object(scanner, "_ocr_signature", return_value=([3540], "3540", 0.95)):
        mock_rs.is_configured.return_value = True
        mock_rs.load_region.return_value = (0, 0, img.width, img.height)
        result = scanner.scan_image(img_path)

    assert result is not None
    assert result.get("signature") == 3540
```

- [ ] **Step 2: Run, expect failure**

```bash
pytest tests/test_scanner_pil.py -v
```
Expected: FAIL with `AttributeError: 'SignatureScanner' object has no attribute 'scan_pil_image'`.

- [ ] **Step 3: Refactor `scanner.py`**

Replace the existing `scan_image` method (currently at `scanner.py:160-215`) with the following two methods:

```python
    def scan_image(self, image_path: Path) -> Optional[Dict[str, Any]]:
        """Scan an image file for signature values."""
        available, error = self.is_ocr_available()
        if not available:
            return {'error': f'OCR not available: {error}'}

        img = self._load_image(image_path)
        if img is None:
            return {'error': f'Failed to load image: {image_path.name}'}

        self.last_debug_info = {
            'image_path': str(image_path),
            'debug_files': [],
            'method': None,
        }
        return self.scan_pil_image(img)

    def scan_pil_image(
        self,
        img: Image.Image,
        *,
        region: Optional[Tuple[int, int, int, int]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Scan an in-memory image.

        Args:
            img: The image to scan (already loaded, full RGB).
            region: Explicit (x1, y1, x2, y2) within `img`. When provided, this
                overrides the on-disk scan_region.json and is used as-is — live
                mode passes (0, 0, w, h) because the image is already the ROI.
                When None, falls back to region_selector.load_region().

        Returns:
            Same shape as the old scan_image: a dict with 'signature', 'matches',
            'method', 'ocr_confidence', etc., or None when no signature found,
            or {'error': ...} on failure.
        """
        available, error = self.is_ocr_available()
        if not available:
            return {'error': f'OCR not available: {error}'}

        # Generate timestamp prefix for this scan session (preserves existing
        # debug-file behaviour for file-based scans).
        self._debug_prefix = datetime.now().strftime("%Y%m%d_%H%M%S_")
        # Ensure the bookkeeping dict exists even when scan_pil_image is called
        # directly (e.g. by live mode), not via scan_image.
        if not isinstance(getattr(self, "last_debug_info", None), dict):
            self.last_debug_info = {'debug_files': [], 'method': None}
        else:
            self.last_debug_info.setdefault('debug_files', [])
            self.last_debug_info.setdefault('method', None)

        try:
            width, height = img.size
            self.last_debug_info['image_size'] = (width, height)

            if self.debug_mode:
                try:
                    self.debug_dir.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    print(f"[DEBUG] Could not create debug dir {self.debug_dir}: {e}")
                    raise
                img.save(self._debug_path("00_original.png"))
                self.last_debug_info['debug_files'].append(
                    f"{self._debug_prefix}00_original.png"
                )

            # Determine the region to scan: explicit > stored > error.
            if region is not None:
                x1, y1, x2, y2 = region
            elif region_selector.is_configured():
                x1, y1, x2, y2 = region_selector.load_region()
            else:
                return {'error': 'Scan region not configured. Define it in Settings.'}

            # Clamp inside image (preserved from the old _scan_with_fixed_region).
            x1 = max(0, min(x1, width - 1))
            y1 = max(0, min(y1, height - 1))
            x2 = max(0, min(x2, width))
            y2 = max(0, min(y2, height))
            if x2 <= x1 or y2 <= y1:
                return {'error': 'Invalid scan region (degenerate after clamp)'}

            result = self._scan_region(img, x1, y1, x2, y2, "fixed")
            if result:
                self.last_debug_info['method'] = 'fixed_region'
                return result
            return {'error': 'No signature detected in scan region'}

        except Exception as e:
            if self.debug_mode:
                import traceback
                with open(self._debug_path("99_error.txt"), 'w') as f:
                    f.write(traceback.format_exc())
            return {'error': str(e)}
```

Delete the now-unreferenced `_scan_with_fixed_region` method (it lives at `scanner.py:217-239`) — its logic is folded into `scan_pil_image` above.

- [ ] **Step 4: Run new tests, expect pass**

```bash
pytest tests/test_scanner_pil.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Sanity-check nothing else broke (full pytest run)**

```bash
pytest
```
Expected: all green (smoke + window_finder + scanner_pil).

- [ ] **Step 6: Commit**

```bash
git add scanner.py tests/test_scanner_pil.py
git commit -m "refactor: split scan_image into a PIL-Image entry point for live capture"
```

---

## Task 4: Window-relative region storage

**Files:**
- Modify: `region_selector.py:14-65` (add new I/O functions next to existing screen-pixel ones)
- Create: `tests/test_region_selector_storage.py`

Add four functions that mirror the existing screen-pixel I/O but persist coordinates relative to the SC client area's top-left. Used by live mode.

- [ ] **Step 1: Write failing tests for window-region I/O**

`tests/test_region_selector_storage.py`:
```python
"""Window-relative scan_region_window.json — load/save/clear/is_configured."""
from pathlib import Path
from unittest.mock import patch

import region_selector


def _patch_config_path(tmp_path: Path):
    """Redirect WINDOW_CONFIG_FILE to tmp_path so tests don't touch real user data."""
    return patch.object(region_selector, "WINDOW_CONFIG_FILE", tmp_path / "scan_region_window.json")


def test_load_window_region_returns_none_when_missing(tmp_path: Path):
    with _patch_config_path(tmp_path):
        assert region_selector.load_window_region() is None
        assert region_selector.is_window_region_configured() is False


def test_save_and_load_window_region_roundtrip(tmp_path: Path):
    with _patch_config_path(tmp_path):
        region_selector.save_window_region(100, 200, 300, 240)
        assert region_selector.load_window_region() == (100, 200, 300, 240)
        assert region_selector.is_window_region_configured() is True


def test_clear_window_region(tmp_path: Path):
    with _patch_config_path(tmp_path):
        region_selector.save_window_region(0, 0, 10, 10)
        region_selector.clear_window_region()
        assert region_selector.load_window_region() is None
        assert region_selector.is_window_region_configured() is False


def test_load_window_region_returns_none_on_invalid_json(tmp_path: Path):
    target = tmp_path / "scan_region_window.json"
    target.write_text("not json", encoding="utf-8")
    with _patch_config_path(tmp_path):
        assert region_selector.load_window_region() is None
```

- [ ] **Step 2: Run, expect failures**

```bash
pytest tests/test_region_selector_storage.py -v
```
Expected: FAIL — `WINDOW_CONFIG_FILE`, `load_window_region`, etc. don't exist.

- [ ] **Step 3: Add the new I/O to `region_selector.py`**

Insert after the existing `CONFIG_FILE` line (`region_selector.py:17`):
```python
WINDOW_CONFIG_FILE = paths.get_user_data_path() / "scan_region_window.json"
```

And insert after the existing `is_configured` function (`region_selector.py:62-64`):
```python
def load_window_region() -> Optional[Tuple[int, int, int, int]]:
    """Load the window-relative scan region.

    Returns:
        (x1, y1, x2, y2) in coordinates relative to the SC client area's
        top-left, or None if not configured / file unreadable.
    """
    if WINDOW_CONFIG_FILE.exists():
        try:
            with open(WINDOW_CONFIG_FILE, 'r') as f:
                data = json.load(f)
                return (data['x1'], data['y1'], data['x2'], data['y2'])
        except (json.JSONDecodeError, KeyError, IOError):
            pass
    return None


def save_window_region(x1: int, y1: int, x2: int, y2: int) -> None:
    """Persist a window-relative scan region."""
    data = {
        'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2,
        'width': x2 - x1, 'height': y2 - y1,
    }
    with open(WINDOW_CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def clear_window_region() -> None:
    """Delete the window-relative scan region file."""
    if WINDOW_CONFIG_FILE.exists():
        WINDOW_CONFIG_FILE.unlink()


def is_window_region_configured() -> bool:
    """True if a window-relative scan region has been saved."""
    return WINDOW_CONFIG_FILE.exists()
```

- [ ] **Step 4: Run tests, expect pass**

```bash
pytest tests/test_region_selector_storage.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add region_selector.py tests/test_region_selector_storage.py
git commit -m "feat: add window-relative scan region storage (scan_region_window.json)"
```

---

## Task 5: `live_capture.StabilityTracker` — pure state machine

**Files:**
- Create: `live_capture.py` (initial skeleton; expanded in Tasks 6 and 7)
- Create: `tests/test_live_capture_stability.py`

The stability counter logic that gates OCR. Pure-Python, no IO, fully unit-testable. Decision returned per observed digest:
- `"no_change"` — same as last seen, but not yet stable enough OR already emitted
- `"ongoing"` — different from last seen but still building stability
- `"stable_change"` — stable enough AND differs from `last_emitted_hash` → caller should run OCR

- [ ] **Step 1: Write failing tests**

`tests/test_live_capture_stability.py`:
```python
"""StabilityTracker — pure-logic gate for 'when should OCR fire?'."""
from live_capture import StabilityTracker


def test_first_observation_is_ongoing():
    tracker = StabilityTracker(stable_frames=3)
    assert tracker.observe(b"A") == "ongoing"


def test_reaches_stable_change_after_n_identical():
    tracker = StabilityTracker(stable_frames=3)
    assert tracker.observe(b"A") == "ongoing"
    assert tracker.observe(b"A") == "ongoing"
    assert tracker.observe(b"A") == "stable_change"


def test_further_identical_observations_after_stable_are_no_change():
    tracker = StabilityTracker(stable_frames=3)
    for _ in range(3):
        tracker.observe(b"A")
    # Now A is the emitted hash. More A's should not re-fire.
    assert tracker.observe(b"A") == "no_change"
    assert tracker.observe(b"A") == "no_change"


def test_flicker_resets_seen_count():
    tracker = StabilityTracker(stable_frames=3)
    tracker.observe(b"A")
    tracker.observe(b"A")
    # Flicker — different hash, count resets.
    assert tracker.observe(b"B") == "ongoing"
    assert tracker.observe(b"A") == "ongoing"
    assert tracker.observe(b"A") == "ongoing"
    assert tracker.observe(b"A") == "stable_change"


def test_stable_change_to_different_value():
    tracker = StabilityTracker(stable_frames=2)
    tracker.observe(b"A")
    assert tracker.observe(b"A") == "stable_change"
    # Now content changes and stabilizes on B.
    assert tracker.observe(b"B") == "ongoing"
    assert tracker.observe(b"B") == "stable_change"


def test_empty_rearm_clears_last_emitted():
    tracker = StabilityTracker(stable_frames=2)
    tracker.observe(b"A")
    assert tracker.observe(b"A") == "stable_change"
    tracker.empty_rearm()  # OCR returned no signatures
    # Same hash should fire again now (looking-away-then-back case).
    assert tracker.observe(b"A") == "ongoing"
    assert tracker.observe(b"A") == "stable_change"


def test_reset_clears_all_state():
    tracker = StabilityTracker(stable_frames=2)
    tracker.observe(b"A")
    tracker.observe(b"A")  # stable_change
    tracker.reset()
    # Both last_seen and last_emitted are cleared — A is fresh again.
    assert tracker.observe(b"A") == "ongoing"
    assert tracker.observe(b"A") == "stable_change"
```

- [ ] **Step 2: Run, expect failures**

```bash
pytest tests/test_live_capture_stability.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'live_capture'`.

- [ ] **Step 3: Create `live_capture.py` with the StabilityTracker class only**

```python
"""Live signature scanning from the running Star Citizen window.

Three units, each in this file:
  - StabilityTracker — pure-logic gate (this task)
  - compute_abs_capture_rect — pure geometry helper (next task)
  - LiveCapture — capture loop / thread / orchestration (next task)
"""
from __future__ import annotations

from typing import Literal, Optional


Decision = Literal["no_change", "ongoing", "stable_change"]


class StabilityTracker:
    """Decide when a captured region's content has stabilized into a new value.

    The capture loop calls `observe(digest)` once per probe tick. The tracker
    returns:
        - "ongoing" — the hash just changed or hasn't repeated enough times yet.
        - "stable_change" — the hash has repeated `stable_frames` times AND
          differs from the last digest that produced an emission. The caller
          should run OCR.
        - "no_change" — the hash is stable but matches the last emitted one
          (we've already reported this content; don't re-fire).

    After running OCR, the caller decides whether to call `empty_rearm()`
    (OCR found no signatures — clear the emitted-hash memo so the same hash
    can re-fire later) or do nothing (OCR succeeded — the tracker has already
    recorded the emitted hash).
    """

    def __init__(self, stable_frames: int = 3) -> None:
        if stable_frames < 1:
            raise ValueError("stable_frames must be >= 1")
        self.stable_frames = stable_frames
        self._last_seen: Optional[bytes] = None
        self._seen_count = 0
        self._last_emitted: Optional[bytes] = None

    def observe(self, digest: bytes) -> Decision:
        if digest == self._last_seen:
            self._seen_count += 1
        else:
            self._last_seen = digest
            self._seen_count = 1

        if self._seen_count == self.stable_frames:
            if digest != self._last_emitted:
                self._last_emitted = digest
                return "stable_change"
            return "no_change"

        if self._seen_count > self.stable_frames:
            # Already stable and emitted (or no-change'd) — keep silent.
            return "no_change"

        return "ongoing"

    def empty_rearm(self) -> None:
        """Called after OCR returned no signatures; allow the same hash to fire next time."""
        self._last_emitted = None

    def reset(self) -> None:
        """Drop all state — used when the window moves and the capture rect changes."""
        self._last_seen = None
        self._seen_count = 0
        self._last_emitted = None
```

- [ ] **Step 4: Run tests, expect pass**

```bash
pytest tests/test_live_capture_stability.py -v
```
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add live_capture.py tests/test_live_capture_stability.py
git commit -m "feat: stability tracker for live-capture change detection"
```

---

## Task 6: `compute_abs_capture_rect` — geometry helper

**Files:**
- Modify: `live_capture.py` (add function)
- Create: `tests/test_live_capture_geometry.py`

Pure function that takes the SC client rect + window-relative ROI and produces the absolute screen rect to feed to `mss.grab`. Clamps the ROI inside the client area; returns `None` if the result is degenerate.

- [ ] **Step 1: Write failing tests**

`tests/test_live_capture_geometry.py`:
```python
"""compute_abs_capture_rect — clamp the window-relative region inside the client rect."""
from live_capture import compute_abs_capture_rect


def test_simple_case_returns_translated_rect():
    """Client at (100,200) size 1920x1080, ROI window-rel (50,60)->(170,90) → abs (150,260,120,30)."""
    client = (100, 200, 1920, 1080)
    region_window_rel = (50, 60, 170, 90)
    assert compute_abs_capture_rect(client, region_window_rel) == (150, 260, 120, 30)


def test_clamps_to_client_bounds_when_region_overflows():
    """ROI extending past the client edge gets clamped, not rejected."""
    client = (0, 0, 1000, 500)
    region_window_rel = (900, 400, 1100, 600)  # right/bottom overflow
    assert compute_abs_capture_rect(client, region_window_rel) == (900, 400, 100, 100)


def test_returns_none_for_degenerate_region_after_clamp():
    """Region entirely outside the client area collapses to width/height <= 0."""
    client = (0, 0, 800, 600)
    region_window_rel = (900, 700, 950, 750)
    assert compute_abs_capture_rect(client, region_window_rel) is None


def test_returns_none_when_clamped_too_small():
    """Below the (10, 5) minimum size — treat as degenerate."""
    client = (0, 0, 800, 600)
    region_window_rel = (100, 100, 105, 103)  # 5x3 — too small
    assert compute_abs_capture_rect(client, region_window_rel) is None


def test_negative_client_origin_supported_for_left_of_primary_monitor():
    """SC on a monitor with negative origin (left-of-primary) — mss handles it natively."""
    client = (-1920, 0, 1920, 1080)
    region_window_rel = (100, 50, 220, 80)
    assert compute_abs_capture_rect(client, region_window_rel) == (-1820, 50, 120, 30)
```

- [ ] **Step 2: Run, expect failure**

```bash
pytest tests/test_live_capture_geometry.py -v
```
Expected: FAIL — `compute_abs_capture_rect` not defined.

- [ ] **Step 3: Add the function to `live_capture.py`**

Append below `StabilityTracker`:
```python
MIN_ROI_W = 10
MIN_ROI_H = 5


def compute_abs_capture_rect(
    client_rect: tuple[int, int, int, int],
    region_window_rel: tuple[int, int, int, int],
) -> Optional[tuple[int, int, int, int]]:
    """Translate a window-relative ROI into an absolute screen rect for mss.grab.

    Args:
        client_rect: (x, y, w, h) of the SC client area in screen coords.
        region_window_rel: (x1, y1, x2, y2) of the ROI in coordinates relative
            to the client area's top-left.

    Returns:
        (left, top, width, height) for mss.grab(), or None if the ROI clamps
        to a degenerate area (smaller than MIN_ROI_W × MIN_ROI_H).
    """
    cx, cy, cw, ch = client_rect
    x1, y1, x2, y2 = region_window_rel

    # Clamp inside (0..cw, 0..ch) — window-relative.
    x1 = max(0, min(x1, cw))
    y1 = max(0, min(y1, ch))
    x2 = max(0, min(x2, cw))
    y2 = max(0, min(y2, ch))

    w = x2 - x1
    h = y2 - y1
    if w < MIN_ROI_W or h < MIN_ROI_H:
        return None

    return (cx + x1, cy + y1, w, h)
```

- [ ] **Step 4: Run tests, expect pass**

```bash
pytest tests/test_live_capture_geometry.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add live_capture.py tests/test_live_capture_geometry.py
git commit -m "feat: window-relative ROI to absolute screen rect with clamping"
```

---

## Task 7: `LiveCapture` — thread, loop, orchestration

**Files:**
- Modify: `live_capture.py` (add `LiveCapture` class)
- Create: `tests/test_live_capture_loop.py`

Owns the background thread. Dependencies (`find_sc_window`, `mss.mss()`, `scanner.scan_pil_image`, `region_selector.load_window_region`) are injected via constructor parameters so tests can stub them.

- [ ] **Step 1: Write failing tests for the high-level state transitions**

`tests/test_live_capture_loop.py`:
```python
"""LiveCapture — capture loop / thread / orchestration.

Strategy: drive the loop body synchronously via _tick(), bypassing the thread
entirely. The thread is dead-simple wrapping around _tick() in a sleep loop and
isn't usefully unit-testable on its own.
"""
from typing import Optional
from unittest.mock import MagicMock

import pytest

from live_capture import LiveCapture
from window_finder import WindowInfo


class FakeShot:
    def __init__(self, raw: bytes, w: int, h: int) -> None:
        self.raw = raw
        self.width = w
        self.height = h


class FakeMss:
    """Stand-in for mss.mss() returning canned shots in sequence."""

    def __init__(self, shots: list[FakeShot]) -> None:
        self._shots = list(shots)
        self.calls: list[dict] = []

    def grab(self, monitor: dict) -> FakeShot:
        self.calls.append(monitor)
        return self._shots.pop(0) if self._shots else self._shots and self._shots[-1]


def _make_live(
    *,
    window: Optional[WindowInfo],
    shots: Optional[list[FakeShot]] = None,
    region: Optional[tuple[int, int, int, int]] = (0, 0, 100, 30),
    scan_result: Optional[dict] = None,
) -> tuple[LiveCapture, MagicMock]:
    finder = MagicMock(return_value=window)
    scanner = MagicMock()
    scanner.scan_pil_image.return_value = scan_result
    region_loader = MagicMock(return_value=region)
    emit = MagicMock()
    mss_factory = MagicMock(return_value=FakeMss(shots or []))
    live = LiveCapture(
        scanner=scanner,
        emit=emit,
        find_sc_window=finder,
        load_window_region=region_loader,
        mss_factory=mss_factory,
        probe_hz=30,
        stable_frames=2,
    )
    return live, emit


def test_status_starts_stopped():
    live, _ = _make_live(window=None)
    assert live.status == "stopped"


def test_tick_with_no_window_sets_waiting():
    live, _ = _make_live(window=None)
    live.start_for_tests()
    live.tick()
    assert live.status == "waiting"


def test_tick_with_minimized_window_sets_idle_minimized():
    win = WindowInfo(hwnd=1, client_rect=(0, 0, 1920, 1080), is_minimized=True, is_foreground=False)
    live, _ = _make_live(window=win)
    live.start_for_tests()
    live.tick()
    assert live.status == "idle_minimized"


def test_tick_with_visible_window_captures_and_runs_ocr_after_stable_frames():
    win = WindowInfo(hwnd=1, client_rect=(0, 0, 1920, 1080), is_minimized=False, is_foreground=True)
    same_bytes = b"\x00" * (100 * 30 * 4)
    shots = [FakeShot(same_bytes, 100, 30) for _ in range(3)]
    scan_result = {
        "signature": 3540,
        "matches": [{"name": "Beryl (Rare)"}],
        "method": "fixed",
        "ocr_confidence": 0.9,
    }
    live, emit = _make_live(window=win, shots=shots, scan_result=scan_result)
    live.start_for_tests()
    # Two stable_frames=2 → second identical tick triggers OCR.
    live.tick()
    live.tick()
    assert live.status == "running"
    emit.assert_called_once()
    payload = emit.call_args.args[0]
    assert payload["signature"] == 3540
    assert emit.call_args.kwargs == {"source": "live"}


def test_empty_ocr_result_re_arms_so_same_hash_fires_again():
    """Looking away then back at the same rock must fire the overlay again."""
    win = WindowInfo(hwnd=1, client_rect=(0, 0, 1920, 1080), is_minimized=False, is_foreground=True)
    same_bytes = b"\xAA" * (100 * 30 * 4)
    shots = [FakeShot(same_bytes, 100, 30) for _ in range(6)]
    # First two ticks: scanner returns a real result. Then it returns None
    # (looking away). Then a real result again.
    live, emit = _make_live(window=win, shots=shots, scan_result=None)
    live.start_for_tests()
    # First emit — needs to be a real result so we have something to re-arm from.
    live.scanner.scan_pil_image.return_value = {"signature": 1, "matches": [{"name": "x"}]}
    live.tick()
    live.tick()  # stable_change → emit
    assert emit.call_count == 1
    # Now OCR returns None (blank region between rocks). The tracker should re-arm.
    live.scanner.scan_pil_image.return_value = None
    live.tick()  # still same hash but now no-change/already-emitted → not emit
    # Tick again with the same hash but now OCR returns a result again
    live.scanner.scan_pil_image.return_value = {"signature": 1, "matches": [{"name": "x"}]}
    live.tick()  # first identical observation post-rearm
    live.tick()  # second → stable_change → emit
    assert emit.call_count == 2


def test_window_move_invalidates_hash_state():
    """When the window moves, the next captured content is treated as fresh."""
    win_a = WindowInfo(hwnd=1, client_rect=(0, 0, 1920, 1080), is_minimized=False, is_foreground=True)
    win_b = WindowInfo(hwnd=1, client_rect=(500, 0, 1920, 1080), is_minimized=False, is_foreground=True)
    same_bytes = b"\xCC" * (100 * 30 * 4)
    shots = [FakeShot(same_bytes, 100, 30) for _ in range(4)]
    scan_result = {"signature": 1, "matches": [{"name": "x"}]}
    finder = MagicMock(side_effect=[win_a, win_a, win_b, win_b])
    scanner = MagicMock()
    scanner.scan_pil_image.return_value = scan_result
    emit = MagicMock()
    live = LiveCapture(
        scanner=scanner,
        emit=emit,
        find_sc_window=finder,
        load_window_region=lambda: (0, 0, 100, 30),
        mss_factory=lambda: FakeMss(shots),
        probe_hz=30,
        stable_frames=2,
    )
    live.start_for_tests()
    live.tick()  # win_a, ongoing
    live.tick()  # win_a, stable_change → emit
    assert emit.call_count == 1
    live.tick()  # win_b — geometry changed, reset, then ongoing
    live.tick()  # win_b, stable_change → emit again
    assert emit.call_count == 2


def test_starts_with_missing_region_sets_error():
    win = WindowInfo(hwnd=1, client_rect=(0, 0, 1920, 1080), is_minimized=False, is_foreground=True)
    live, emit = _make_live(window=win, region=None)
    started = live.start_for_tests()
    assert started["ok"] is False
    assert "calibrate" in started["error"].lower()


def test_stop_returns_to_stopped():
    win = WindowInfo(hwnd=1, client_rect=(0, 0, 1920, 1080), is_minimized=False, is_foreground=True)
    live, _ = _make_live(window=win)
    live.start_for_tests()
    live.stop()
    assert live.status == "stopped"
```

- [ ] **Step 2: Run, expect failures**

```bash
pytest tests/test_live_capture_loop.py -v
```
Expected: FAIL — `LiveCapture` not defined.

- [ ] **Step 3: Append the `LiveCapture` class to `live_capture.py`**

```python
import hashlib
import threading
import time
from typing import Any, Callable, Literal

from PIL import Image


Status = Literal["stopped", "waiting", "idle_minimized", "running", "error"]


# These imports stay lazy so the unit tests don't need win32 / mss installed
# to exercise the pure logic.
def _default_mss_factory():
    import mss
    return mss.mss()


def _default_find_sc_window():
    from window_finder import find_sc_window
    return find_sc_window()


def _default_load_window_region():
    import region_selector
    return region_selector.load_window_region()


class LiveCapture:
    """Background capture loop. Probes the SC window at probe_hz and emits
    scan results via the supplied `emit` callback when content changes and
    stabilizes."""

    def __init__(
        self,
        *,
        scanner: Any,
        emit: Callable[..., None],
        find_sc_window: Callable[[], Any] = _default_find_sc_window,
        load_window_region: Callable[[], Any] = _default_load_window_region,
        mss_factory: Callable[[], Any] = _default_mss_factory,
        probe_hz: int = 30,
        stable_frames: int = 3,
    ) -> None:
        self.scanner = scanner
        self.emit = emit
        self._find_sc_window = find_sc_window
        self._load_window_region = load_window_region
        self._mss_factory = mss_factory

        self._tick_period = 1.0 / probe_hz
        self._idle_period = 0.5  # waiting / idle_minimized
        self._tracker = StabilityTracker(stable_frames=stable_frames)
        self._status: Status = "stopped"
        self._consecutive_grab_failures = 0

        self._region_window_rel: Optional[tuple[int, int, int, int]] = None
        self._prev_client_rect: Optional[tuple[int, int, int, int]] = None
        self._abs_capture_rect: Optional[tuple[int, int, int, int]] = None

        self._mss: Any = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    @property
    def status(self) -> Status:
        return self._status

    def start(self) -> dict:
        """Start the background capture thread."""
        if self._thread and self._thread.is_alive():
            return {"ok": True, "alreadyRunning": True}
        result = self._prepare_start()
        if not result["ok"]:
            return result
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="LiveCapture")
        self._thread.start()
        return {"ok": True}

    def start_for_tests(self) -> dict:
        """Initialize state without launching the thread — for unit tests."""
        return self._prepare_start()

    def _prepare_start(self) -> dict:
        region = self._load_window_region()
        if region is None:
            self._status = "error"
            return {
                "ok": False,
                "error": "Live region not calibrated — use REGION → Calibrate from live frame.",
            }
        self._region_window_rel = region
        self._tracker.reset()
        self._prev_client_rect = None
        self._abs_capture_rect = None
        self._consecutive_grab_failures = 0
        self._status = "waiting"
        return {"ok": True}

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        self._thread = None
        self._mss = None
        self._status = "stopped"

    # ---- Loop -----------------------------------------------------------------

    def _run(self) -> None:
        self._mss = self._mss_factory()
        try:
            while not self._stop_event.is_set():
                start = time.monotonic()
                next_period = self.tick()
                elapsed = time.monotonic() - start
                remaining = max(0.0, next_period - elapsed)
                self._stop_event.wait(remaining)
        finally:
            self._mss = None

    def tick(self) -> float:
        """Run one probe iteration. Returns the desired sleep before next tick."""
        if self._region_window_rel is None:
            self._status = "error"
            return self._idle_period

        try:
            info = self._find_sc_window()
        except Exception:
            info = None

        if info is None:
            self._tracker.reset()
            self._prev_client_rect = None
            self._abs_capture_rect = None
            self._status = "waiting"
            return self._idle_period

        if info.is_minimized:
            self._status = "idle_minimized"
            return self._idle_period

        if info.client_rect != self._prev_client_rect:
            self._abs_capture_rect = compute_abs_capture_rect(
                info.client_rect, self._region_window_rel
            )
            self._prev_client_rect = info.client_rect
            self._tracker.reset()

        if self._abs_capture_rect is None:
            self._status = "error"
            return self._idle_period

        try:
            shot = (self._mss or self._mss_factory()).grab({
                "left": self._abs_capture_rect[0],
                "top": self._abs_capture_rect[1],
                "width": self._abs_capture_rect[2],
                "height": self._abs_capture_rect[3],
            })
        except Exception:
            self._consecutive_grab_failures += 1
            if self._consecutive_grab_failures >= 3:
                self._status = "error"
            return self._tick_period
        self._consecutive_grab_failures = 0

        raw = bytes(shot.raw)
        digest = hashlib.blake2b(raw, digest_size=8).digest()
        decision = self._tracker.observe(digest)
        self._status = "running"

        if decision != "stable_change":
            return self._tick_period

        img = Image.frombytes("RGB", (shot.width, shot.height), raw, "raw", "BGRX")
        try:
            result = self.scanner.scan_pil_image(
                img, region=(0, 0, shot.width, shot.height)
            )
        except Exception as e:
            self.emit({"error": f"Live scan failed: {e}"}, source="live")
            return self._tick_period

        if result is None or result.get("error") or not result.get("matches"):
            # Blank / no-lock — re-arm so the same content can fire later.
            self._tracker.empty_rearm()
            return self._tick_period

        self.emit(result, source="live")
        return self._tick_period
```

Make sure the imports at the top of `live_capture.py` are now:
```python
from __future__ import annotations

import hashlib
import threading
import time
from typing import Any, Callable, Literal, Optional

from PIL import Image
```

- [ ] **Step 4: Run all live_capture tests, expect pass**

```bash
pytest tests/test_live_capture_stability.py tests/test_live_capture_geometry.py tests/test_live_capture_loop.py -v
```
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add live_capture.py tests/test_live_capture_loop.py
git commit -m "feat: LiveCapture thread, state machine, and ROI capture loop"
```

---

## Task 8: `region_selector.py` — accept an in-memory image + window-relative save

**Files:**
- Modify: `region_selector.py` — three small, surgical edits to existing `RegionSelector`

Today `RegionSelector.open(image_path)` always loads from disk. Live-mode calibration has the image in memory (just grabbed via `mss`), so we add two new kwargs: `image` (skip the file-load) and `save_as_window_relative` (persist via `save_window_region` instead of `save_region`). All other Tkinter UI code is untouched.

No unit tests — this is Tkinter UI; integration coverage is the manual checklist in Task 12.

- [ ] **Step 1: Initialize the new flag in `__init__`**

In `RegionSelector.__init__` (around `region_selector.py:69`), find the block that ends with:
```python
        self.root: Optional[tk.Toplevel] = None
        self.canvas: Optional[tk.Canvas] = None
```
And append after it:
```python
        self._save_as_window_relative: bool = False
```

- [ ] **Step 2: Change the signature of `open` and short-circuit the file-load when `image` is provided**

Find the existing `open` method signature (around `region_selector.py:93`):
```python
    def open(self, image_path: Optional[Path] = None):
```
Replace with:
```python
    def open(
        self,
        image_path: Optional[Path] = None,
        *,
        image: Optional[Image.Image] = None,
        save_as_window_relative: bool = False,
    ):
```

Then replace the existing image-loading prelude (the block that today reads):
```python
        # Get image path
        if image_path is None:
            image_path = filedialog.askopenfilename(
                title="Select Screenshot",
                filetypes=[
                    ("Image files", "*.png *.jpg *.jpeg"),
                    ("PNG files", "*.png"),
                    ("JPEG files", "*.jpg *.jpeg"),
                ]
            )
            if not image_path:
                return
            image_path = Path(image_path)

        # Load image
        try:
            self.original_image = Image.open(image_path)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load image:\n{e}")
            return
```
With:
```python
        # Persist the save-mode flag so _save() knows which storage to use.
        self._save_as_window_relative = save_as_window_relative

        # Three call modes:
        #   1. open(image=<PIL.Image>, save_as_window_relative=True) — live mode.
        #   2. open(image_path=<Path>) — given file.
        #   3. open() — prompt for a file.
        if image is not None:
            self.original_image = image
        else:
            if image_path is None:
                picked = filedialog.askopenfilename(
                    title="Select Screenshot",
                    filetypes=[
                        ("Image files", "*.png *.jpg *.jpeg"),
                        ("PNG files", "*.png"),
                        ("JPEG files", "*.jpg *.jpeg"),
                    ],
                )
                if not picked:
                    return
                image_path = Path(picked)
            try:
                self.original_image = Image.open(image_path)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load image:\n{e}")
                return
```

All Tkinter window/canvas/button code below this prelude stays untouched.

- [ ] **Step 3: Make `_save` dispatch on the flag**

Find the existing `_save` method (`region_selector.py:330`). Replace the line that reads:
```python
        save_region(x1, y1, x2, y2)
```
With:
```python
        if self._save_as_window_relative:
            save_window_region(x1, y1, x2, y2)
        else:
            save_region(x1, y1, x2, y2)
```

- [ ] **Step 4: Update the one call site in `bridge.py` (Task 9 already plans to use the new kwargs)**

No change required here — Task 9, Step 4 already calls `selector.open(image=img, save_as_window_relative=True)`. (If you reached Task 8 before Task 9 and need to test in isolation, you can stub it temporarily by adding a `python -c` smoke test that imports the module and instantiates `RegionSelector` to make sure the signature change parses.)

- [ ] **Step 5: Verify nothing broke**

```bash
pytest
```
Expected: all green (no new tests, but the refactor mustn't regress existing ones).

- [ ] **Step 6: Commit**

```bash
git add region_selector.py
git commit -m "refactor: RegionSelector.open accepts in-memory image + window-relative save"
```

---

## Task 9: `bridge.py` — scan_mode + calibrate_region_live + dispatched start

**Files:**
- Modify: `bridge.py` — class body additions and refactor of `start_monitoring`/`stop_monitoring`

Wires the live-capture path into the JS-exposed API. Bridge code is hard to unit-test (pywebview side effects), so coverage here is via the manual checklist in Task 12.

- [ ] **Step 1: Add new imports at the top of `bridge.py`**

Insert after the existing `from monitor import ScreenshotMonitor` line (~line 25):
```python
from live_capture import LiveCapture
from window_finder import find_sc_window
import mss
```

- [ ] **Step 2: Add `live_capture` to `__init__`**

Inside `Bridge.__init__`, after `self.monitor: Optional[ScreenshotMonitor] = None` (~line 48):
```python
        self.live_capture: Optional[LiveCapture] = None
```

- [ ] **Step 3: Add `get_scan_mode` / `set_scan_mode` JS-exposed methods**

After `get_initial_state` (~bridge.py:100), append:
```python
    def get_scan_mode(self) -> str:
        cfg = self.config.load() or {}
        mode = cfg.get("scan_mode", "folder")
        return mode if mode in ("folder", "live") else "folder"

    def set_scan_mode(self, mode: str) -> dict[str, Any]:
        if mode not in ("folder", "live"):
            return {"ok": False, "error": f"Unknown scan mode: {mode}"}
        was_running = (self.monitor and self.monitor.is_running) or (
            self.live_capture and self.live_capture.status not in ("stopped",)
        )
        self.config.set("scan_mode", mode)
        if was_running:
            self.stop_engagement()
            return self.start_engagement()
        return {"ok": True}
```

- [ ] **Step 4: Add `calibrate_region_live`**

Append below `set_scan_mode`:
```python
    def calibrate_region_live(self) -> dict[str, Any]:
        """One-shot: grab the SC client area, open the region picker on that
        image, persist the rect window-relative."""
        info = find_sc_window()
        if info is None:
            return {"ok": False, "error": "Star Citizen not running"}

        x, y, w, h = info.client_rect
        with mss.mss() as sct:
            shot = sct.grab({"left": x, "top": y, "width": w, "height": h})

        from PIL import Image as _Image
        img = _Image.frombytes("RGB", (shot.width, shot.height), bytes(shot.raw), "raw", "BGRX")

        import region_selector
        selector = region_selector.RegionSelector(parent=None)
        selector.open(image=img, save_as_window_relative=True)
        return {"ok": True}
```

- [ ] **Step 5: Add `find_sc_window_status`**

Append:
```python
    def find_sc_window_status(self) -> dict[str, Any]:
        """For the Scanner module's status pill."""
        status = self.live_capture.status if self.live_capture else "stopped"
        info = find_sc_window()
        return {
            "scStatus": "running" if (info and not info.is_minimized) else (
                "minimized" if info and info.is_minimized else "missing"
            ),
            "captureStatus": status,
        }
```

- [ ] **Step 6: Refactor `start_monitoring` and `stop_monitoring` into mode-dispatched `start_engagement` / `stop_engagement`**

Replace the existing `start_monitoring` and `stop_monitoring` methods (`bridge.py:272-294`) with:

```python
    def start_engagement(self) -> dict[str, Any]:
        mode = self.get_scan_mode()
        if mode == "live":
            return self._start_live()
        return self._start_folder()

    def stop_engagement(self) -> dict[str, Any]:
        if self.live_capture is not None:
            self.live_capture.stop()
            self.live_capture = None
        if self.monitor is not None:
            self.monitor.stop()
            self.monitor = None
        return {"ok": True}

    # Backwards-compat aliases used by existing JS until UI migrates.
    def start_monitoring(self) -> dict[str, Any]:
        return self.start_engagement()

    def stop_monitoring(self) -> dict[str, Any]:
        return self.stop_engagement()

    def _start_folder(self) -> dict[str, Any]:
        cfg = self.config.load() or {}
        folder = cfg.get("screenshot_folder", "")
        if not folder or not Path(folder).is_dir():
            return {"ok": False, "error": "Screenshot folder is not set or does not exist."}
        if self.monitor and self.monitor.is_running:
            return {"ok": True, "alreadyRunning": True}
        self.monitor = ScreenshotMonitor(folder=folder, callback=self._on_screenshot)
        self.monitor.start()
        return {"ok": True}

    def _start_live(self) -> dict[str, Any]:
        if self.scanner is None:
            return {"ok": False, "error": "Scanner not initialized"}
        self.live_capture = LiveCapture(
            scanner=self.scanner,
            emit=self._on_live_result,
        )
        return self.live_capture.start()
```

- [ ] **Step 7: Add the live result callback**

Append below `_scan_and_push` (`bridge.py:709`):
```python
    def _on_live_result(self, result: dict[str, Any], *, source: str = "live") -> None:
        """Callback fired on the LiveCapture thread when OCR produces a result.

        Parallels _on_screenshot/_scan_and_push but starts from a result dict
        rather than a file path. Uses 'live' as the synthetic 'file' label.
        """
        from datetime import datetime
        synthetic = Path(f"live:{datetime.now().strftime('%H%M%S')}")
        payload = self._build_detection_payload(synthetic, result)
        self._push_to_main("onDetection", payload)
        if not payload.get("error") and payload.get("matches"):
            self._show_overlay(self._build_overlay_payload(payload))
```

- [ ] **Step 8: Smoke-test by launching the app**

```bash
python app_webview.py
```
Expected: app starts; no import errors; existing folder-watch ENGAGE flow still works (mode defaults to "folder" when `scan_mode` key is absent in config).

- [ ] **Step 9: Commit**

```bash
git add bridge.py
git commit -m "feat: bridge wires live-capture mode behind scan_mode + calibrate_region_live"
```

---

## Task 10: UI — Scanner mode toggle + REGION calibrate-from-live button

**Files:**
- Modify: `ui/main/app.jsx`

> NOTE TO IMPLEMENTER: read the current Scanner module and REGION module markup in `app.jsx` first to match the existing component conventions (Tailwind-ish class names, `pywebview.api.<method>` calls, state hooks). The changes below describe behavior only — match existing styling.

- [ ] **Step 1: Add `scanMode` state to the Scanner module**

Around the existing `useState` declarations for monitoring state, add:
```jsx
const [scanMode, setScanMode] = useState('folder');

useEffect(() => {
  window.pywebview?.api.get_scan_mode().then(setScanMode);
}, []);

const onModeChange = async (mode) => {
  setScanMode(mode);
  await window.pywebview.api.set_scan_mode(mode);
};
```

- [ ] **Step 2: Render a `[FOLDER ◖ LIVE]` segmented control next to the ENGAGE button**

Two `<button>`s wrapped in a small container; the active one gets the existing "active button" styling, the other gets the dim style. Clicking either calls `onModeChange`.

- [ ] **Step 3: When `scanMode === 'live'`, show a "WAITING FOR STAR CITIZEN" / "RUNNING — 30 Hz" / "IDLE (MINIMIZED)" / "ERROR" pill driven by polling `find_sc_window_status`**

```jsx
useEffect(() => {
  if (scanMode !== 'live') return;
  const id = setInterval(() => {
    window.pywebview?.api.find_sc_window_status().then(setLiveStatus);
  }, 1000);
  return () => clearInterval(id);
}, [scanMode]);
```

- [ ] **Step 4: When `scanMode === 'folder'`, hide the screenshot-folder picker requirement check; when `scanMode === 'live'`, hide the folder picker and show a "Live region calibrated: yes/no" indicator + a link to the REGION module**

Driven off a new bridge call `is_live_region_configured` — add it to bridge:
```python
    def is_live_region_configured(self) -> bool:
        import region_selector
        return region_selector.is_window_region_configured()
```
(Add to Task 9's bridge edits if you reach this step before having merged Task 9; otherwise add as a tiny follow-up commit.)

- [ ] **Step 5: REGION module — add a second button "PICK FROM LIVE FRAME" next to the existing "PICK REGION"**

Calls `window.pywebview.api.calibrate_region_live()`. Show a toast (existing toast mechanism in the UI) when the response is `{ok: false}`.

- [ ] **Step 6: Manual verification**

Run the app and confirm:
1. Mode toggle persists across restart.
2. ENGAGE in `folder` mode uses the screenshot folder (existing behavior).
3. ENGAGE in `live` mode with no calibrated region shows an error toast about calibrating.
4. PICK FROM LIVE FRAME with SC not running shows "Star Citizen not running".
5. PICK FROM LIVE FRAME with SC running opens the existing region picker overlaid on a fresh capture; saving persists `scan_region_window.json`.

- [ ] **Step 7: Commit**

```bash
git add ui/main/app.jsx bridge.py
git commit -m "feat(ui): Scanner mode toggle + REGION calibrate-from-live button"
```

---

## Task 11: PyInstaller spec + requirements

**Files:**
- Modify: `requirements.txt`
- Modify: `SC_Signature_Scanner.spec`

- [ ] **Step 1: Add runtime deps to `requirements.txt`**

Append:
```
# ===== Live window capture (v6.1+) =====
mss>=9.0.0
pywin32>=306
psutil>=5.9.0
```

- [ ] **Step 2: Install locally to make sure the modules import**

```bash
pip install -r requirements.txt
python -c "import mss, win32gui, psutil; print('ok')"
```
Expected: `ok` printed.

- [ ] **Step 3: Update `SC_Signature_Scanner.spec` hidden imports**

Inside the `hiddenimports` list in the spec (`SC_Signature_Scanner.spec:65-109`), append:
```python
    # Live window capture (v6.1+)
    'mss',
    'mss.windows',
    'win32gui',
    'win32process',
    'win32con',
    'psutil',
```

And below the existing `collect_submodules` calls (`SC_Signature_Scanner.spec:114-118`), append:
```python
hiddenimports += collect_submodules('mss')
hiddenimports += collect_submodules('win32')  # pulls win32gui, win32process, etc.
hiddenimports += collect_submodules('psutil')
```

- [ ] **Step 4: Rebuild and confirm the EXE launches**

```bash
pyinstaller --clean SC_Signature_Scanner.spec
./dist/SC_Signature_Scanner/SC_Signature_Scanner.exe
```
Expected: app launches; in the Scanner module, switching to LIVE mode shows the new toggle without import errors.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt SC_Signature_Scanner.spec
git commit -m "build: bundle mss/pywin32/psutil for live capture"
```

---

## Task 12: Manual test checklist + DEVLOG entry

**Files:**
- Create: `docs/manual-test-live-capture.md`
- Modify: `DEVLOG.md` (append a v6.1.0 / live-capture entry)

Spec Section 5 lists 9 manual scenarios. This task lifts them into a release checklist.

- [ ] **Step 1: Create `docs/manual-test-live-capture.md`**

```markdown
# Manual Test Checklist — Live Window Capture

Run this once per release of any change touching `window_finder.py`,
`live_capture.py`, `region_selector.py` (open_with_image), or the Scanner /
REGION modules in `ui/main/app.jsx`.

**Prerequisites:**
- Star Citizen installed and runnable.
- `scan_region_window.json` calibrated against your current SC HUD layout
  (REGION module → PICK FROM LIVE FRAME).

## Scenarios

- [ ] **Cold start, SC closed.** ENGAGE in LIVE mode → status pill reads
  "WAITING FOR STAR CITIZEN". Launch SC → status flips to "RUNNING — 30 Hz"
  within ~1 second of the game window appearing.

- [ ] **Detection latency.** With a known mineable in view, overlay fires
  within ~150 ms of the signature appearing on the HUD.

- [ ] **No re-fire on static content.** Stand on the same rock 10 seconds →
  overlay fires exactly once. Detection log shows one entry.

- [ ] **Look-away re-arm.** Look away (signature gone) → look back at the
  same rock → overlay fires again. Both detections in the log.

- [ ] **Window-move robustness.** Drag the SC window across the desktop
  mid-session → no spurious detection during the move; first new stable
  signature after the move fires correctly.

- [ ] **Minimize idle.** Minimize SC → status pill flips to
  "IDLE (MINIMIZED)"; CPU usage drops (verify in Task Manager). Restore →
  capture resumes.

- [ ] **Region out-of-bounds.** Resize SC so the window is smaller than the
  calibrated region's bottom-right corner → status reads "ERROR" with an
  "out of bounds — recalibrate" message. Re-enlarge → capture resumes
  without re-engaging.

- [ ] **Mid-session mode switch.** While LIVE is running, switch the toggle
  to FOLDER → live thread stops cleanly (verify in logs), folder watcher
  starts on the configured screenshot folder.

- [ ] **SC closes mid-session.** Close SC → status returns to "WAITING FOR
  STAR CITIZEN"; no errors logged. Relaunching SC resumes capture.

## What's NOT tested by this checklist

- Multi-monitor with negative-origin monitors (covered by unit tests).
- Exclusive-fullscreen SC — explicitly unsupported; same constraint as the
  existing always-on-top overlay.
```

- [ ] **Step 2: Append DEVLOG entry**

Add to `DEVLOG.md` (top of file, following the existing chronological style):
```markdown
## 6.1.0 — Live window capture

- New `live_capture.py` module: probes the running starcitizen.exe window at
  ~30 Hz, runs OCR only on stable byte-hash changes within the calibrated
  region. Replaces the print-screen-to-folder hop for the common case.
- Folder-watch mode preserved behind a Scanner-module toggle (FOLDER / LIVE).
- New `window_finder.py` locates SC by process name with title fallback;
  returns the client-area rect for ROI capture.
- New window-relative scan region storage (`scan_region_window.json`);
  REGION module gains a "PICK FROM LIVE FRAME" calibration entry.
- `scanner.py` refactored: `scan_image` now delegates to a new
  `scan_pil_image` entry point that accepts an in-memory PIL Image — used
  by live mode to skip the file-write/-read round-trip.
- Added `mss`, `pywin32`, `psutil` runtime dependencies; updated
  PyInstaller spec for the bundle.
- Test suite: 24 pytest cases covering window enumeration, scanner
  refactor, region storage, stability tracker, geometry math, and the
  full LiveCapture loop with mocked window/mss/scanner.
```

- [ ] **Step 3: Commit**

```bash
git add docs/manual-test-live-capture.md DEVLOG.md
git commit -m "docs: manual test checklist and DEVLOG entry for live capture"
```

---

## Self-review notes

After all tasks complete, run the full suite one more time:
```bash
pytest
```
Expected: all green.

Also verify the spec coverage:
- ✅ `window_finder.py` (Task 2) — covers Components → window_finder
- ✅ `scan_pil_image` (Task 3) — covers Components → Scanner refactor
- ✅ Window-relative storage (Task 4) — covers Persisted state row 3
- ✅ `StabilityTracker` (Task 5) — covers Change-detection algorithms → Layer 2
- ✅ `compute_abs_capture_rect` (Task 6) — covers Components → live_capture geometry
- ✅ `LiveCapture` loop (Task 7) — covers Data flow probe tick + error-handling rows for grab failures and never-stabilizes
- ✅ `RegionSelector.open(image=..., save_as_window_relative=True)` (Task 8) — covers Region calibration changes
- ✅ Bridge methods (Task 9) — covers Bridge additions + Mode switch flow
- ✅ UI (Task 10) — covers UI additions
- ✅ PyInstaller spec (Task 11) — covers Error handling → PyInstaller bundling
- ✅ Manual checklist (Task 12) — covers Testing → Manual / integration

Spec sections explicitly not implemented (out-of-scope per spec):
- Replacing EasyOCR with a faster engine
- Windows.Graphics.Capture (WGC) path
- GPU EasyOCR mode toggle
- Automated win32 / mss tests
