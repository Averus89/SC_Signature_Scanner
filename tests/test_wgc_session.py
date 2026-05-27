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


def _make_session(hwnd: int = 42) -> tuple[WGCSession, dict, MagicMock]:
    """Create a WGCSession backed by a FakeCaptureLib. Returns
    (session, holder, on_frame_callback). After session.start(), holder['lib']
    will be the FakeCaptureLib instance."""
    on_frame = MagicMock()
    fake_lib_holder: dict = {}

    def lib_factory(hwnd_in: int):
        lib = FakeCaptureLib()
        fake_lib_holder["lib"] = lib
        return lib

    session = WGCSession(hwnd, on_frame, capture_lib_factory=lib_factory)
    return session, fake_lib_holder, on_frame


def test_start_raises_when_wgc_unsupported():
    """is_supported() False → start() raises WGCError."""
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
