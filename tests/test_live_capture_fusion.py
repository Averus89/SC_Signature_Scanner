"""Multi-frame super-resolution: fuse_frames + its wiring into the tick loop.

The signature renders too small (~20px) for stable single-frame OCR. While a
rock is held the loop captures many sub-pixel-distinct frames of the same value;
fuse_frames aligns and averages them to recover detail and cancel anti-aliasing
noise. These tests pin the helper's contract and verify the loop feeds a fused,
upscaled image to the scanner.
"""
from unittest.mock import MagicMock

import cv2
import numpy as np
from PIL import Image

from live_capture import LiveCapture, _FUSION_SCALE, fuse_frames
from window_finder import WindowInfo


def _raw(rgb: np.ndarray) -> tuple[bytes, int, int]:
    """Pack an RGB array into a (bgrx_bytes, w, h) crop like the WGC path yields."""
    h, w = rgb.shape[:2]
    buf = Image.fromarray(rgb, "RGB").tobytes("raw", "BGRX")
    return (buf, w, h)


def _structured_base(w: int = 40, h: int = 27) -> np.ndarray:
    """A deterministic textured patch — gives ECC gradients to lock onto."""
    base = np.zeros((h, w, 3), dtype=np.uint8)
    base[:, ::4] = 200          # vertical bars
    base[::3, :] = np.maximum(base[::3, :], 80)  # horizontal texture
    return base


def test_single_frame_upscales_to_target_size():
    rgb = _structured_base()
    fused = fuse_frames([_raw(rgb)], scale=_FUSION_SCALE)
    assert fused is not None
    assert fused.size == (40 * _FUSION_SCALE, 27 * _FUSION_SCALE)


def test_empty_input_returns_none():
    assert fuse_frames([], scale=_FUSION_SCALE) is None


def test_identical_frames_average_to_the_single_upscale():
    rgb = _structured_base()
    one = np.asarray(fuse_frames([_raw(rgb)], scale=4))
    many = np.asarray(fuse_frames([_raw(rgb)] * 5, scale=4))
    # Averaging identical (zero-shift) frames must reproduce the single upscale.
    assert np.allclose(one, many, atol=1)


def test_mismatched_shapes_are_skipped():
    big = _structured_base(40, 27)
    small = _structured_base(20, 13)
    fused = fuse_frames([_raw(big), _raw(small)], scale=4)
    # First crop sets the reference size; the odd one out is dropped.
    assert fused.size == (40 * 4, 27 * 4)


def test_uniform_frames_do_not_raise():
    flat = np.full((27, 40, 3), 127, dtype=np.uint8)
    # ECC cannot converge on a flat patch; fusion must fall back, not crash.
    fused = fuse_frames([_raw(flat)] * 4, scale=4)
    assert fused.size == (40 * 4, 27 * 4)


def test_fusion_reduces_noise_vs_single_frame():
    base = _structured_base()
    target = (base.shape[1] * 4, base.shape[0] * 4)
    base_up = cv2.resize(base, target, interpolation=cv2.INTER_LANCZOS4).astype(np.float32)

    rng = np.random.RandomState(0)
    frames = [
        np.clip(base.astype(np.float32) + rng.normal(0, 25, base.shape), 0, 255).astype(np.uint8)
        for _ in range(6)
    ]

    fused = np.asarray(fuse_frames([_raw(f) for f in frames], scale=4)).astype(np.float32)
    single = cv2.resize(frames[0], target, interpolation=cv2.INTER_LANCZOS4).astype(np.float32)

    mse_fused = float(np.mean((fused - base_up) ** 2))
    mse_single = float(np.mean((single - base_up) ** 2))
    assert mse_fused < mse_single


# ---- loop integration -------------------------------------------------------

class _FakeWGC:
    def __init__(self, hwnd, on_frame):
        self._on_frame = on_frame
        self.is_active = False

    def start(self):
        self.is_active = True

    def stop(self):
        self.is_active = False

    def push(self, raw, w, h):
        self._on_frame(raw, w, h)


def test_loop_feeds_a_fused_upscaled_image_to_the_scanner():
    win = WindowInfo(hwnd=1, client_rect=(0, 0, 1920, 1080), is_minimized=False, is_foreground=True)
    frame = b"\x00" * (100 * 30 * 4)
    scanner = MagicMock()
    scanner.scan_pil_image.return_value = {"signature": 1, "matches": [{"name": "x"}]}
    sessions: dict[int, _FakeWGC] = {}

    def factory(hwnd, on_frame):
        sessions[hwnd] = _FakeWGC(hwnd, on_frame)
        return sessions[hwnd]

    live = LiveCapture(
        scanner=scanner,
        emit=MagicMock(),
        find_sc_window=MagicMock(return_value=win),
        load_window_region=lambda: (0, 0, 100, 30),
        wgc_session_factory=factory,
        probe_hz=30,
    )
    live.start_for_tests()
    live.tick()                       # creates session, no frame yet
    sessions[1].push(frame, 100, 30)
    live.tick()                       # first frame → fuse → scan

    scanner.scan_pil_image.assert_called_once()
    passed = scanner.scan_pil_image.call_args.args[0]
    # ROI is 100x30; fused output is scaled up for OCR.
    assert passed.size == (100 * _FUSION_SCALE, 30 * _FUSION_SCALE)
