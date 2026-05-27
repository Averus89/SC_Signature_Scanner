"""Windows Graphics Capture session wrapper.

Encapsulates the windows-capture library so the rest of the app speaks a
small, testable interface: hwnd in, BGRA frame bytes out via callback.

The real library's API uses a single `@event` decorator that routes by
function name (on_frame_arrived / on_closed). This wrapper flattens that
into a constructor parameter and exposes start/stop. A
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
    """Construct the real windows-capture session bound to `hwnd`.

    windows-capture 2.x supports window_hwnd directly, which is more
    reliable than window_name for windows with dynamic titles.
    """
    from windows_capture import WindowsCapture

    return WindowsCapture(window_hwnd=hwnd, cursor_capture=False)


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
        self._control: Optional[Any] = None
        self._is_active = False
        self._lock = threading.Lock()

    @property
    def is_active(self) -> bool:
        return self._is_active

    def start(self) -> None:
        """Create the underlying capture, register callbacks, start it.

        Raises WGCError if the underlying start call throws.
        """
        with self._lock:
            if self._is_active:
                return
            lib = self._capture_lib_factory(self.hwnd)

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
                control = lib.start_free_threaded()
            except Exception as e:
                raise WGCError(f"WGC session failed to start: {e}") from e

            self._lib = lib
            self._control = control
            self._is_active = True

    def stop(self) -> None:
        """Stop the capture. Idempotent and safe from any thread.

        Uses the CaptureControl returned by start_free_threaded() — the
        WindowsCapture instance itself has no stop method.
        """
        with self._lock:
            control = self._control
            self._is_active = False
            self._lib = None
            self._control = None
        if control is not None:
            try:
                control.stop()
            except Exception:
                # Best-effort cleanup; the control may already be torn down.
                pass


def _default_wgc_session_factory(
    hwnd: int,
    on_frame: Callable[[bytes, int, int], None],
) -> WGCSession:
    """Construct a real WGCSession. Replaceable via dependency injection
    in LiveCapture for unit tests."""
    return WGCSession(hwnd, on_frame)
