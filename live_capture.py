"""Live signature scanning from the running Star Citizen window.

Three units, each in this file:
  - StabilityTracker — pure-logic gate (this task)
  - compute_abs_capture_rect — pure geometry helper (next task)
  - LiveCapture — capture loop / thread / orchestration (next task)
"""
from __future__ import annotations

from typing import Literal
from typing import Optional


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
