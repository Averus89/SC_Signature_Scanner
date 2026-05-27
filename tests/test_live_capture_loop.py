"""LiveCapture — capture loop / thread / orchestration.

Strategy: drive the loop body synchronously via tick(), bypassing the thread
entirely. The thread is dead-simple wrapping around tick() in a sleep loop and
isn't usefully unit-testable on its own.
"""
from typing import Optional
from unittest.mock import MagicMock

from live_capture import LiveCapture
from window_finder import WindowInfo


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


def test_status_starts_stopped():
    live, _, _ = _make_live(window=None)
    assert live.status == "stopped"


def test_tick_with_no_window_sets_waiting():
    live, _, _ = _make_live(window=None)
    live.start_for_tests()
    live.tick()
    assert live.status == "waiting"


def test_tick_with_minimized_window_sets_idle_minimized():
    win = WindowInfo(hwnd=1, client_rect=(0, 0, 1920, 1080), is_minimized=True, is_foreground=False)
    live, _, _ = _make_live(window=win)
    live.start_for_tests()
    live.tick()
    assert live.status == "idle_minimized"


def test_tick_with_visible_window_captures_and_runs_ocr_after_stable_frames():
    win = WindowInfo(hwnd=1, client_rect=(0, 0, 1920, 1080), is_minimized=False, is_foreground=True)
    same_bytes = b"\x00" * (100 * 30 * 4)
    scan_result = {
        "signature": 3540,
        "matches": [{"name": "Beryl (Rare)"}],
        "method": "fixed",
        "ocr_confidence": 0.9,
    }
    live, emit, sessions = _make_live(window=win, scan_result=scan_result)
    live.start_for_tests()
    # First tick creates the WGC session but has no frame yet.
    live.tick()
    # Now push the frame and drive two identical ticks (stable_frames=2).
    sessions[1].push_frame(same_bytes, 100, 30)
    live.tick()  # ongoing
    sessions[1].push_frame(same_bytes, 100, 30)
    live.tick()  # stable_change → OCR → emit
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

    finder = MagicMock(return_value=win)
    scanner = MagicMock()
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
        load_window_region=lambda: (0, 0, 100, 30),
        wgc_session_factory=factory,
        probe_hz=30,
        stable_frames=2,
    )
    live.start_for_tests()

    # Tick 0: creates WGC session (no frame yet).
    live.tick()

    # Ticks 1-2: signature, OCR returns a real result → emit fires once.
    scanner.scan_pil_image.return_value = {
        "signature": 1, "matches": [{"name": "x"}]
    }
    sessions[1].push_frame(sig_bytes, 100, 30)
    live.tick()  # ongoing
    sessions[1].push_frame(sig_bytes, 100, 30)
    live.tick()  # stable_change → emit (1st)
    assert emit.call_count == 1

    # Ticks 3-4: blank region, OCR returns None → tracker re-arms via empty_rearm.
    scanner.scan_pil_image.return_value = None
    sessions[1].push_frame(blank_bytes, 100, 30)
    live.tick()  # ongoing (hash changed to blank_bytes)
    sessions[1].push_frame(blank_bytes, 100, 30)
    live.tick()  # stable_change → OCR called → returns None → empty_rearm

    # Ticks 5-6: signature again, OCR returns a real result → emit fires again.
    scanner.scan_pil_image.return_value = {
        "signature": 1, "matches": [{"name": "x"}]
    }
    sessions[1].push_frame(sig_bytes, 100, 30)
    live.tick()  # ongoing (hash flipped back to sig_bytes)
    sessions[1].push_frame(sig_bytes, 100, 30)
    live.tick()  # stable_change → emit (2nd)
    assert emit.call_count == 2


def test_window_move_invalidates_hash_state():
    """When the window hwnd changes, a fresh WGC session starts and the tracker resets."""
    win_a = WindowInfo(hwnd=1, client_rect=(0, 0, 1920, 1080), is_minimized=False, is_foreground=True)
    win_b = WindowInfo(hwnd=2, client_rect=(500, 0, 1920, 1080), is_minimized=False, is_foreground=True)
    same_bytes = b"\xCC" * (100 * 30 * 4)
    scan_result = {"signature": 1, "matches": [{"name": "x"}]}
    finder = MagicMock(side_effect=[win_a, win_a, win_a, win_b, win_b, win_b, win_b])
    scanner = MagicMock()
    scanner.scan_pil_image.return_value = scan_result
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
        load_window_region=lambda: (0, 0, 100, 30),
        wgc_session_factory=factory,
        probe_hz=30,
        stable_frames=2,
    )
    live.start_for_tests()

    # Tick 0: creates WGC session for win_a (hwnd=1), no frame yet.
    live.tick()
    sessions[1].push_frame(same_bytes, 100, 30)
    live.tick()  # win_a, ongoing
    sessions[1].push_frame(same_bytes, 100, 30)
    live.tick()  # win_a, stable_change → emit
    assert emit.call_count == 1

    # win_b has a different hwnd → _start_wgc called, tracker reset, frame None
    live.tick()  # win_b — new session created (hwnd=2), no frame yet → running (warming up)
    assert 2 in sessions  # session for hwnd=2 was created during this tick
    sessions[2].push_frame(same_bytes, 100, 30)
    live.tick()  # win_b, frame arrives → ongoing (stable_frames=2 needs 2 identical)
    sessions[2].push_frame(same_bytes, 100, 30)
    live.tick()  # win_b, stable_change → emit again
    assert emit.call_count == 2


def test_starts_with_missing_region_sets_error():
    win = WindowInfo(hwnd=1, client_rect=(0, 0, 1920, 1080), is_minimized=False, is_foreground=True)
    live, _, _ = _make_live(window=win, region=None)
    started = live.start_for_tests()
    assert started["ok"] is False
    assert "calibrate" in started["error"].lower()


def test_stop_returns_to_stopped():
    win = WindowInfo(hwnd=1, client_rect=(0, 0, 1920, 1080), is_minimized=False, is_foreground=True)
    live, _, _ = _make_live(window=win)
    live.start_for_tests()
    live.stop()
    assert live.status == "stopped"


def test_emit_empty_true_surfaces_no_signature_to_emit():
    """With emit_empty=True, a stable frame whose OCR returns no signature still
    fires the emit callback so the detection log shows the loop is alive."""
    win = WindowInfo(hwnd=1, client_rect=(0, 0, 1920, 1080), is_minimized=False, is_foreground=True)
    same_bytes = b"\x77" * (100 * 30 * 4)

    finder = MagicMock(return_value=win)
    scanner = MagicMock()
    scanner.scan_pil_image.return_value = None  # OCR found nothing
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
        load_window_region=lambda: (0, 0, 100, 30),
        wgc_session_factory=factory,
        probe_hz=30,
        stable_frames=2,
        emit_empty=True,
    )
    live.start_for_tests()
    live.tick()  # creates WGC session (hwnd=1), no frame yet
    sessions[1].push_frame(same_bytes, 100, 30)
    live.tick()  # ongoing
    sessions[1].push_frame(same_bytes, 100, 30)
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

    finder = MagicMock(return_value=win)
    scanner = MagicMock()
    scanner.scan_pil_image.return_value = None
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
        load_window_region=lambda: (0, 0, 100, 30),
        wgc_session_factory=factory,
        probe_hz=30,
        stable_frames=2,
        # emit_empty defaults to False — do not pass.
    )
    live.start_for_tests()
    live.tick()  # creates WGC session (hwnd=1), no frame yet
    sessions[1].push_frame(same_bytes, 100, 30)
    live.tick()
    sessions[1].push_frame(same_bytes, 100, 30)
    live.tick()
    emit.assert_not_called()


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
    live.tick()  # creates WGC session (hwnd=1), no frame yet
    sessions[1].push_frame(b"\x00" * (100 * 50 * 4), 100, 50)
    live.tick()
    assert live.status == "error"
