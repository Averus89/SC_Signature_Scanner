# WGC Capture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `mss`-based desktop screen-scraping with Windows.Graphics.Capture via the `windows-capture` 2.0.0 Python library, so live mode reads SC's swap-chain content directly regardless of Z-order. Drop the `WindowFromPoint` occlusion check added in PR #5 — it's obsolete and currently produces false negatives from transparent overlays.

**Architecture:** A new `wgc_capture.py` wraps a `windows-capture` session; it runs on a background callback thread and posts the most recent frame into a `(bytes, w, h)` slot under a lock. The existing `LiveCapture` tick loop reads that slot at `live_probe_hz`, crops the ROI in CPU with a pure `_crop_bgra` helper, and feeds the OCR pipeline unchanged. `bridge.calibrate_region_live` switches from a one-shot `mss.grab` to a short-lived WGC session that waits for the first frame.

**Tech Stack:** Python 3.10+, `windows-capture` 2.0.0 (Rust/PyO3 wrapper around WGC + D3D11 readback), `winrt-*` transitive deps, existing `EasyOCR` / `cv2` / `Pillow` / `pywebview` / React stack.

**Spec:** [`docs/superpowers/specs/2026-05-27-wgc-capture-design.md`](../specs/2026-05-27-wgc-capture-design.md)

**Dependencies between tasks:** Tasks 1, 2, and 3 are independent and can run in any order. Task 4 (`LiveCapture` refactor) depends on Tasks 1 (windows-capture installed) and 3 (WGCSession exists). Task 5 (bridge `calibrate_region_live`) depends on Task 3. Tasks 6 (UI), 7 (PyInstaller spec), and 8 (manual checklist + DEVLOG) stand alone.

---

## File structure

**Create:**
- `wgc_capture.py` — `WGCError` exception, `WGCSession` class, `_default_wgc_session_factory`
- `tests/test_wgc_session.py` — 5 unit tests over a fake `windows_capture.WindowsCapture`
- `tests/test_wgc_crop.py` — 4 unit tests for the `_crop_bgra` helper

**Modify:**
- `live_capture.py` — swap `mss_factory` for `wgc_session_factory`, drop `_window_from_point`, drop `idle_occluded` status; rewrite `tick()` to read the frame slot; add `_crop_bgra` helper
- `tests/test_live_capture_loop.py` — replace `FakeMss` with `FakeWGCSession`; delete 2 occlusion tests; add 3 new tests
- `bridge.py` — replace mss-based `calibrate_region_live` with a one-shot WGC session
- `ui/main/scanner-panel.jsx` — drop the `'idle_occluded' ? 'SC OCCLUDED — FOCUS GAME' :` branch
- `ui/main/index.html` — cache-buster `?v=44 → ?v=45`
- `requirements.txt` — `-mss` `+windows-capture>=2.0.0`
- `SC_Signature_Scanner.spec` — drop mss hidden imports, add windows-capture + winrt
- `docs/manual-test-live-capture.md` — new occlusion-immune scenarios; remove "SC OCCLUDED" scenario
- `DEVLOG.md` — new v6.2.0 entry

---

## Task 1: Add `windows-capture` dependency

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add the dep**

Find the existing `# ===== Live window capture (v6.1+) =====` section in `requirements.txt`. Replace the `mss>=9.0.0` line with `windows-capture>=2.0.0`:

```
# ===== Live window capture (v6.1+) =====
windows-capture>=2.0.0
pywin32>=306
psutil>=5.9.0
```

- [ ] **Step 2: Install locally**

```bash
python -m pip install windows-capture>=2.0.0
```

Expected: installs `windows-capture` and its transitive `winrt-*` packages.

- [ ] **Step 3: Smoke-import**

```bash
python -c "from windows_capture import WindowsCapture; print('ok')"
```

Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "build: replace mss with windows-capture for WGC migration"
```

---

## Task 2: Pure `_crop_bgra` helper + tests

**Files:**
- Modify: `live_capture.py` (append the helper at module level, near `compute_abs_capture_rect`)
- Create: `tests/test_wgc_crop.py`

This pure-function helper crops a BGRA byte buffer to a sub-rectangle. Used by `LiveCapture.tick` after WGC delivers a full-window frame.

- [ ] **Step 1: Write failing tests**

Create `tests/test_wgc_crop.py`:

```python
"""_crop_bgra — pure helper that crops a BGRA byte buffer to a sub-rect."""
from live_capture import _crop_bgra


def test_crop_returns_correct_subrect_bytes():
    """Synthetic 4x3 BGRA frame, crop the middle 2x2."""
    # Each pixel is 4 bytes; we encode column index as the B byte so we can
    # spot-check column ordering.
    def row(start_col: int, w: int) -> bytes:
        return b"".join(bytes([c, 0, 0, 255]) for c in range(start_col, start_col + w))

    frame = row(0, 4) + row(0, 4) + row(0, 4)  # 4x3
    roi, w, h = _crop_bgra(frame, 4, 3, (1, 1, 3, 3))
    assert (w, h) == (2, 2)
    # Two rows of two pixels each, columns 1 and 2.
    expected = bytes([1, 0, 0, 255, 2, 0, 0, 255, 1, 0, 0, 255, 2, 0, 0, 255])
    assert roi == expected


def test_crop_handles_full_frame():
    """Region equal to full frame returns the whole buffer unchanged."""
    frame = bytes(range(4 * 2 * 4))  # 4x2 = 32 bytes
    roi, w, h = _crop_bgra(frame, 4, 2, (0, 0, 4, 2))
    assert (w, h) == (4, 2)
    assert roi == frame


def test_crop_first_pixel_of_row_is_top_left():
    """Verify no row flip and no column swap."""
    # 2x2 frame, top-left is byte 0, top-right is byte 4, etc.
    frame = bytes(range(2 * 2 * 4))
    roi, _, _ = _crop_bgra(frame, 2, 2, (0, 0, 1, 1))
    # Top-left pixel is bytes 0..3.
    assert roi == bytes([0, 1, 2, 3])


def test_crop_size_matches_region():
    """len(output) == (x2-x1) * (y2-y1) * 4."""
    frame = bytes(100 * 50 * 4)  # 20,000 bytes
    roi, w, h = _crop_bgra(frame, 100, 50, (10, 5, 60, 25))
    assert (w, h) == (50, 20)
    assert len(roi) == 50 * 20 * 4
```

- [ ] **Step 2: Run, expect failure**

```bash
pytest tests/test_wgc_crop.py -v
```

Expected: FAIL — `ImportError: cannot import name '_crop_bgra' from 'live_capture'`.

- [ ] **Step 3: Add `_crop_bgra` to `live_capture.py`**

Find the existing `compute_abs_capture_rect` function (around `live_capture.py:94`). After its closing line and before the `Status = Literal[...]` line, insert:

```python
def _crop_bgra(
    buf: bytes,
    frame_w: int,
    frame_h: int,
    region: tuple[int, int, int, int],
) -> tuple[bytes, int, int]:
    """Crop a BGRA pixel buffer to (x1, y1, x2, y2). Returns (roi_bytes, w, h).

    Pure-Python row slicing. Caller must ensure the region is already clamped
    inside (0, 0, frame_w, frame_h) — compute_abs_capture_rect handles this.
    """
    x1, y1, x2, y2 = region
    stride = frame_w * 4
    rows = [buf[y * stride + x1 * 4 : y * stride + x2 * 4] for y in range(y1, y2)]
    return (b"".join(rows), x2 - x1, y2 - y1)
```

- [ ] **Step 4: Run, expect pass**

```bash
pytest tests/test_wgc_crop.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Full suite**

```bash
pytest
```

Expected: 41 passed (37 current + 4 new).

- [ ] **Step 6: Commit**

```bash
git add live_capture.py tests/test_wgc_crop.py
git commit -m "feat: _crop_bgra helper for cropping a full-window BGRA buffer to ROI"
```

---

## Task 3: `WGCSession` + `WGCError` in `wgc_capture.py`

**Files:**
- Create: `wgc_capture.py`
- Create: `tests/test_wgc_session.py`

Wraps a `windows-capture` session. Knows nothing about ROIs, hashes, or OCR — just delivers full-window frames to a user-supplied callback.

- [ ] **Step 1: Write failing tests**

Create `tests/test_wgc_session.py`:

```python
"""WGCSession — wraps a windows-capture session, delivers frames via callback."""
from unittest.mock import MagicMock

import pytest

from wgc_capture import WGCSession, WGCError


class FakeCaptureLib:
    """Stand-in for windows_capture.WindowsCapture.

    Mirrors the real library's API: a single `@event` decorator that routes
    by function name to either `on_frame_arrived` or `on_closed`.
    """

    is_supported_return = True

    def __init__(self, *, window_name=None, cursor_capture=None):
        self.window_name = window_name
        self.cursor_capture = cursor_capture
        self.frame_arrived_handler = None
        self.closed_handler = None
        self.start_called = False
        self.stop_called = 0

    def is_supported(self) -> bool:
        return type(self).is_supported_return

    def event(self, fn):
        """Decorator: route by function name (mirrors windows-capture's API)."""
        name = fn.__name__
        if name == "on_frame_arrived":
            self.frame_arrived_handler = fn
        elif name == "on_closed":
            self.closed_handler = fn
        return fn

    def start_free_threaded(self):
        self.start_called = True

    def stop(self):
        self.stop_called += 1


def _make_session(hwnd: int = 42) -> tuple[WGCSession, FakeCaptureLib, MagicMock]:
    """Create a WGCSession backed by a FakeCaptureLib. Returns
    (session, fake_lib_instance, on_frame_callback)."""
    on_frame = MagicMock()
    fake_lib_holder = {}

    def lib_factory(hwnd_in: int):
        lib = FakeCaptureLib()
        fake_lib_holder["lib"] = lib
        return lib

    session = WGCSession(hwnd, on_frame, capture_lib_factory=lib_factory)
    # start() to actually instantiate the fake
    return session, fake_lib_holder, on_frame


def test_start_raises_when_wgc_unsupported():
    """is_supported() False → start() raises WGCError, no session created."""
    session, holder, _ = _make_session()
    FakeCaptureLib.is_supported_return = False
    try:
        with pytest.raises(WGCError):
            session.start()
    finally:
        FakeCaptureLib.is_supported_return = True


def test_start_registers_frame_callback_and_calls_start_free_threaded():
    """After start(), the fake's frame handler is set and start_free_threaded was invoked."""
    session, holder, _ = _make_session()
    session.start()
    lib = holder["lib"]
    assert lib.frame_arrived_handler is not None
    assert lib.start_called is True


def test_frame_callback_invokes_on_frame_with_bgra_bytes():
    """When the fake delivers a frame, on_frame(raw, w, h) is called with the right shape."""
    session, holder, on_frame = _make_session()
    session.start()
    lib = holder["lib"]

    # Simulate a frame: the library passes a frame object with .frame_buffer (bytes)
    # and .width / .height attributes (or .shape — depends on lib API). Our
    # WGCSession adapter is responsible for converting to (bytes, w, h).
    fake_frame = MagicMock()
    fake_frame.frame_buffer = b"\xAA\xBB\xCC\xFF" * (4 * 3)  # 4x3 BGRA = 48 bytes
    fake_frame.width = 4
    fake_frame.height = 3
    fake_capture_control = MagicMock()
    lib.frame_arrived_handler(fake_frame, fake_capture_control)

    on_frame.assert_called_once()
    raw, w, h = on_frame.call_args.args
    assert (w, h) == (4, 3)
    assert len(raw) == 4 * 3 * 4


def test_stop_is_idempotent():
    """Calling stop twice doesn't raise. Calling stop without start doesn't raise."""
    session, holder, _ = _make_session()
    session.stop()  # before start — safe
    session.start()
    session.stop()
    session.stop()  # double stop — safe
    lib = holder["lib"]
    assert lib.stop_called >= 1


def test_on_closed_marks_session_inactive():
    """When the fake fires on_closed, is_active flips to False."""
    session, holder, _ = _make_session()
    session.start()
    assert session.is_active is True
    lib = holder["lib"]
    lib.closed_handler()
    assert session.is_active is False
```

- [ ] **Step 2: Run, expect failure**

```bash
pytest tests/test_wgc_session.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'wgc_capture'`.

- [ ] **Step 3: Create `wgc_capture.py`**

```python
"""Windows Graphics Capture session wrapper.

Encapsulates the windows-capture library so the rest of the app speaks a
small, testable interface: hwnd in, BGRA frame bytes out via callback.

The real library's API uses decorators to register callbacks; this wrapper
flattens that into a constructor parameter and exposes start/stop. A
`capture_lib_factory` constructor argument allows tests to substitute a
fake library object without touching the real WGC stack.
"""
from __future__ import annotations

import threading
from typing import Any, Callable, Optional


class WGCError(Exception):
    """Raised when Windows Graphics Capture is unsupported or a session
    fails to start."""


def _default_capture_lib_factory(hwnd: int) -> Any:
    """Construct the real windows-capture session bound to `hwnd`."""
    import win32gui
    from windows_capture import WindowsCapture
    title = win32gui.GetWindowText(hwnd) or ""
    # windows-capture 2.x binds by window title rather than hwnd directly.
    # The title we pass must match a current top-level window's title.
    return WindowsCapture(window_name=title, cursor_capture=False)


class WGCSession:
    """A WGC capture session bound to a single hwnd.

    Calls `on_frame(raw_bgra_bytes, w, h)` on the capture thread whenever
    the source produces a new frame. Owns no policy — drop / aggregate /
    throttle decisions live in the caller (LiveCapture).
    """

    def __init__(
        self,
        hwnd: int,
        on_frame: Callable[[bytes, int, int], None],
        *,
        capture_lib_factory: Callable[[int], Any] = _default_capture_lib_factory,
    ) -> None:
        self.hwnd = hwnd
        self._on_frame_user = on_frame
        self._capture_lib_factory = capture_lib_factory
        self._lib: Optional[Any] = None
        self._is_active = False
        self._lock = threading.Lock()

    @property
    def is_active(self) -> bool:
        return self._is_active

    def start(self) -> None:
        """Create the underlying capture, register callbacks, start it.

        Raises WGCError if WGC is unsupported on this system or the
        underlying start call throws.
        """
        with self._lock:
            if self._is_active:
                return
            lib = self._capture_lib_factory(self.hwnd)

            if hasattr(lib, "is_supported") and not lib.is_supported():
                raise WGCError(
                    "Windows Graphics Capture is not supported on this system"
                )

            # windows-capture uses a single @event decorator that routes by
            # function name — these names are part of the contract.
            @lib.event
            def on_frame_arrived(frame: Any, capture_control: Any) -> None:
                try:
                    raw = bytes(frame.frame_buffer)
                    w = int(frame.width)
                    h = int(frame.height)
                except Exception:
                    return
                self._on_frame_user(raw, w, h)

            @lib.event
            def on_closed() -> None:
                with self._lock:
                    self._is_active = False

            try:
                lib.start_free_threaded()
            except Exception as e:
                raise WGCError(f"WGC session failed to start: {e}") from e

            self._lib = lib
            self._is_active = True

    def stop(self) -> None:
        """Stop the capture. Idempotent and safe from any thread."""
        with self._lock:
            lib = self._lib
            self._is_active = False
            self._lib = None
        if lib is not None:
            try:
                lib.stop()
            except Exception:
                # Best-effort cleanup; the library may already be torn down.
                pass


def _default_wgc_session_factory(
    hwnd: int,
    on_frame: Callable[[bytes, int, int], None],
) -> WGCSession:
    """Construct a real WGCSession. Replaceable via dependency injection
    in LiveCapture for unit tests."""
    return WGCSession(hwnd, on_frame)
```

- [ ] **Step 4: Run, expect pass**

```bash
pytest tests/test_wgc_session.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Full suite**

```bash
pytest
```

Expected: 46 passed (41 + 5 new).

- [ ] **Step 6: Commit**

```bash
git add wgc_capture.py tests/test_wgc_session.py
git commit -m "feat: WGCSession wraps windows-capture for SC swap-chain capture"
```

---

## Task 4: Refactor `LiveCapture` to use `WGCSession`

**Files:**
- Modify: `live_capture.py:126,165-330` (Status literal, factories, class body)
- Modify: `tests/test_live_capture_loop.py` (rewrite scaffolding, delete 2 tests, add 3 new)

This is the biggest single task. Replaces `mss_factory` with `wgc_session_factory`, removes `_window_from_point` + `idle_occluded`, rewrites `tick()` to read the frame slot.

### 4a. Update `Status` literal and add `_default_wgc_session_factory` re-export

- [ ] **Step 1: Drop `idle_occluded` from the Status literal**

In `live_capture.py`, find the line (around line 126):

```python
Status = Literal["stopped", "waiting", "idle_minimized", "idle_occluded", "running", "error"]
```

Replace with:

```python
Status = Literal["stopped", "waiting", "idle_minimized", "running", "error"]
```

- [ ] **Step 2: Delete `_default_mss_factory` and `_default_window_from_point`, add `_default_wgc_session_factory` re-export**

Find the existing factory functions (around lines 131–163 of `live_capture.py`). Delete `_default_mss_factory` and `_default_window_from_point` (and the `GA_ROOT = 2` constant and `win32gui` import inside `_default_window_from_point`). Keep `_default_find_sc_window` and `_default_load_window_region`.

Then add an alias for `_default_wgc_session_factory` from `wgc_capture.py`:

```python
def _default_wgc_session_factory(hwnd, on_frame):
    """Construct a real WGCSession bound to `hwnd` for `on_frame` callbacks."""
    from wgc_capture import WGCSession
    return WGCSession(hwnd, on_frame)
```

### 4b. Update `LiveCapture.__init__`

- [ ] **Step 3: Swap constructor parameters**

Find `LiveCapture.__init__` (around `live_capture.py:165`). Locate the parameter block:

```python
        mss_factory: Callable[[], Any] = _default_mss_factory,
        window_from_point: Callable[[tuple[int, int]], int] = _default_window_from_point,
        probe_hz: int = 30,
        stable_frames: int = 3,
        emit_empty: bool = False,
```

Replace with:

```python
        wgc_session_factory: Callable[[int, Callable[[bytes, int, int], None]], Any] = _default_wgc_session_factory,
        probe_hz: int = 30,
        stable_frames: int = 3,
        emit_empty: bool = False,
```

Then in the constructor body, find:

```python
        self._mss_factory = mss_factory
        self._window_from_point = window_from_point
        self._emit_empty = emit_empty
```

Replace with:

```python
        self._wgc_session_factory = wgc_session_factory
        self._emit_empty = emit_empty
```

Find the existing state-init block in `__init__`:

```python
        self._mss: Any = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
```

Replace with:

```python
        self._wgc: Optional[Any] = None
        self._wgc_hwnd: Optional[int] = None
        self._frame_lock = threading.Lock()
        self._latest_frame: Optional[tuple[bytes, int, int]] = None
        self._ticks_without_frame: int = 0
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
```

### 4c. Replace `_run` and `tick`

- [ ] **Step 4: Rewrite `_run`**

Find the existing `_run` method (around `live_capture.py:255`). Replace its body with:

```python
    def _run(self) -> None:
        """Tick loop main. Owns the WGC session lifecycle."""
        try:
            while not self._stop_event.is_set():
                start = time.monotonic()
                period = self.tick()
                elapsed = time.monotonic() - start
                remaining = max(0.0, period - elapsed)
                if self._stop_event.wait(remaining):
                    break
        finally:
            self._stop_wgc()
```

- [ ] **Step 5: Add private `_start_wgc` and `_stop_wgc` helpers**

Insert as methods on `LiveCapture` (between `_run` and `tick`):

```python
    def _start_wgc(self, hwnd: int) -> None:
        """Bind a fresh WGC session to `hwnd`. Raises WGCError on failure."""
        self._stop_wgc()
        with self._frame_lock:
            self._latest_frame = None
        self._ticks_without_frame = 0

        def on_frame(raw: bytes, w: int, h: int) -> None:
            with self._frame_lock:
                self._latest_frame = (raw, w, h)

        self._wgc = self._wgc_session_factory(hwnd, on_frame)
        self._wgc.start()
        self._wgc_hwnd = hwnd

    def _stop_wgc(self) -> None:
        """Tear down the active WGC session if any. Idempotent."""
        wgc = self._wgc
        self._wgc = None
        self._wgc_hwnd = None
        with self._frame_lock:
            self._latest_frame = None
        self._ticks_without_frame = 0
        if wgc is not None:
            try:
                wgc.stop()
            except Exception:
                pass
```

- [ ] **Step 6: Add module-level no-frame error threshold constant**

Near the top of `live_capture.py` (just after the imports, before `class StabilityTracker`), add:

```python
# Live capture thresholds.
_NO_FRAME_ERROR_THRESHOLD = 90  # ticks with no frame before flipping to error
                                 # — ~3 sec at the default 30 Hz probe rate.
```

- [ ] **Step 7: Rewrite `tick`**

Find the existing `tick` method (around `live_capture.py:265-330`). Replace the entire method body with:

```python
    def tick(self) -> float:
        """One probe iteration. Returns the sleep period until next tick."""
        try:
            info = self._find_sc_window()
        except Exception:
            info = None

        if info is None:
            self._stop_wgc()
            self._tracker.reset()
            self._status = "waiting"
            return self._idle_period

        if info.is_minimized:
            self._stop_wgc()
            self._status = "idle_minimized"
            return self._idle_period

        if info.hwnd != self._wgc_hwnd:
            try:
                self._start_wgc(info.hwnd)
            except WGCError as e:
                self._status = "error"
                if self._emit_empty:
                    self.emit({"error": f"WGC session failed: {e}"}, source="live")
                return self._idle_period
            self._tracker.reset()

        if self._wgc is None or not self._wgc.is_active:
            self._status = "error"
            return self._idle_period

        with self._frame_lock:
            frame = self._latest_frame

        if frame is None:
            self._ticks_without_frame += 1
            if self._ticks_without_frame >= _NO_FRAME_ERROR_THRESHOLD:
                self._status = "error"
                if self._emit_empty:
                    self.emit(
                        {"error": "WGC session running but no frames received"},
                        source="live",
                    )
                return self._idle_period
            self._status = "running"
            return self._tick_period

        self._ticks_without_frame = 0
        raw_bgra, frame_w, frame_h = frame

        abs_roi = compute_abs_capture_rect(
            (0, 0, frame_w, frame_h), self._region_window_rel
        )
        if abs_roi is None:
            self._status = "error"
            if self._emit_empty:
                self.emit(
                    {"error": "Live region out of bounds — recalibrate"},
                    source="live",
                )
            return self._idle_period

        left, top, roi_w, roi_h = abs_roi
        roi_bytes, _, _ = _crop_bgra(
            raw_bgra, frame_w, frame_h, (left, top, left + roi_w, top + roi_h)
        )

        digest = hashlib.blake2b(roi_bytes, digest_size=8).digest()
        decision = self._tracker.observe(digest)
        self._status = "running"

        if decision != "stable_change":
            return self._tick_period

        try:
            img = Image.frombytes("RGB", (roi_w, roi_h), roi_bytes, "raw", "BGRX")
            result = self.scanner.scan_pil_image(img, region=(0, 0, roi_w, roi_h))
        except Exception as e:
            if self._emit_empty:
                self.emit({"error": f"frame decode/OCR failed: {e}"}, source="live")
            return self._tick_period

        if result is None or result.get("error") or not result.get("matches"):
            self._tracker.empty_rearm()
            if self._emit_empty:
                self.emit(result or {"error": "No signature detected"}, source="live")
            return self._tick_period

        self.emit(result, source="live")
        return self._tick_period
```

- [ ] **Step 8: Add `from wgc_capture import WGCError` to imports at the top of `live_capture.py`**

Locate the imports block at the top. After `from typing import ...`, add:

```python
from wgc_capture import WGCError
```

If there's an existing `import mss` in `live_capture.py`, delete it.

- [ ] **Step 9: Rewrite the test scaffolding in `tests/test_live_capture_loop.py`**

Open `tests/test_live_capture_loop.py`. Locate the `FakeMss` and `FakeShot` classes near the top.

Replace them entirely with:

```python
class FakeWGCSession:
    """Stand-in for WGCSession. Tests call push_frame() to inject frames
    into the LiveCapture frame slot."""

    def __init__(self, hwnd: int, on_frame):
        self.hwnd = hwnd
        self._on_frame = on_frame
        self.is_active = False
        self.start_count = 0
        self.stop_count = 0

    def start(self) -> None:
        self.is_active = True
        self.start_count += 1

    def stop(self) -> None:
        self.is_active = False
        self.stop_count += 1

    def push_frame(self, raw: bytes, w: int, h: int) -> None:
        """Synchronously call the on_frame callback as if a real frame arrived."""
        self._on_frame(raw, w, h)
```

Then locate the `_make_live` helper. Replace it with:

```python
def _make_live(
    *,
    window: Optional[WindowInfo],
    region: Optional[tuple[int, int, int, int]] = (0, 0, 100, 30),
    scan_result: Optional[dict] = None,
    emit_empty: bool = False,
) -> tuple[LiveCapture, MagicMock, dict]:
    """Build a LiveCapture wired with a FakeWGCSession factory.

    Returns (live, emit_mock, sessions_dict). `sessions_dict` exposes the
    FakeWGCSession instances keyed by hwnd so tests can call push_frame().
    """
    finder = MagicMock(return_value=window)
    scanner = MagicMock()
    scanner.scan_pil_image.return_value = scan_result
    region_loader = MagicMock(return_value=region)
    emit = MagicMock()
    sessions: dict[int, FakeWGCSession] = {}

    def factory(hwnd: int, on_frame):
        session = FakeWGCSession(hwnd, on_frame)
        sessions[hwnd] = session
        return session

    live = LiveCapture(
        scanner=scanner,
        emit=emit,
        find_sc_window=finder,
        load_window_region=region_loader,
        wgc_session_factory=factory,
        probe_hz=30,
        stable_frames=2,
        emit_empty=emit_empty,
    )
    return live, emit, sessions
```

The tests currently using positional/keyword `mss_factory=...` calls need to be updated. Find all such occurrences in the file (search for `mss_factory=`) — replace each with the equivalent `wgc_session_factory=` pattern. Also drop the `window_from_point=lambda pt: 1` arguments wherever they appear (the parameter no longer exists).

For each remaining test that previously called `live.tick()` expecting an mss-driven capture:
- Before `live.tick()`, push a synthetic frame: `sessions[<hwnd>].push_frame(b"\x00" * (100 * 30 * 4), 100, 30)`.

The exact patch differs per test; the table below summarises:

| Test | Was | Becomes |
|---|---|---|
| `test_tick_with_visible_window_captures_and_runs_ocr_after_stable_frames` | `live.tick(); live.tick()` with 2 identical mss shots | `sessions[1].push_frame(bytes, 100, 30); live.tick();` (ongoing) then `live.tick();` (stable_change → emit). One push is enough — content hash is what matters, not how many bytes flow. |
| `test_empty_ocr_result_re_arms_so_same_hash_fires_again` | 3 mss-shot sequences (sig, blank, sig) | 3 push_frame calls with sig_bytes, blank_bytes, sig_bytes between the tick pairs. |
| `test_window_move_invalidates_hash_state` | Same content, side_effect changes window | Same logic but using push_frame; verify after window change a NEW FakeWGCSession is created (i.e. `len(sessions) == 2`). |

Delete these two tests entirely:
- `test_tick_skips_capture_when_sc_is_occluded_by_another_window`
- `test_tick_proceeds_when_sc_is_topmost_at_capture_point`

Add three new tests at the end of the file:

```python
def test_tick_with_no_frame_yet_remains_running():
    """Session active, but no frame delivered yet — status stays 'running'
    (warming up) and tick returns the normal tick period, no OCR."""
    win = WindowInfo(hwnd=1, client_rect=(0, 0, 1920, 1080), is_minimized=False, is_foreground=False)
    live, emit, sessions = _make_live(window=win)
    live.start_for_tests()
    # Run tick without push_frame — frame slot is None.
    live.tick()
    assert live.status == "running"
    emit.assert_not_called()
    live.scanner.scan_pil_image.assert_not_called()


def test_tick_warming_up_eventually_errors_if_no_frames_arrive():
    """After _NO_FRAME_ERROR_THRESHOLD ticks of no frame, status becomes 'error'."""
    from live_capture import _NO_FRAME_ERROR_THRESHOLD
    win = WindowInfo(hwnd=1, client_rect=(0, 0, 1920, 1080), is_minimized=False, is_foreground=False)
    live, emit, sessions = _make_live(window=win)
    live.start_for_tests()
    for _ in range(_NO_FRAME_ERROR_THRESHOLD):
        live.tick()
    assert live.status == "error"


def test_roi_clamp_to_smaller_frame_yields_degenerate_error():
    """Live region's bottom-right falls outside the frame size → status 'error'."""
    win = WindowInfo(hwnd=1, client_rect=(0, 0, 5120, 1440), is_minimized=False, is_foreground=False)
    # Region (4000, 1000, 4100, 1050) — but we'll push a 100x50 frame
    # whose origin is the SC client. Region falls entirely outside.
    live, emit, sessions = _make_live(
        window=win,
        region=(4000, 1000, 4100, 1050),
    )
    live.start_for_tests()
    sessions[1].push_frame(b"\x00" * (100 * 50 * 4), 100, 50)
    live.tick()
    assert live.status == "error"
```

- [ ] **Step 10: Run the live_capture loop tests**

```bash
pytest tests/test_live_capture_loop.py -v
```

Expected: **13 passed**. Math: master has 12 loop tests (10 original + 2 added in PR #5); delete the 2 PR #5 tests → 10 surviving; add 3 new tests → 13.

- [ ] **Step 11: Run the full test suite**

```bash
pytest
```

Expected: **47 passed**. Per-file breakdown:
- `test_smoke.py`: 1
- `test_window_finder.py`: 5
- `test_scanner_pil.py`: 3
- `test_region_selector_storage.py`: 4
- `test_live_capture_stability.py`: 7
- `test_live_capture_geometry.py`: 5
- `test_live_capture_loop.py`: 13
- `test_wgc_session.py`: 5
- `test_wgc_crop.py`: 4
- Total: 1 + 5 + 3 + 4 + 7 + 5 + 13 + 5 + 4 = **47**.

If the total isn't 47, list which file's count is off and fix the corresponding test before committing.

- [ ] **Step 12: Commit**

```bash
git add live_capture.py tests/test_live_capture_loop.py
git commit -m "refactor: LiveCapture uses WGCSession + drops WindowFromPoint occlusion check"
```

---

## Task 5: Bridge `calibrate_region_live` uses WGC

**Files:**
- Modify: `bridge.py:127-146` (the `calibrate_region_live` method)

- [ ] **Step 1: Read the current method**

Find `calibrate_region_live` in `bridge.py` (around line 127). Note its current shape — it calls `find_sc_window()`, then uses `mss.mss()` to grab the client area, then passes the image to `RegionSelector.open`.

- [ ] **Step 2: Replace the body**

Replace the entire `calibrate_region_live` method with:

```python
    def calibrate_region_live(self) -> dict[str, Any]:
        """One-shot: start a brief WGC session against the SC window, capture
        the first delivered frame, hand it to the region picker, persist the
        rect as window-relative."""
        info = find_sc_window()
        if info is None:
            return {"ok": False, "error": "Star Citizen not running"}

        import threading
        from wgc_capture import WGCSession, WGCError

        frame_ready = threading.Event()
        captured: list[tuple[bytes, int, int]] = []

        def cb(raw: bytes, w: int, h: int) -> None:
            if captured:
                return
            captured.append((raw, w, h))
            frame_ready.set()

        session = WGCSession(info.hwnd, on_frame=cb)
        try:
            session.start()
        except WGCError as e:
            return {"ok": False, "error": str(e)}

        ok = frame_ready.wait(timeout=5.0)
        session.stop()

        if not ok or not captured:
            return {"ok": False, "error": "WGC didn't deliver a frame in 5 seconds"}

        raw, w, h = captured[0]
        from PIL import Image as _Image
        img = _Image.frombytes("RGB", (w, h), raw, "raw", "BGRX")

        import region_selector
        selector = region_selector.RegionSelector(parent=None)
        selector.open(image=img, save_as_window_relative=True)
        return {"ok": True}
```

- [ ] **Step 3: Remove the now-unused `import mss` from `bridge.py`**

If `bridge.py` has `import mss` at the top, delete that line. (Check around line 26.)

- [ ] **Step 4: Verify the bridge module imports**

```bash
python -c "import bridge; print('ok')"
```

Expected: `ok`.

- [ ] **Step 5: Full suite (regression check)**

```bash
pytest
```

Expected: still 47 passed.

- [ ] **Step 6: Commit**

```bash
git add bridge.py
git commit -m "feat(bridge): calibrate_region_live uses one-shot WGC instead of mss"
```

---

## Task 6: UI — drop `idle_occluded` label + cache-buster bump

**Files:**
- Modify: `ui/main/scanner-panel.jsx`
- Modify: `ui/main/index.html`

- [ ] **Step 1: Remove the `idle_occluded` branch from the status label**

Find the status-label ternary in `ui/main/scanner-panel.jsx` (search for `liveStatus.captureStatus === 'idle_occluded'`). Delete this line entirely:

```jsx
                     liveStatus.captureStatus === 'idle_occluded' ? 'SC OCCLUDED — FOCUS GAME' :
```

The surrounding branches stay; the line just gets dropped.

- [ ] **Step 2: Bump cache-buster**

In `ui/main/index.html`, replace every `?v=44` with `?v=45`. Use search/replace on the file:

```bash
sed -i 's/?v=44/?v=45/g' ui/main/index.html
```

(Or use the editor directly; six occurrences.)

- [ ] **Step 3: Smoke check**

```bash
python -c "import bridge; print('ok')"
pytest
```

Expected: bridge OK, tests still 47 passed.

- [ ] **Step 4: Commit**

```bash
git add ui/main/scanner-panel.jsx ui/main/index.html
git commit -m "ui: drop SC OCCLUDED status label + cache-buster v=44 → v=45"
```

---

## Task 7: PyInstaller spec — drop mss, add windows-capture + winrt

**Files:**
- Modify: `SC_Signature_Scanner.spec`

- [ ] **Step 1: Drop mss from `hiddenimports`**

Find the live-capture additions in the `hiddenimports` list (added in PR #2). Currently:

```python
    # Live window capture (v6.1+)
    'mss',
    'mss.windows',
    'win32gui',
    'win32process',
    'win32con',
    'psutil',
```

Replace the `'mss'` and `'mss.windows'` lines with:

```python
    # Live window capture (v6.2+ — WGC via windows-capture)
    'windows_capture',
    'win32gui',
    'win32process',
    'win32con',
    'psutil',
```

- [ ] **Step 2: Update `collect_submodules` calls**

Find the existing block (added in PR #2):

```python
hiddenimports += collect_submodules('mss')
hiddenimports += collect_submodules('win32')
hiddenimports += collect_submodules('psutil')
```

Replace with:

```python
hiddenimports += collect_submodules('windows_capture')
hiddenimports += collect_submodules('winrt')
hiddenimports += collect_submodules('win32')
hiddenimports += collect_submodules('psutil')
```

- [ ] **Step 3: Add `collect_dynamic_libs` for the windows-capture native wheel**

In the spec file, near where `collect_data_files` is imported, also import `collect_dynamic_libs`:

```python
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_dynamic_libs
```

After the existing `datas += torch_datas` lines, append:

```python
# windows-capture ships a native .pyd from its Rust/PyO3 wheel.
binaries_wgc = collect_dynamic_libs('windows_capture')
```

Then find the `Analysis(...)` call and locate its `binaries=` keyword. Change from `binaries=[]` to:

```python
    binaries=binaries_wgc,
```

- [ ] **Step 4: Verify the spec parses**

```bash
python -c "exec(open('SC_Signature_Scanner.spec').read())" 2>&1 | head -10
```

Expected: no `SyntaxError`. A `NameError: name 'Analysis' is not defined` is acceptable (PyInstaller injects those at build time).

- [ ] **Step 5: Smoke check**

```bash
pytest
```

Expected: 47 passed.

- [ ] **Step 6: Commit**

```bash
git add SC_Signature_Scanner.spec
git commit -m "build: bundle windows-capture (drop mss) for WGC migration"
```

---

## Task 8: Manual checklist update + DEVLOG entry

**Files:**
- Modify: `docs/manual-test-live-capture.md`
- Modify: `DEVLOG.md`

- [ ] **Step 1: Update the manual checklist**

In `docs/manual-test-live-capture.md`, replace the existing "Scenarios" section's content with:

```markdown
## Scenarios

- [ ] **Cold start, SC closed.** ENGAGE in LIVE mode → status pill reads
  "WAITING FOR SC". Launch SC → status flips to "LIVE · 30 Hz" within
  ~1 second of the game window appearing.

- [ ] **Detection latency.** With a known mineable in view, overlay fires
  within ~150 ms of the signature appearing on the HUD.

- [ ] **No re-fire on static content.** Stand on the same rock 10 seconds →
  overlay fires exactly once. Detection log shows one entry.

- [ ] **Look-away re-arm.** Look away (signature gone) → look back at the
  same rock → overlay fires again. Both detections in the log.

- [ ] **SC behind opaque windows.** Open Windows Settings (or any other
  opaque window) over the SC HUD area. → Detections fire normally. (WGC
  captures SC's swap-chain content regardless of Z-order.)

- [ ] **Transparent overlay active.** Enable NVIDIA / Steam / Discord
  overlay. → Detections fire normally.

- [ ] **Live mode while scanner is foreground.** Click into the Scanner UI
  itself while LIVE is engaged. → Detections continue to fire.

- [ ] **Window-move robustness.** Drag the SC window across the desktop
  mid-session. → First new stable signature after the move fires correctly.

- [ ] **Minimize idle.** Minimize SC → status pill flips to
  "IDLE (MINIMIZED)"; CPU usage drops. Restore → capture resumes.

- [ ] **Region out-of-bounds.** Resize SC smaller than the calibrated
  region. → Status reads "ERROR" with an "out of bounds" message.
  Re-enlarging resumes without re-engaging.

- [ ] **Mid-session mode switch.** While LIVE is running, switch the
  toggle to FOLDER. → Live thread stops cleanly, folder watcher starts.

- [ ] **SC closes mid-session.** Close SC. → Status returns to "WAITING
  FOR SC"; no errors logged. Relaunching SC resumes capture.

- [ ] **WGC unsupported (rare).** On a system without WGC support (very
  old Windows 10 build, exotic graphics driver), ENGAGE in LIVE mode
  surfaces a clear error: "Windows Graphics Capture is not supported on
  this system."
```

- [ ] **Step 2: Append v6.2.0 entry to DEVLOG.md**

In `DEVLOG.md`, find the `## Changelog` heading (around line 50). Insert immediately after that line (and before the most recent entry):

```markdown
### 2026-05-27 — v6.2.0: WGC capture (replaces mss desktop-scrape)

Branch `feat/wgc-capture` (or similar). Replaces `mss`-based desktop screen-scraping with Windows.Graphics.Capture via the `windows-capture` 2.0.0 Python library. WGC captures SC's swap-chain content directly regardless of Z-order, fixing the field bug where live mode returned the topmost window's pixels (Windows Settings UI, Explorer thumbnails) instead of SC's HUD.

**1. Capture backend.** New `wgc_capture.py` wraps a `windows-capture` session. Runs WGC on the library's callback thread; pushes the most recent frame into a single-slot `(bytes, w, h)` storage under a lock. The existing `LiveCapture` tick loop reads that slot at `live_probe_hz`. Drop-newest semantics — frames between ticks are discarded naturally.

**2. CPU-side ROI cropping.** New `_crop_bgra` pure helper crops a full-window BGRA buffer to the calibrated window-relative region. Cropping happens after readback for simplicity; ~20 KB of bytes per OCR-eligible frame.

**3. Occlusion check removed.** PR #5's `WindowFromPoint` check + `idle_occluded` Status are deleted. WGC makes them obsolete; they were producing false negatives from transparent always-on-top overlays (NVIDIA, Steam, Discord, our own overlay window).

**4. Calibration also moved to WGC.** `bridge.calibrate_region_live` replaces its `mss.mss().grab(client_rect)` one-shot with a short-lived WGC session that waits for the first frame (5-second timeout). Works under occlusion the same way the live loop does.

**Files added:**
- `wgc_capture.py` — `WGCSession`, `WGCError`, factory.
- `tests/test_wgc_session.py` — 5 unit tests over a fake `windows_capture.WindowsCapture`.
- `tests/test_wgc_crop.py` — 4 unit tests for `_crop_bgra`.

**Files modified:**
- `live_capture.py` — `mss_factory` / `window_from_point` → `wgc_session_factory`; tick rewrite; `idle_occluded` removed from `Status`.
- `tests/test_live_capture_loop.py` — `FakeMss` → `FakeWGCSession`; 2 occlusion tests deleted; 3 new tests (warming up, warming-up-errors, ROI-clamp-degenerate).
- `bridge.py` — `calibrate_region_live` rewrite.
- `ui/main/scanner-panel.jsx` — drop "SC OCCLUDED — FOCUS GAME" label.
- `ui/main/index.html` — cache-buster `v=44 → v=45`.
- `requirements.txt` — `-mss` `+windows-capture>=2.0.0`.
- `SC_Signature_Scanner.spec` — hidden imports + collect_submodules + collect_dynamic_libs for windows-capture and winrt.

**Test suite:** 47 pytest cases (37 v6.1.0 baseline − 2 deleted occlusion tests + 5 WGC session + 4 crop + 3 new live-capture cases). Manual verification per `docs/manual-test-live-capture.md`.

**Out of scope (future):**
- GPU-side ROI cropping via D3D11 `CopySubresourceRegion` (perf optimization if CPU usage is high).
- mss-as-fallback if WGC fails (not currently observed).
- Per-window cursor inclusion toggle.

**Version:** `6.1.0` → `6.2.0`.
```

- [ ] **Step 3: Commit**

```bash
git add docs/manual-test-live-capture.md DEVLOG.md
git commit -m "docs: manual test checklist + DEVLOG entry for WGC migration"
```

---

## Self-review notes

After all tasks complete, run the full suite one more time:

```bash
pytest
```

Expected: 47 passed.

Then verify spec coverage:

- ✅ `WGCSession` + `WGCError` (Task 3) — covers Components → `wgc_capture.py`
- ✅ `_crop_bgra` (Task 2) — covers Components → `_crop_bgra` helper
- ✅ `LiveCapture` refactor (Task 4) — covers Components → `LiveCapture` refactor + Data flow probe tick + removal of `idle_occluded`
- ✅ Bridge calibrate_region_live (Task 5) — covers Components → Bridge changes + Calibration flow
- ✅ UI updates (Task 6) — covers Components → UI section
- ✅ requirements + PyInstaller (Tasks 1, 7) — covers PyInstaller bundling
- ✅ Manual checklist + DEVLOG (Task 8) — covers Testing → Manual / integration + release notes

Spec items explicitly NOT implemented (deferred):
- GPU-side ROI cropping via D3D11.
- mss-as-fallback behavior.
- Per-window cursor toggle UI.
