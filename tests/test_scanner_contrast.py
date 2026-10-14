"""_normalize_contrast — dark text on light, stretched to the full range."""
import numpy as np

from scanner import SignatureScanner


def _crop(text_level: int, bg_level: int) -> np.ndarray:
    """A 40x100 crop whose 'text' is a thin bar covering ~15% of the pixels."""
    gray = np.full((40, 100), bg_level, np.uint8)
    gray[15:21, 10:90] = text_level
    return gray


def test_light_text_on_dark_is_inverted_to_dark_on_light():
    out = SignatureScanner._normalize_contrast(_crop(text_level=220, bg_level=20))
    assert out[0, 0] > out[17, 50]  # background lighter than text


def test_low_contrast_text_over_bright_rock_is_stretched():
    """A label over a bright asteroid differs from its background by only a few
    levels; after normalization it must span (nearly) the full range."""
    out = SignatureScanner._normalize_contrast(_crop(text_level=200, bg_level=180))
    assert int(out[0, 0]) - int(out[17, 50]) > 200


def test_dark_text_on_light_keeps_polarity():
    out = SignatureScanner._normalize_contrast(_crop(text_level=30, bg_level=230))
    assert out[0, 0] > out[17, 50]


def test_flat_crop_is_returned_unchanged():
    flat = np.full((40, 100), 77, np.uint8)
    assert np.array_equal(SignatureScanner._normalize_contrast(flat), flat)
