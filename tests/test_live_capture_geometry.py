"""compute_abs_capture_rect — clamp the window-relative region inside the client rect."""
from live_capture import compute_abs_capture_rect


def test_simple_case_returns_translated_rect():
    """Client at (100,200) size 1920x1080, ROI window-rel (50,60)->(170,90) → abs (150,260,120,30)."""
    client = (100, 200, 1920, 1080)
    region_window_rel = (50, 60, 170, 90)
    assert compute_abs_capture_rect(client, region_window_rel) == (150, 260, 120, 30)


def test_clamps_to_client_bounds_when_region_overflows():
    """ROI extending past the client edge gets clamped, not rejected."""
    client = (0, 0, 1000, 500)
    region_window_rel = (900, 400, 1100, 600)  # right/bottom overflow
    assert compute_abs_capture_rect(client, region_window_rel) == (900, 400, 100, 100)


def test_returns_none_for_degenerate_region_after_clamp():
    """Region entirely outside the client area collapses to width/height <= 0."""
    client = (0, 0, 800, 600)
    region_window_rel = (900, 700, 950, 750)
    assert compute_abs_capture_rect(client, region_window_rel) is None


def test_returns_none_when_clamped_too_small():
    """Below the (10, 5) minimum size — treat as degenerate."""
    client = (0, 0, 800, 600)
    region_window_rel = (100, 100, 105, 103)  # 5x3 — too small
    assert compute_abs_capture_rect(client, region_window_rel) is None


def test_negative_client_origin_supported_for_left_of_primary_monitor():
    """SC on a monitor with negative origin (left-of-primary) — mss handles it natively."""
    client = (-1920, 0, 1920, 1080)
    region_window_rel = (100, 50, 220, 80)
    assert compute_abs_capture_rect(client, region_window_rel) == (-1820, 50, 120, 30)
