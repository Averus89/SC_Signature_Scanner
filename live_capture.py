"""Live signature scanning from the running Star Citizen window.

Units in this file:
  - compute_abs_capture_rect — pure geometry helper
  - fuse_frames — multi-frame super-resolution of same-content crops
  - LiveCapture — capture loop / thread / orchestration (timed OCR)
"""
from __future__ import annotations

import hashlib
import threading
import time
from collections import deque
from typing import Any, Callable, Literal, Optional

from PIL import Image

from wgc_capture import WGCError


# Live capture thresholds.
# Number of ticks with no frame before flipping to error status —
# ~3 sec at the default 30 Hz probe rate.
_NO_FRAME_ERROR_THRESHOLD = 90

# OCR runs on a fixed interval rather than when the ROI "stabilizes". The
# signature label is drawn over moving space and rocks, so a whole-ROI digest
# almost never repeats while the player flies — measured live, a 3-frame
# stability gate fired 0 times in 443 samples, and only ever fired on still,
# empty space. ~40 ms of OCR every 0.4 s is ~10% of one core.
DEFAULT_OCR_INTERVAL_S = 0.4

# Identical reads in a row needed before a popup. 2 stopped single misreads
# from flipping the popup, but most rocks are never read correctly twice in a
# row before the player moves on: in two replayed sessions it covered 6 of 11
# and 1 of 3 rocks, versus all of them at 1. With the pin crop and confidence
# floor doing the filtering, 1 is the better trade (configurable).
DEFAULT_CONFIRM_READS = 1
# Reads below this mean OCR confidence are ignored. In a labelled session every
# wrong read that survived icon stripping scored <= 0.39 while true reads were
# mostly 0.55-0.99; 0.45 dropped all wrong reads and one true read (0.35).
DEFAULT_MIN_CONFIDENCE = 0.45

# The signature label is drawn right of an orange map-pin icon, which OCR reads
# as a leading "2" or "9" ("9.2000" -> 3200, "94000"). The pin is a solid
# orange block; digits only carry thin orange fringes, so a wide run of mostly
# orange columns marks the pin. Only the FIRST such run from the left counts:
# taking the rightmost orange column instead cut into narrow digits whose
# fringes overlap ("11,565" -> "565").
_ICON_COLUMN_FRACTION = 0.25  # share of a column's pixels that must be orange
_ICON_MIN_RUN_FRACTION = 0.05  # a pin run is at least this share of the width
_ICON_SEARCH_FRACTION = 0.6   # the pin is only looked for in the left part
_ICON_MARGIN_FRACTION = 0.03  # extra crop right of the pin's last column


def strip_marker_icon(img: Image.Image) -> Image.Image:
    """Crop away the orange map-pin icon left of the signature digits.

    Returns the image unchanged when no pin is found.
    """
    import numpy as np

    rgb = np.asarray(img.convert("RGB")).astype(np.int16)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    orange = (r - b > 80) & (r > 150) & (g < 170)
    icon_cols = orange.sum(axis=0) >= _ICON_COLUMN_FRACTION * rgb.shape[0]
    width = rgb.shape[1]
    min_run = _ICON_MIN_RUN_FRACTION * width
    x = 0
    while x < int(width * _ICON_SEARCH_FRACTION):
        if not icon_cols[x]:
            x += 1
            continue
        start = x
        while x < width and icon_cols[x]:
            x += 1
        if x - start >= min_run:
            left = x + int(_ICON_MARGIN_FRACTION * width)
            return img.crop((left, 0, img.width, img.height))
    return img


class SignatureConfirmer:
    """Decide which OCR reads reach the popup.

    - A signature is emitted once it has been read `confirm_reads` times in a
      row and differs from the last emitted one.
    - An empty read (nothing on screen) breaks the run. After
      `rearm_empty_reads` empty reads in a row the last emitted value is
      forgotten, so looking away and back at the same rock fires again; a
      single flickering empty read does not repeat the popup.
    - A low-confidence read is ignored (the caller never passes it in).
    """

    def __init__(
        self,
        confirm_reads: int = DEFAULT_CONFIRM_READS,
        rearm_empty_reads: int = 3,
    ) -> None:
        if confirm_reads < 1:
            raise ValueError("confirm_reads must be >= 1")
        self._confirm_reads = confirm_reads
        self._rearm_empty_reads = rearm_empty_reads
        self._candidate: Optional[Any] = None
        self._count = 0
        self._empty_count = 0
        self._last_emitted: Optional[Any] = None

    def observe(self, signature: Optional[Any]) -> Optional[Any]:
        """Feed one confident read (None = no signature). Returns the
        signature to emit, or None."""
        if signature is None:
            self._candidate = None
            self._count = 0
            self._empty_count += 1
            if self._empty_count >= self._rearm_empty_reads:
                self._last_emitted = None
            return None
        self._empty_count = 0
        if signature == self._candidate:
            self._count += 1
        else:
            self._candidate = signature
            self._count = 1
        if self._count >= self._confirm_reads and signature != self._last_emitted:
            self._last_emitted = signature
            return signature
        return None

    def reset(self) -> None:
        self._candidate = None
        self._count = 0
        self._empty_count = 0
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


def _stable_digest(bgra_bytes: bytes, w: int, h: int) -> bytes:
    """Perceptual digest robust to subpixel jitter and HUD anti-aliasing.

    Live SC rendering produces minor per-frame variation (anti-aliasing,
    breathing animations, distance counters) even on visually-static HUD
    content. Hashing the raw BGRA bytes never produces equal digests across
    frames, so same-content crops could never be grouped for fusion.
    Downscaling to 32x16 grayscale + 4-bit quantization absorbs that noise
    while still yielding distinct hashes for actually-different content.
    """
    img = Image.frombytes("RGB", (w, h), bgra_bytes, "raw", "BGRX")
    small = img.convert("L").resize((32, 16), Image.BILINEAR)
    quantized = bytes(p >> 4 for p in small.tobytes())
    return hashlib.blake2b(quantized, digest_size=8).digest()


# Multi-frame super-resolution. The signature renders at ~20px digit height, too
# small for stable OCR. While a rock is held the loop captures many frames of the
# same number, each with slightly different sub-pixel jitter and anti-aliasing.
# Fusing them recovers detail a single frame lacks (like phone "super-res zoom").
_FUSION_MAX_FRAMES = 8   # ring-buffer depth of recent ROI crops
_FUSION_SCALE = 4        # upscale factor of the fused output


def fuse_frames(
    raw_crops: list[tuple[bytes, int, int]],
    scale: int = _FUSION_SCALE,
) -> Optional[Image.Image]:
    """Sub-pixel-aligned mean of same-content ROI crops — multi-frame SR.

    Each crop is upscaled to the target grid, registered to the first crop with
    an ECC translation estimate (sub-pixel at native resolution = whole-pixel on
    the upscaled grid), then averaged. Averaging sub-pixel-distinct samples on a
    finer grid reconstructs edge detail and cancels per-frame anti-aliasing
    noise, which is what makes a steady number read inconsistently frame to
    frame.

    Args:
        raw_crops: list of (bgrx_bytes, width, height) for the SAME ROI content.
            Crops whose size differs from the first are skipped.
        scale: upscale factor of the fused output.

    Returns:
        The fused RGB image (size scale*W x scale*H), or None if no usable crop.
        Alignment is best-effort: if ECC fails to converge (e.g. a flat crop)
        that frame is averaged un-aligned rather than dropped.
    """
    if not raw_crops:
        return None

    import numpy as np

    decoded: list[Any] = []
    w0 = h0 = None
    for buf, w, h in raw_crops:
        if w0 is None:
            w0, h0 = w, h
        if (w, h) != (w0, h0):
            continue
        decoded.append(np.asarray(Image.frombytes("RGB", (w, h), buf, "raw", "BGRX")))
    if not decoded:
        return None

    try:
        import cv2
    except ImportError:
        # No OpenCV — fall back to a plain upscale of the most recent frame.
        return Image.fromarray(decoded[-1]).resize((w0 * scale, h0 * scale), Image.LANCZOS)

    target = (w0 * scale, h0 * scale)
    ups = [cv2.resize(c, target, interpolation=cv2.INTER_LANCZOS4) for c in decoded]
    if len(ups) == 1:
        return Image.fromarray(ups[0])

    ref_gray = cv2.cvtColor(ups[0], cv2.COLOR_RGB2GRAY).astype(np.float32)
    acc = ups[0].astype(np.float32).copy()
    n = 1
    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 50, 1e-4)
    for u in ups[1:]:
        gray = cv2.cvtColor(u, cv2.COLOR_RGB2GRAY).astype(np.float32)
        warp = np.eye(2, 3, dtype=np.float32)
        try:
            cv2.findTransformECC(ref_gray, gray, warp, cv2.MOTION_TRANSLATION, criteria, None, 5)
            aligned = cv2.warpAffine(
                u, warp, target,
                flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP,
                borderMode=cv2.BORDER_REPLICATE,
            )
        except cv2.error:
            aligned = u  # ECC didn't converge — use the frame un-aligned.
        acc += aligned.astype(np.float32)
        n += 1

    fused = (acc / n).clip(0, 255).astype(np.uint8)
    return Image.fromarray(fused)


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
    """Background capture loop. Probes the SC window at probe_hz, OCRs the
    ROI every `ocr_interval_s`, and emits scan results via the supplied
    `emit` callback once a new signature is confirmed (see SignatureConfirmer)."""

    def __init__(
        self,
        *,
        scanner: Any,
        emit: Callable[..., None],
        find_sc_window: Callable[[], Any] = _default_find_sc_window,
        load_window_region: Callable[[], Any] = _default_load_window_region,
        wgc_session_factory: Callable[[int, Callable[[bytes, int, int], None]], Any] = _default_wgc_session_factory,
        probe_hz: int = 30,
        ocr_interval_s: float = DEFAULT_OCR_INTERVAL_S,
        confirm_reads: int = DEFAULT_CONFIRM_READS,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        emit_empty: bool = False,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.scanner = scanner
        self.emit = emit
        self._find_sc_window = find_sc_window
        self._load_window_region = load_window_region
        self._wgc_session_factory = wgc_session_factory
        self._emit_empty = emit_empty
        self._clock = clock

        self._tick_period = 1.0 / probe_hz
        self._idle_period = 0.5  # waiting / idle_minimized
        self._ocr_interval_s = ocr_interval_s
        self._last_ocr_at: Optional[float] = None
        self._min_confidence = min_confidence
        self._confirmer = SignatureConfirmer(confirm_reads)
        self._status: Status = "stopped"

        self._region_window_rel: Optional[tuple[int, int, int, int]] = None

        self._wgc: Optional[Any] = None
        self._wgc_hwnd: Optional[int] = None
        self._frame_lock = threading.Lock()
        self._latest_frame: Optional[tuple[bytes, int, int]] = None
        # Recent ROI crops (digest, bgrx_bytes, w, h) for multi-frame fusion.
        self._frame_buffer: deque[tuple[bytes, bytes, int, int]] = deque(
            maxlen=_FUSION_MAX_FRAMES
        )
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
        self._reset_detection()
        self._status = "waiting"
        return {"ok": True}

    def _reset_detection(self) -> None:
        """Forget buffered crops, the OCR timer and the last emitted value —
        used whenever the capture target changes."""
        self._frame_buffer.clear()
        self._last_ocr_at = None
        self._confirmer.reset()

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
            self._reset_detection()
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
            self._reset_detection()

        if self._wgc is None or not self._wgc.is_active:
            # WGC can close a session while the window survives (e.g. device
            # loss); dropping it lets the next tick re-bind via the hwnd check.
            self._stop_wgc()
            self._status = "error"
            return self._idle_period

        # Consume the frame so a stalled session can't keep re-OCRing stale
        # pixels and the no-frame threshold actually counts.
        with self._frame_lock:
            frame = self._latest_frame
            self._latest_frame = None

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

        digest = _stable_digest(roi_bytes, roi_w, roi_h)
        self._frame_buffer.append((digest, roi_bytes, roi_w, roi_h))
        self._status = "running"

        now = self._clock()
        if self._last_ocr_at is not None and now - self._last_ocr_at < self._ocr_interval_s:
            return self._tick_period
        self._last_ocr_at = now

        # Fuse buffered frames of the same content into one super-resolved
        # image before OCR. Same digest == same displayed value but sub-pixel-
        # distinct pixels; while the view moves this is usually just one frame.
        same_content = [
            (buf, w, h) for (d, buf, w, h) in self._frame_buffer if d == digest
        ]
        try:
            img = fuse_frames(same_content) or Image.frombytes(
                "RGB", (roi_w, roi_h), roi_bytes, "raw", "BGRX"
            )
            img = strip_marker_icon(img)
            result = self.scanner.scan_pil_image(
                img, region=(0, 0, img.width, img.height)
            )
        except Exception as e:
            if self._emit_empty:
                self.emit({"error": f"frame decode/OCR failed: {e}"}, source="live")
            return self._tick_period

        if result is None or result.get("error") or not result.get("matches"):
            self._confirmer.observe(None)
            if self._emit_empty:
                self.emit(result or {"error": "No signature detected"}, source="live")
            return self._tick_period

        if result.get("ocr_confidence", 1.0) < self._min_confidence:
            return self._tick_period

        if self._confirmer.observe(result.get("signature")) is not None:
            self.emit(result, source="live")
        return self._tick_period
