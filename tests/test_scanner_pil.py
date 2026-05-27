"""scan_pil_image entry point — accepts an in-memory PIL Image with optional explicit region."""
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

import paths
from scanner import SignatureScanner


def _make_signature_image(value: str, size=(220, 60)) -> Image.Image:
    """Render a synthetic SC-style signature image — black background, white digits."""
    img = Image.new("RGB", size, color=(0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Use the default bitmap font; pixel dimensions are deterministic across systems.
    draw.text((10, 10), value, fill=(255, 255, 255))
    return img


def test_scan_pil_image_accepts_explicit_region_and_extracts_signature():
    """Given an image and an explicit region covering the digits, signature is extracted."""
    db_path = paths.get_base_path() / "data" / "combat_analyst_db.json"
    scanner = SignatureScanner(db_path)

    img = _make_signature_image("3540")  # Beryl (Rare)

    # Stub OCR so the test doesn't depend on EasyOCR being initialized.
    with patch.object(
        scanner, "_ocr_signature", return_value=([3540], "3540", 0.95)
    ):
        result = scanner.scan_pil_image(img, region=(0, 0, img.width, img.height))

    assert result is not None
    assert result.get("signature") == 3540
    assert result.get("method") == "fixed"
    assert any(m.get("mineral", "").lower() == "beryl" for m in result.get("matches", []))


def test_scan_pil_image_returns_none_on_no_signatures():
    db_path = paths.get_base_path() / "data" / "combat_analyst_db.json"
    scanner = SignatureScanner(db_path)
    img = Image.new("RGB", (100, 30), color=(0, 0, 0))
    with patch.object(scanner, "_ocr_signature", return_value=([], "", 0.0)):
        result = scanner.scan_pil_image(img, region=(0, 0, 100, 30))
    # No signatures found → error dict, NOT None (consistent with file-mode behavior).
    assert result is not None
    assert "error" in result
    assert "No signature detected" in result["error"]


def test_scan_image_still_works_via_scan_pil_image(tmp_path: Path):
    """Existing scan_image API must keep working — it now delegates to scan_pil_image."""
    db_path = paths.get_base_path() / "data" / "combat_analyst_db.json"
    scanner = SignatureScanner(db_path)

    img = _make_signature_image("3540")
    img_path = tmp_path / "shot.png"
    img.save(img_path)

    # Provide a configured region so scan_image takes the fixed-region branch.
    with patch("scanner.region_selector") as mock_rs, \
         patch.object(scanner, "_ocr_signature", return_value=([3540], "3540", 0.95)):
        mock_rs.is_configured.return_value = True
        mock_rs.load_region.return_value = (0, 0, img.width, img.height)
        result = scanner.scan_image(img_path)

    assert result is not None
    assert result.get("signature") == 3540
