"""SignatureConfirmer and strip_marker_icon — what reaches the live popup."""
import numpy as np
import pytest
from PIL import Image

from live_capture import SignatureConfirmer, strip_marker_icon


def _feed(reads, confirm_reads=2):
    c = SignatureConfirmer(confirm_reads)
    return [c.observe(r) for r in reads]


def test_a_b_a_never_emits():
    assert _feed([2000, 3200, 2000]) == [None, None, None]


def test_a_a_emits_a_once():
    assert _feed([2000, 2000, 2000]) == [None, 2000, None]


def test_a_a_b_b_switches_to_b():
    assert _feed([2000, 2000, 3200, 3200]) == [None, 2000, None, 3200]


def test_single_empty_read_does_not_repeat_the_popup():
    assert _feed([2000, 2000, None, 2000, 2000]) == [None, 2000, None, None, None]


def test_looking_away_re_arms_the_same_value():
    reads = [2000, 2000, None, None, None, 2000, 2000]
    assert _feed(reads) == [None, 2000, None, None, None, None, 2000]


def test_confirm_reads_one_emits_immediately():
    assert _feed([2000, 3200], confirm_reads=1) == [2000, 3200]


def test_confirm_reads_must_be_positive():
    with pytest.raises(ValueError):
        SignatureConfirmer(0)


def _label(with_icon: bool) -> Image.Image:
    """Dark crop with white 'digits' on the right and an orange pin on the left."""
    a = np.full((40, 100, 3), 20, np.uint8)
    a[10:30, 50:90] = (235, 235, 235)  # digits
    # Chromatic fringes on the digits: orange, but only ~15% of a column
    # (real crops: <= 21%; the pin: 42-45%).
    a[12:18, 50:90:6] = (240, 120, 60)
    if with_icon:
        a[5:35, 10:22] = (240, 120, 40)  # solid orange pin
    return Image.fromarray(a)


def test_marker_icon_is_cropped_off():
    out = strip_marker_icon(_label(with_icon=True))
    assert 22 <= 100 - out.width <= 30  # pin and a small margin removed
    assert out.height == 40


def test_crop_without_icon_is_unchanged():
    img = _label(with_icon=False)
    assert strip_marker_icon(img) is img
