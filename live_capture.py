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


Status = Literal["stopped", "waiting", "idle_minimized", "idle_occluded", "running", "error"]


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


def _default_window_from_point(pt: tuple[int, int]) -> int:
    """Return the top-level (root) hwnd at the given screen point, or 0.

    Used to detect when SC is occluded by another window at the capture
    point — mss.grab is a desktop screen-scrape and returns the topmost
    pixel content, so we must check that SC is actually on top before
    interpreting captured bytes as HUD content.
    """
    import win32gui
    GA_ROOT = 2
    try:
        hwnd = win32gui.WindowFromPoint(pt)
        if not hwnd:
            return 0
        return win32gui.GetAncestor(hwnd, GA_ROOT) or hwnd
    except Exception:
        return 0


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
        window_from_point: Callable[[tuple[int, int]], int] = _default_window_from_point,
        probe_hz: int = 30,
        stable_frames: int = 3,
        emit_empty: bool = False,
    ) -> None:
        self.scanner = scanner
        self.emit = emit
        self._find_sc_window = find_sc_window
        self._load_window_region = load_window_region
        self._mss_factory = mss_factory
        self._window_from_point = window_from_point
        self._emit_empty = emit_empty

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
        result = self._prepare_start()
        if result["ok"]:
            # Pre-create the mss context so tick() reuses a single instance,
            # allowing FakeMss to dispense shots in sequence.
            self._mss = self._mss_factory()
        return result

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

        # Occlusion check: mss.grab is a desktop screen-scrape and returns
        # whatever window is topmost at the captured pixels. If SC isn't
        # the topmost window at the center of our capture rect, the bytes
        # we'd grab are from a different window (Explorer, an OSD, the
        # taskbar, etc.) — interpreting them as HUD content produces
        # garbage OCR. Skip the capture and surface the state to the UI.
        cx, cy, cw, ch = self._abs_capture_rect
        center_pt = (cx + cw // 2, cy + ch // 2)
        top_root = self._window_from_point(center_pt)
        if top_root and top_root != info.hwnd:
            self._tracker.reset()
            self._status = "idle_occluded"
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
            if self._emit_empty:
                # Power-user diagnostic: surface no-signature stable frames so
                # the detection log shows the loop is actually probing.
                self.emit(result or {"error": "No signature detected"}, source="live")
            return self._tick_period

        self.emit(result, source="live")
        return self._tick_period
