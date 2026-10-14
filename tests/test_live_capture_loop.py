"""LiveCapture — capture loop / thread / orchestration.

Strategy: drive the loop body synchronously via tick(), bypassing the thread
entirely. The thread is dead-simple wrapping around tick() in a sleep loop and
isn't usefully unit-testable on its own. A fake clock controls the OCR interval.
"""
from typing import Optional
from unittest.mock import MagicMock

from live_capture import LiveCapture
from window_finder import WindowInfo


INTERVAL = 0.4
ROI_BYTES = 100 * 30 * 4
WIN = WindowInfo(hwnd=1, client_rect=(0, 0, 1920, 1080), is_minimized=False, is_foreground=True)
HIT = {"signature": 3540, "matches": [{"name": "Beryl (Rare)"}], "method": "fixed", "ocr_confidence": 0.9}


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


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def _make_live(
    *,
    window,
    region: Optional[tuple[int, int, int, int]] = (0, 0, 100, 30),
    scan_result: Optional[dict] = None,
    emit_empty: bool = False,
) -> tuple[LiveCapture, MagicMock, dict, FakeClock]:
    """Build a LiveCapture wired with a FakeWGCSession factory and fake clock.

    `window` may be a WindowInfo/None, or a list used as the finder's
    side_effect. Returns (live, emit_mock, sessions_dict, clock).
    """
    if isinstance(window, list):
        finder = MagicMock(side_effect=window)
    else:
        finder = MagicMock(return_value=window)
    scanner = MagicMock()
    scanner.scan_pil_image.return_value = scan_result
    emit = MagicMock()
    sessions: dict[int, FakeWGCSession] = {}
    clock = FakeClock()

    def factory(hwnd: int, on_frame):
        session = FakeWGCSession(hwnd, on_frame)
        sessions[hwnd] = session
        return session

    live = LiveCapture(
        scanner=scanner,
        emit=emit,
        find_sc_window=finder,
        load_window_region=MagicMock(return_value=region),
        wgc_session_factory=factory,
        probe_hz=30,
        ocr_interval_s=INTERVAL,
        emit_empty=emit_empty,
        clock=clock,
    )
    return live, emit, sessions, clock


def _frame_tick(live, sessions, clock, byte: int, *, advance: float = INTERVAL, hwnd: int = 1) -> None:
    """Advance the clock, push a uniform frame and run one tick."""
    clock.now += advance
    sessions[hwnd].push_frame(bytes([byte]) * ROI_BYTES, 100, 30)
    live.tick()


def test_status_starts_stopped():
    live, _, _, _ = _make_live(window=None)
    assert live.status == "stopped"


def test_tick_with_no_window_sets_waiting():
    live, _, _, _ = _make_live(window=None)
    live.start_for_tests()
    live.tick()
    assert live.status == "waiting"


def test_tick_with_minimized_window_sets_idle_minimized():
    win = WindowInfo(hwnd=1, client_rect=(0, 0, 1920, 1080), is_minimized=True, is_foreground=False)
    live, _, _, _ = _make_live(window=win)
    live.start_for_tests()
    live.tick()
    assert live.status == "idle_minimized"


def test_first_frame_is_ocrd_and_emitted_immediately():
    live, emit, sessions, clock = _make_live(window=WIN, scan_result=HIT)
    live.start_for_tests()
    live.tick()  # creates the WGC session, no frame yet
    _frame_tick(live, sessions, clock, 0x10, advance=0)
    assert live.status == "running"
    emit.assert_called_once()
    assert emit.call_args.args[0]["signature"] == 3540
    assert emit.call_args.kwargs == {"source": "live"}


def test_ocr_fires_on_interval_even_while_the_image_keeps_changing():
    """The old stability gate never fired over moving background; timed OCR must."""
    live, _, sessions, clock = _make_live(window=WIN)
    live.start_for_tests()
    live.tick()
    for i in range(5):
        _frame_tick(live, sessions, clock, i)  # every frame different
    assert live.scanner.scan_pil_image.call_count == 5


def test_ocr_is_throttled_between_intervals():
    live, _, sessions, clock = _make_live(window=WIN)
    live.start_for_tests()
    live.tick()
    _frame_tick(live, sessions, clock, 1, advance=0)  # OCR #1
    for i in range(10):
        _frame_tick(live, sessions, clock, 2 + i, advance=INTERVAL / 20)  # 0.2 s total
    assert live.scanner.scan_pil_image.call_count == 1
    _frame_tick(live, sessions, clock, 99, advance=INTERVAL)  # OCR #2
    assert live.scanner.scan_pil_image.call_count == 2


def test_same_signature_is_not_re_emitted():
    live, emit, sessions, clock = _make_live(window=WIN, scan_result=HIT)
    live.start_for_tests()
    live.tick()
    for i in range(4):
        _frame_tick(live, sessions, clock, i)
    assert live.scanner.scan_pil_image.call_count == 4
    emit.assert_called_once()


def test_new_signature_is_emitted():
    live, emit, sessions, clock = _make_live(window=WIN, scan_result=HIT)
    live.start_for_tests()
    live.tick()
    _frame_tick(live, sessions, clock, 1)
    live.scanner.scan_pil_image.return_value = {"signature": 7000, "matches": [{"name": "y"}]}
    _frame_tick(live, sessions, clock, 2)
    assert [c.args[0]["signature"] for c in emit.call_args_list] == [3540, 7000]


def test_empty_read_re_arms_so_the_same_signature_fires_again():
    """Looking away (no signature) then back to the same rock must fire again."""
    live, emit, sessions, clock = _make_live(window=WIN, scan_result=HIT)
    live.start_for_tests()
    live.tick()
    _frame_tick(live, sessions, clock, 1)  # emit #1
    live.scanner.scan_pil_image.return_value = None
    _frame_tick(live, sessions, clock, 2)  # empty read → re-arm
    live.scanner.scan_pil_image.return_value = HIT
    _frame_tick(live, sessions, clock, 1)  # emit #2
    assert emit.call_count == 2


def test_window_change_starts_a_fresh_session_and_re_arms():
    win_b = WindowInfo(hwnd=2, client_rect=(500, 0, 1920, 1080), is_minimized=False, is_foreground=True)
    live, emit, sessions, clock = _make_live(window=[WIN, WIN, win_b, win_b], scan_result=HIT)
    live.start_for_tests()
    live.tick()  # session for hwnd=1
    _frame_tick(live, sessions, clock, 1)  # emit #1
    live.tick()  # win_b → new session, no frame yet
    assert 2 in sessions
    _frame_tick(live, sessions, clock, 1, hwnd=2)  # same value, but state was reset → emit #2
    assert emit.call_count == 2


def test_starts_with_missing_region_sets_error():
    live, _, _, _ = _make_live(window=WIN, region=None)
    started = live.start_for_tests()
    assert started["ok"] is False
    assert "calibrate" in started["error"].lower()


def test_stop_returns_to_stopped():
    live, _, _, _ = _make_live(window=WIN)
    live.start_for_tests()
    live.stop()
    assert live.status == "stopped"


def test_emit_empty_true_surfaces_no_signature_to_emit():
    """With emit_empty=True, an OCR run that finds no signature still fires
    the emit callback so the detection log shows the loop is alive."""
    live, emit, sessions, clock = _make_live(window=WIN, emit_empty=True)
    live.start_for_tests()
    live.tick()
    _frame_tick(live, sessions, clock, 0x77)
    emit.assert_called_once()
    assert "error" in emit.call_args.args[0]
    assert emit.call_args.kwargs == {"source": "live"}


def test_emit_empty_false_suppresses_no_signature_default_behavior():
    """Default emit_empty=False: no-signature reads are silent."""
    live, emit, sessions, clock = _make_live(window=WIN)
    live.start_for_tests()
    live.tick()
    _frame_tick(live, sessions, clock, 0x77)
    _frame_tick(live, sessions, clock, 0x78)
    emit.assert_not_called()


def test_tick_with_no_frame_yet_remains_running():
    """Session active, but no frame delivered yet — status stays 'running'
    (warming up) and tick returns the normal tick period, no OCR."""
    live, emit, _, _ = _make_live(window=WIN)
    live.start_for_tests()
    live.tick()
    assert live.status == "running"
    emit.assert_not_called()
    live.scanner.scan_pil_image.assert_not_called()


def test_tick_warming_up_eventually_errors_if_no_frames_arrive():
    """After _NO_FRAME_ERROR_THRESHOLD ticks of no frame, status becomes 'error'."""
    from live_capture import _NO_FRAME_ERROR_THRESHOLD
    live, _, _, _ = _make_live(window=WIN)
    live.start_for_tests()
    for _ in range(_NO_FRAME_ERROR_THRESHOLD):
        live.tick()
    assert live.status == "error"


def test_roi_clamp_to_smaller_frame_yields_degenerate_error():
    """Live region's bottom-right falls outside the frame size → status 'error'."""
    win = WindowInfo(hwnd=1, client_rect=(0, 0, 5120, 1440), is_minimized=False, is_foreground=False)
    live, _, sessions, _ = _make_live(window=win, region=(4000, 1000, 4100, 1050))
    live.start_for_tests()
    live.tick()  # creates WGC session (hwnd=1), no frame yet
    sessions[1].push_frame(b"\x00" * (100 * 50 * 4), 100, 50)
    live.tick()
    assert live.status == "error"
