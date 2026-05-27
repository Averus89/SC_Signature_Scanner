"""Live signature scanning from the running Star Citizen window.

Three units, each in this file:
  - StabilityTracker — pure-logic gate (this task)
  - compute_abs_capture_rect — pure geometry helper (next task)
  - LiveCapture — capture loop / thread / orchestration (next task)
"""
from __future__ import annotations

import hashlib
import threading
import time
from typing import Any, Callable, Literal, Optional

from PIL import Image

from wgc_capture import WGCError


Decision = Literal["no_change", "ongoing", "stable_change"]

# Live capture thresholds.
# Number of ticks with no frame before flipping to error status —
# ~3 sec at the default 30 Hz probe rate.
_NO_FRAME_ERROR_THRESHOLD = 90


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
        """Observe a new digest and return the stability decision.

        Args:
            digest: The content hash (e.g., MD5 of the captured region).

        Returns:
            - "ongoing" if the hash is new or hasn't stabilized yet.
            - "stable_change" if the hash has stabilized and differs from
              the last emitted hash.
            - "no_change" if the hash is stable and matches the last emitted one.
        """
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
        self._seen_count = 0
        self._last_seen = None

    def reset(self) -> None:
        """Drop all state — used when the window moves and the capture rect changes."""
        self._last_seen = None
        self._seen_count = 0
        self._last_emitted = None


MIN_ROI_W = 10
MIN_ROI_H = 5


def compute_abs_capture_rect(
    client_rect: tuple[int, int, int, int],
    region_window_rel: tuple[int, int, int, int],
) -> Optional[tuple[int, int, int, int]]:
    """Clamp a window-relative ROI to a client rectangle.

    Args:
        client_rect: (x, y, w, h) — the SC client area. In the WGC path
            this is (0, 0, frame_w, frame_h) because the captured frame's
            origin IS the client area's top-left.
        region_window_rel: (x1, y1, x2, y2) — the calibrated ROI in
            window-relative coordinates.

    Returns:
        (left, top, width, height) of the clamped ROI for downstream
        cropping, or None if the result is degenerate (smaller than
        MIN_ROI_W × MIN_ROI_H).
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


Status = Literal["stopped", "waiting", "idle_minimized", "running", "error"]


# These imports stay lazy so the unit tests don't need win32 installed
# to exercise the pure logic.
def _default_find_sc_window():
    from window_finder import find_sc_window
    return find_sc_window()


def _default_load_window_region():
    import region_selector
    return region_selector.load_window_region()


def _default_wgc_session_factory(hwnd, on_frame):
    """Construct a real WGCSession bound to `hwnd` for `on_frame` callbacks."""
    from wgc_capture import WGCSession
    return WGCSession(hwnd, on_frame)


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
        wgc_session_factory: Callable[[int, Callable[[bytes, int, int], None]], Any] = _default_wgc_session_factory,
        probe_hz: int = 30,
        stable_frames: int = 3,
        emit_empty: bool = False,
    ) -> None:
        self.scanner = scanner
        self.emit = emit
        self._find_sc_window = find_sc_window
        self._load_window_region = load_window_region
        self._wgc_session_factory = wgc_session_factory
        self._emit_empty = emit_empty

        self._tick_period = 1.0 / probe_hz
        self._idle_period = 0.5  # waiting / idle_minimized
        self._tracker = StabilityTracker(stable_frames=stable_frames)
        self._status: Status = "stopped"

        self._region_window_rel: Optional[tuple[int, int, int, int]] = None

        self._wgc: Optional[Any] = None
        self._wgc_hwnd: Optional[int] = None
        self._frame_lock = threading.Lock()
        self._latest_frame: Optional[tuple[bytes, int, int]] = None
        self._ticks_without_frame: int = 0
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
        self._status = "waiting"
        return {"ok": True}

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        self._thread = None
        self._stop_wgc()
        self._status = "stopped"

    # ---- Loop -----------------------------------------------------------------

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
