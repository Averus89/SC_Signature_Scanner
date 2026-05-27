"""_crop_bgra — pure helper that crops a BGRA byte buffer to a sub-rect."""
from live_capture import _crop_bgra


def test_crop_returns_correct_subrect_bytes():
    """Synthetic 4x3 BGRA frame, crop the middle 2x2."""
    # Each pixel is 4 bytes; we encode column index as the B byte so we can
    # spot-check column ordering.
    def row(start_col: int, w: int) -> bytes:
        return b"".join(bytes([c, 0, 0, 255]) for c in range(start_col, start_col + w))

    frame = row(0, 4) + row(0, 4) + row(0, 4)  # 4x3
    roi, w, h = _crop_bgra(frame, 4, 3, (1, 1, 3, 3))
    assert (w, h) == (2, 2)
    # Two rows of two pixels each, columns 1 and 2.
    expected = bytes([1, 0, 0, 255, 2, 0, 0, 255, 1, 0, 0, 255, 2, 0, 0, 255])
    assert roi == expected


def test_crop_handles_full_frame():
    """Region equal to full frame returns the whole buffer unchanged."""
    frame = bytes(range(4 * 2 * 4))  # 4x2 = 32 bytes
    roi, w, h = _crop_bgra(frame, 4, 2, (0, 0, 4, 2))
    assert (w, h) == (4, 2)
    assert roi == frame


def test_crop_first_pixel_of_row_is_top_left():
    """Verify no row flip and no column swap."""
    # 2x2 frame, top-left is byte 0, top-right is byte 4, etc.
    frame = bytes(range(2 * 2 * 4))
    roi, _, _ = _crop_bgra(frame, 2, 2, (0, 0, 1, 1))
    # Top-left pixel is bytes 0..3.
    assert roi == bytes([0, 1, 2, 3])


def test_crop_size_matches_region():
    """len(output) == (x2-x1) * (y2-y1) * 4."""
    frame = bytes(100 * 50 * 4)  # 20,000 bytes
    roi, w, h = _crop_bgra(frame, 100, 50, (10, 5, 60, 25))
    assert (w, h) == (50, 20)
    assert len(roi) == 50 * 20 * 4
