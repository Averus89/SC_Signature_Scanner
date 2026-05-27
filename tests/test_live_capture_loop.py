"""LiveCapture — capture loop / thread / orchestration.

Strategy: drive the loop body synchronously via tick(), bypassing the thread
entirely. The thread is dead-simple wrapping around tick() in a sleep loop and
isn't usefully unit-testable on its own.
"""
from typing import Optional
from unittest.mock import MagicMock

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
        # Repeat the last shot if we've run out — keeps tests resilient.
        if len(self._shots) == 1:
            return self._shots[0]
        return self._shots.pop(0)


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
    mss_factory = MagicMock(return_value=FakeMss(shots or [FakeShot(b"\x00" * (100 * 30 * 4), 100, 30)]))
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
    """Looking away (blank region) then back to the same rock must fire again."""
    win = WindowInfo(hwnd=1, client_rect=(0, 0, 1920, 1080), is_minimized=False, is_foreground=True)
    sig_bytes = b"\xAA" * (100 * 30 * 4)
    blank_bytes = b"\x55" * (100 * 30 * 4)
    # Sequence: signature, signature, blank, blank, signature, signature
    shots = [
        FakeShot(sig_bytes, 100, 30),
        FakeShot(sig_bytes, 100, 30),
        FakeShot(blank_bytes, 100, 30),
        FakeShot(blank_bytes, 100, 30),
        FakeShot(sig_bytes, 100, 30),
        FakeShot(sig_bytes, 100, 30),
    ]

    finder = MagicMock(return_value=win)
    scanner = MagicMock()
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

    # Ticks 1-2: signature, OCR returns a real result → emit fires once.
    scanner.scan_pil_image.return_value = {
        "signature": 1, "matches": [{"name": "x"}]
    }
    live.tick()  # ongoing
    live.tick()  # stable_change → emit (1st)
    assert emit.call_count == 1

    # Ticks 3-4: blank region, OCR returns None → tracker re-arms via empty_rearm.
    scanner.scan_pil_image.return_value = None
    live.tick()  # ongoing (hash changed to blank_bytes)
    live.tick()  # stable_change → OCR called → returns None → empty_rearm

    # Ticks 5-6: signature again, OCR returns a real result → emit fires again.
    scanner.scan_pil_image.return_value = {
        "signature": 1, "matches": [{"name": "x"}]
    }
    live.tick()  # ongoing (hash flipped back to sig_bytes)
    live.tick()  # stable_change → emit (2nd)
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
    live, _ = _make_live(window=win, region=None)
    started = live.start_for_tests()
    assert started["ok"] is False
    assert "calibrate" in started["error"].lower()


def test_stop_returns_to_stopped():
    win = WindowInfo(hwnd=1, client_rect=(0, 0, 1920, 1080), is_minimized=False, is_foreground=True)
    live, _ = _make_live(window=win)
    live.start_for_tests()
    live.stop()
    assert live.status == "stopped"


def test_emit_empty_true_surfaces_no_signature_to_emit():
    """With emit_empty=True, a stable frame whose OCR returns no signature still
    fires the emit callback so the detection log shows the loop is alive."""
    win = WindowInfo(hwnd=1, client_rect=(0, 0, 1920, 1080), is_minimized=False, is_foreground=True)
    same_bytes = b"\x77" * (100 * 30 * 4)
    shots = [FakeShot(same_bytes, 100, 30) for _ in range(3)]

    finder = MagicMock(return_value=win)
    scanner = MagicMock()
    scanner.scan_pil_image.return_value = None  # OCR found nothing
    emit = MagicMock()
    live = LiveCapture(
        scanner=scanner,
        emit=emit,
        find_sc_window=finder,
        load_window_region=lambda: (0, 0, 100, 30),
        mss_factory=lambda: FakeMss(shots),
        probe_hz=30,
        stable_frames=2,
        emit_empty=True,
    )
    live.start_for_tests()
    live.tick()  # ongoing
    live.tick()  # stable_change → OCR returns None → emit fires anyway
    emit.assert_called_once()
    payload = emit.call_args.args[0]
    # Synthesized error payload when result is None.
    assert "error" in payload
    assert emit.call_args.kwargs == {"source": "live"}


def test_emit_empty_false_suppresses_no_signature_default_behavior():
    """Default emit_empty=False: stable no-signature frames are silent
    (regression guard for the v6.1.0 default behavior)."""
    win = WindowInfo(hwnd=1, client_rect=(0, 0, 1920, 1080), is_minimized=False, is_foreground=True)
    same_bytes = b"\x77" * (100 * 30 * 4)
    shots = [FakeShot(same_bytes, 100, 30) for _ in range(3)]

    finder = MagicMock(return_value=win)
    scanner = MagicMock()
    scanner.scan_pil_image.return_value = None
    emit = MagicMock()
    live = LiveCapture(
        scanner=scanner,
        emit=emit,
        find_sc_window=finder,
        load_window_region=lambda: (0, 0, 100, 30),
        mss_factory=lambda: FakeMss(shots),
        probe_hz=30,
        stable_frames=2,
        # emit_empty defaults to False — do not pass.
    )
    live.start_for_tests()
    live.tick()
    live.tick()
    emit.assert_not_called()
