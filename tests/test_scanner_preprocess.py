"""OCR preprocessing and signature ordering in SignatureScanner."""
from unittest.mock import MagicMock

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import paths
from scanner import TARGET_OCR_HEIGHT, SignatureScanner


def _scanner() -> SignatureScanner:
    return SignatureScanner(paths.get_base_path() / "data" / "combat_analyst_db.json")


def _font() -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", 20)
    except OSError:
        return ImageFont.load_default(size=20)


def _render(text: str, fg, bg, size=(130, 26)) -> Image.Image:
    img = Image.new("RGB", size, bg)
    ImageDraw.Draw(img).text((4, 0), text, fill=fg, font=_font())
    return img


def _ink_columns(gray: np.ndarray) -> np.ndarray:
    """Columns that contain any dark (text) pixel."""
    return np.flatnonzero((gray < 128).any(axis=0))


def test_light_text_on_dark_is_inverted_to_dark_on_light():
    """SC HUD style input comes out with a light background."""
    out = _scanner()._enhance_for_ocr(_render("8060", (230, 240, 255), (15, 20, 30)))
    assert out.ndim == 2
    assert np.median(out) > 200  # background is light
    assert (out < 60).any()  # and text is dark


def test_crop_is_upscaled_towards_target_height():
    out = _scanner()._enhance_for_ocr(_render("8060", (255, 255, 255), (0, 0, 0)))
    assert out.shape[0] >= TARGET_OCR_HEIGHT


def test_comma_removed_regardless_of_polarity():
    """The punctuation filter must work on the light-on-dark HUD, not only
    on dark-on-light screenshots (it used to be a no-op on the HUD)."""
    s = _scanner()
    for fg, bg in [((230, 240, 255), (15, 20, 30)), ((15, 20, 30), (230, 240, 255))]:
        with_comma = s._enhance_for_ocr(_render("8,060", fg, bg))
        without = s._enhance_for_ocr(_render("8 060", fg, bg))
        assert _ink_columns(with_comma).size == _ink_columns(without).size


def test_holes_in_digits_survive():
    """Inner counters of 0/6/8 must not be filled in."""
    out = _scanner()._enhance_for_ocr(_render("808", (230, 240, 255), (15, 20, 30)))
    # Centre row of the first '8' crosses ink, a light counter, then ink.
    row = out[out.shape[0] // 3]
    ink = _ink_columns(out)
    segment = row[ink[0] : ink[0] + 30] < 128
    transitions = np.count_nonzero(np.diff(segment.astype(int)))
    assert transitions >= 2


def test_ocr_orders_signatures_by_confidence():
    """A low-confidence stray number must not beat the real reading."""
    s = _scanner()
    reader = MagicMock()
    reader.readtext.return_value = [
        (None, "74400", 0.20),  # stray / garbage read
        (None, "3540", 0.97),
    ]
    s._ocr_reader, s._ocr_initialized = reader, True
    signatures, _, _ = s._ocr_signature(np.zeros((10, 10), np.uint8))
    assert signatures[0] == 3540
