#!/usr/bin/env python3
"""
Signature scanner for SC Signature Scanner.
Detects signature values from Star Citizen screenshots using OCR.

Requires a scan region to be configured in Settings.

OCR engine: EasyOCR (deep learning).
- ~115 MB model download on first run (cached to ~/.EasyOCR/model/).
- Loads on a background thread during the splash so app boot stays smooth.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Any, Optional, Tuple
from PIL import Image
import numpy as np

import paths

import region_selector

# Pillow 10.0.0+ removed ANTIALIAS, but EasyOCR still uses it
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.Resampling.LANCZOS

HAS_EASYOCR = False
EASYOCR_ERROR: Optional[str] = None

try:
    import easyocr
    HAS_EASYOCR = True
except (ImportError, OSError) as e:
    EASYOCR_ERROR = str(e)
    print(f"Warning: EasyOCR not available. OCR disabled. Error: {e}")

# Signature validity range
MIN_SIGNATURE = 100
MAX_SIGNATURE = 200_000

# OCR image processing
MIN_OCR_DIMENSION = 64       # upscale threshold (pixels)

# Signature matching
MAX_CLUSTER_COUNT = 100      # sanity cap on rock count (value / base signature)

# OCR digit look-alikes. At the ~20px digit height the SC HUD renders, EasyOCR
# confuses these glyphs frame-to-frame (e.g. 16,960 read as 18,960 / 18,680).
# Used by _try_substitution_correction to snap a misread back to a valid
# signature — but ONLY when the substitution resolves to a single valid
# signature, so an ambiguous misread is refused rather than guessed.
_OCR_CONFUSABLE_PAIRS = [
    ("0", "8"), ("0", "6"), ("0", "9"),
    ("1", "7"), ("1", "4"),
    ("2", "7"),
    ("3", "8"), ("3", "5"), ("3", "9"),
    ("5", "6"), ("5", "8"),
    ("6", "8"), ("6", "9"),
    ("8", "9"),
]
_OCR_CONFUSIONS: dict[str, set[str]] = {}
for _a, _b in _OCR_CONFUSABLE_PAIRS:
    _OCR_CONFUSIONS.setdefault(_a, set()).add(_b)
    _OCR_CONFUSIONS.setdefault(_b, set()).add(_a)

# Image loading
MAX_IMAGE_FILE_SIZE = 50 * 1024 * 1024  # 50 MB — guard against decompression bombs


class SignatureScanner:
    """Scans screenshots for signature values using EasyOCR."""
    
    def __init__(self, db_path: Path):
        self.db = self._load_database(db_path)
        self._build_lookups()

        self.debug_mode = False
        self.debug_dir = paths.get_debug_path()
        self.last_debug_info = {}
        self._debug_prefix = ""  # Timestamp prefix for debug files

        self.engine_name: str = "EasyOCR"

        # EasyOCR reader - lazily initialized on first use (the splash
        # masks the load via a background thread).
        self._ocr_reader: Optional[Any] = None  # easyocr.Reader when available
        self._ocr_initialized = False
        self._ocr_init_error: Optional[str] = None

        # Callback for model download progress (set by UI)
        self.on_model_download_start: Optional[Callable[[], None]] = None
        self.on_model_download_complete: Optional[Callable[[], None]] = None
    
    def _get_ocr_reader(self) -> Optional[Any]:
        """Get or initialize the EasyOCR reader.
        
        Lazy initialization allows:
        1. Faster app startup
        2. Model download on first actual use
        3. UI can hook download progress callbacks
        
        Returns:
            EasyOCR Reader instance, or None if initialization failed
        """
        if self._ocr_initialized:
            return self._ocr_reader

        if not HAS_EASYOCR:
            self._ocr_init_error = EASYOCR_ERROR or "EasyOCR not installed"
            self._ocr_initialized = True
            return None

        try:
            # Notify UI that download may start
            if self.on_model_download_start:
                self.on_model_download_start()

            if self.debug_mode:
                print("[DEBUG] Initializing EasyOCR reader...")

            # Initialize reader
            # - gpu=False: Use CPU (works everywhere, GPU auto-detected if available)
            # - verbose=False: Suppress download progress to stdout
            self._ocr_reader = easyocr.Reader(
                ['en'],
                gpu=False,  # CPU mode - works universally
                verbose=self.debug_mode
            )
            
            if self.debug_mode:
                print("[DEBUG] EasyOCR reader initialized successfully")
            
            # Notify UI that download/init is complete
            if self.on_model_download_complete:
                self.on_model_download_complete()
            
        except Exception as e:
            self._ocr_init_error = str(e)
            self._ocr_reader = None
            if self.debug_mode:
                print(f"[DEBUG] EasyOCR initialization failed: {e}")
        
        self._ocr_initialized = True
        return self._ocr_reader
    
    def is_ocr_available(self) -> Tuple[bool, Optional[str]]:
        """Check if OCR is available.

        Returns:
            Tuple of (is_available, error_message)
        """
        if not HAS_EASYOCR:
            return False, EASYOCR_ERROR or "EasyOCR not installed"

        if self._ocr_initialized and self._ocr_init_error:
            return False, self._ocr_init_error

        return True, None
    
    def _debug_path(self, filename: str) -> Path:
        """Generate debug file path with timestamp prefix.
        
        Args:
            filename: Base filename like "00_original.png"
            
        Returns:
            Full path like debug_output/20260112_143052_00_original.png
        """
        return self.debug_dir / f"{self._debug_prefix}{filename}"
    
    def scan_image(self, image_path: Path) -> Optional[Dict[str, Any]]:
        """Scan an image file for signature values."""
        available, error = self.is_ocr_available()
        if not available:
            return {'error': f'OCR not available: {error}'}

        img = self._load_image(image_path)
        if img is None:
            return {'error': f'Failed to load image: {image_path.name}'}

        self.last_debug_info = {
            'image_path': str(image_path),
            'debug_files': [],
            'method': None,
        }
        return self.scan_pil_image(img)

    def scan_pil_image(
        self,
        img: Image.Image,
        *,
        region: Optional[Tuple[int, int, int, int]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Scan an in-memory image.

        Args:
            img: The image to scan (already loaded, full RGB).
            region: Explicit (x1, y1, x2, y2) within `img`. When provided, this
                overrides the on-disk scan_region.json and is used as-is — live
                mode passes (0, 0, w, h) because the image is already the ROI.
                When None, falls back to region_selector.load_region().

        Returns:
            Same shape as the old scan_image: a dict with 'signature', 'matches',
            'method', 'ocr_confidence', etc., or {'error': ...} on failure.
        """
        available, error = self.is_ocr_available()
        if not available:
            return {'error': f'OCR not available: {error}'}

        # Generate timestamp prefix for this scan session (preserves existing
        # debug-file behaviour for file-based scans).
        self._debug_prefix = datetime.now().strftime("%Y%m%d_%H%M%S_")
        # Ensure the bookkeeping dict exists even when scan_pil_image is called
        # directly (e.g. by live mode), not via scan_image.
        if not isinstance(getattr(self, 'last_debug_info', None), dict):
            self.last_debug_info = {'debug_files': [], 'method': None}
        else:
            self.last_debug_info.setdefault('debug_files', [])
            self.last_debug_info.setdefault('method', None)

        try:
            width, height = img.size
            self.last_debug_info['image_size'] = (width, height)

            if self.debug_mode:
                try:
                    self.debug_dir.mkdir(parents=True, exist_ok=True)
                    print(f"[DEBUG] Writing debug output to: {self.debug_dir}")
                except OSError as e:
                    print(f"[DEBUG] Could not create debug dir {self.debug_dir}: {e}")
                    raise
                img.save(self._debug_path("00_original.png"))
                self.last_debug_info['debug_files'].append(
                    f"{self._debug_prefix}00_original.png"
                )

            # Determine the region to scan: explicit > stored > error.
            if region is not None:
                x1, y1, x2, y2 = region
            elif region_selector.is_configured():
                x1, y1, x2, y2 = region_selector.load_region()
            else:
                return {'error': 'Scan region not configured. Define it in Settings.'}

            # Clamp inside image (preserved from the old _scan_with_fixed_region).
            x1 = max(0, min(x1, width - 1))
            y1 = max(0, min(y1, height - 1))
            x2 = max(0, min(x2, width))
            y2 = max(0, min(y2, height))
            if x2 <= x1 or y2 <= y1:
                return {'error': 'Invalid scan region (degenerate after clamp)'}

            if self.debug_mode:
                print(f"[DEBUG] Using fixed region: ({x1}, {y1}) to ({x2}, {y2})")

            result = self._scan_region(img, x1, y1, x2, y2, 'fixed')
            if result:
                self.last_debug_info['method'] = 'fixed_region'
                return result
            if self.debug_mode:
                print("[DEBUG] Fixed region scan failed - no signature found")
            return {'error': 'No signature detected in scan region'}

        except Exception as e:
            if self.debug_mode:
                import traceback
                with open(self._debug_path("99_error.txt"), 'w') as f:
                    f.write(traceback.format_exc())
            return {'error': str(e)}

    def _scan_region(self, img: Image.Image, x1: int, y1: int, x2: int, y2: int,
                     method: str) -> Optional[Dict[str, Any]]:
        """Scan a specific region for signature values."""
        if self.debug_mode:
            from PIL import ImageDraw
            debug_img = img.copy()
            draw = ImageDraw.Draw(debug_img)
            draw.rectangle([x1, y1, x2, y2], outline='#00FF00', width=3)
            debug_img.save(self._debug_path(f"02_{method}_region.png"))
            self.last_debug_info['debug_files'].append(f"{self._debug_prefix}02_{method}_region.png")
        
        # Crop region
        sig_crop = img.crop((x1, y1, x2, y2))
        
        if self.debug_mode:
            sig_crop.save(self._debug_path("03_sig_crop.png"))
            self.last_debug_info['debug_files'].append(f"{self._debug_prefix}03_sig_crop.png")
        
        # Enhance and OCR
        enhanced = self._enhance_for_ocr(sig_crop)
        
        if self.debug_mode:
            # Save enhanced version for debugging
            enhanced_pil = Image.fromarray(enhanced)
            enhanced_pil.save(self._debug_path("04_enhanced.png"))
            self.last_debug_info['debug_files'].append(f"{self._debug_prefix}04_enhanced.png")
        
        # Run OCR
        signatures, ocr_text, confidence = self._ocr_signature(enhanced)
        
        if self.debug_mode:
            print(f"[DEBUG] OCR: text='{ocr_text}' signatures={signatures} confidence={confidence:.2f}")
            with open(self._debug_path("99_summary.txt"), 'w') as f:
                f.write(f"Method: {method}\n")
                f.write(f"Region: ({x1}, {y1}) - ({x2}, {y2})\n")
                f.write(f"OCR engine: {self.engine_name}\n")
                f.write(f"OCR text: {ocr_text}\n")
                f.write(f"OCR confidence: {confidence:.2f}\n")
                f.write(f"Signatures found: {signatures}\n")
        
        if signatures:
            # _ocr_signature orders by detection confidence; trusting the
            # most confident read beats max(), which let stray digits win.
            primary_sig = signatures[0]
            matches = self.match_signature(primary_sig)
            return {
                'signature': primary_sig,
                'all_signatures': list(set(signatures)),
                'matches': matches,
                'method': method,
                'ocr_confidence': confidence,
                'debug': self.last_debug_info if self.debug_mode else None
            }
        
        return None
    
    def _enhance_for_ocr(self, img: Image.Image) -> np.ndarray:
        """Enhance image for OCR.

        Upscales small crops so EasyOCR has enough pixels to work with. Note we
        deliberately do NOT run a connected-component "punctuation filter" here:
        the SC HUD renders bright text on a dark background, so an Otsu/INV
        threshold treats the background as foreground and the step at best did
        nothing and at worst erased digit pixels — measured to suppress
        otherwise-recoverable reads (e.g. 16,960). Separator misreads are
        handled downstream in _extract_signatures instead.

        Args:
            img: Cropped region containing signature

        Returns:
            Numpy array (RGB) ready for EasyOCR
        """
        # Ensure RGB
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # Upscale small regions for better detection
        if img.width < MIN_OCR_DIMENSION or img.height < MIN_OCR_DIMENSION:
            scale = max(MIN_OCR_DIMENSION // min(img.width, img.height), 2)
            img = img.resize(
                (img.width * scale, img.height * scale),
                Image.Resampling.LANCZOS
            )

        return np.array(img)

    def _load_database(self, db_path: Path) -> Dict[str, Any]:
        """Load signature database."""
        if db_path.exists():
            with open(db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def _build_lookups(self):
        """Build lookup tables for fast matching from the database."""
        self.signature_lookup = {}
        for sig_str, desc in self.db.get('signature_lookup', {}).items():
            try:
                self.signature_lookup[int(sig_str)] = desc
            except ValueError:
                pass

        minables = self.db.get('minables', {})

        # Build minable signatures from space deposits (asteroids) and surface deposits
        self.minable_signatures = {}
        # Also build rock display names and signature-to-rock-type mapping
        self.rock_display_names = {}
        self.signature_to_rock_type = {}

        # SC 4.7+ per-mineral signature system.
        # Each tier (legendary/epic/rare/uncommon/common) contains {mineral: signature} pairs.
        # The signature uniquely identifies the mineral — applies to both asteroids and surface rocks.
        ship_mining = minables.get('ship_mining', {})
        for tier, tier_data in ship_mining.items():
            if tier.startswith('_') or not isinstance(tier_data, dict):
                continue
            for mineral, sig in tier_data.items():
                if mineral.startswith('_'):
                    continue
                if isinstance(sig, (int, float)):
                    sig = int(sig)
                    display = f'{mineral} ({tier.capitalize()})'
                    self.minable_signatures[sig] = {
                        'name': display,
                        'mineral': mineral,
                        'tier': tier,
                        'category': 'ship_mining',
                    }
                    self.rock_display_names[mineral] = display
                    # Rock type key for pricing lookup (mineral name, uppercase)
                    self.signature_to_rock_type[sig] = (mineral.upper(), 'ship_mining')

        # Ground deposits
        ground = minables.get('ground_deposits', {})
        small_config = ground.get('small', {})
        large_config = ground.get('large', {})

        self.ground_deposit_small_base = small_config.get('_base_signature', 120)
        self.ground_deposit_large_base = large_config.get('_base_signature', 620)
        self.ground_deposit_minerals = ground.get('minerals', [])

        # Salvage — panels and debris types
        salvage = self.db.get('salvage', {})
        panels_config = salvage.get('panels', {})
        self.salvage_per_panel = panels_config.get('_base_signature', 2000)

        # Debris types: list of (base_sig, display_name)
        self.salvage_debris_types: list[tuple[int, str]] = []
        for debris_data in salvage.get('debris', {}).values():
            base_sig = debris_data.get('_base_signature', 0)
            name = debris_data.get('_name', 'Wreck Debris')
            if base_sig > 0:
                self.salvage_debris_types.append((base_sig, name))

        # Known base signatures (collected from all sources) for OCR correction
        self.known_base_signatures = set(self.signature_to_rock_type.keys())
        self.known_base_signatures.add(self.ground_deposit_small_base)
        self.known_base_signatures.add(self.ground_deposit_large_base)
        self.known_base_signatures.add(self.salvage_per_panel)
        for base_sig, _ in self.salvage_debris_types:
            self.known_base_signatures.add(base_sig)
    
    def _ocr_signature(self, img_array: np.ndarray) -> Tuple[List[int], str, float]:
        """OCR the image and extract signature numbers.

        Returns:
            Tuple of (list of signature values, raw OCR text, mean confidence 0..1).
        """
        reader = self._get_ocr_reader()
        if reader is None:
            return [], f"OCR ERROR: {self._ocr_init_error}", 0.0

        try:
            # EasyOCR with digit allowlist for maximum accuracy
            # Note: Comma removed from allowlist - was causing misreads like "7,480" -> "7,4480"
            # Pattern 2 in _extract_signatures handles plain digit sequences
            results = reader.readtext(
                img_array,
                allowlist='0123456789.',
                paragraph=False,  # Don't merge into paragraphs
                detail=1,  # Return bounding boxes + confidence
            )

            if self.debug_mode:
                print(f"[DEBUG] EasyOCR raw results: {results}")

            # detection = (bbox, text, confidence)
            detections = [(d[1], d[2]) for d in results if len(d) >= 3]

            combined_text = ' '.join(text for text, _ in detections)
            confidences = [conf for _, conf in detections]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            # Most confident detection first, so callers can trust
            # signatures[0]; the combined text goes last to catch a number
            # EasyOCR split across two boxes.
            by_confidence = sorted(detections, key=lambda d: d[1], reverse=True)
            signatures: list[int] = []
            for text in [t for t, _ in by_confidence] + [combined_text]:
                for sig in self._extract_signatures(text):
                    if sig not in signatures:
                        signatures.append(sig)

            return signatures, combined_text, avg_confidence

        except Exception as e:
            return [], f"OCR ERROR: {e}", 0.0
    
    def _extract_signatures(self, text: str) -> List[int]:
        """Extract valid signature values from OCR text.
        
        Args:
            text: Raw OCR text
            
        Returns:
            List of valid signature integers
        """
        seen: set[int] = set()
        raw_values: list[int] = []

        def _add(value: int) -> None:
            if self._is_valid_signature(value) and value not in seen:
                seen.add(value)
                raw_values.append(value)

        # Pattern 1: Numbers with comma separators (e.g., "1,850")
        for match in re.findall(r'(\d{1,3},\d{3})', text):
            try:
                _add(int(match.replace(',', '')))
            except ValueError:
                pass

        # Pattern 2: Numbers with period separators (e.g., "6.000" - European format or OCR misread)
        for match in re.findall(r'(\d{1,3}\.\d{3})', text):
            try:
                _add(int(match.replace('.', '')))
            except ValueError:
                pass

        # Pattern 3: Plain numbers (e.g., "1850" or "74400")
        for match in re.findall(r'(\d{3,6})', text):
            try:
                _add(int(match))
            except ValueError:
                pass
        
        # Validate and correct signatures
        signatures = []
        for value in raw_values:
            if self._is_exact_multiple(value):
                # Valid as-is
                signatures.append(value)
            else:
                # Try to correct: first a phantom digit (comma/period read as a
                # digit), then a single look-alike-digit substitution.
                corrected = self._try_correct_signature(value)
                if corrected is None:
                    corrected = self._try_substitution_correction(value)
                if corrected and corrected not in signatures:
                    if self.debug_mode:
                        print(f"[DEBUG] Signature corrected: {value} -> {corrected}")
                    signatures.append(corrected)
                elif self.debug_mode:
                    print(f"[DEBUG] Signature {value} invalid and uncorrectable")
        
        return signatures
    
    def _try_substitution_correction(self, value: int) -> Optional[int]:
        """Snap a misread to a valid signature via one look-alike-digit swap.

        At the small digit height the SC HUD renders, EasyOCR confuses glyphs
        like 6/8/9 — a steady 16,960 is read as 18,960 or 18,680 frame to frame.
        This tries every single substitution of a digit for one of its OCR
        look-alikes (`_OCR_CONFUSIONS`) and keeps only results that are valid
        exact multiples of a known base signature.

        The correction is returned ONLY when exactly one distinct valid
        signature results. If the misread maps to two or more valid signatures
        (e.g. 29,620 → 25,620 / 29,600 / 29,680) it is ambiguous and we refuse
        to guess — returning None avoids fabricating a false lock. Pair this
        with temporal voting so a unique correction must also recur.

        Args:
            value: Invalid signature value to attempt to correct.

        Returns:
            The single valid signature reachable by one look-alike swap, or
            None if zero or multiple candidates result.
        """
        value_str = str(value)
        candidates: set[int] = set()

        for i, ch in enumerate(value_str):
            for repl in _OCR_CONFUSIONS.get(ch, ()):
                cand_str = value_str[:i] + repl + value_str[i + 1 :]
                if cand_str[0] == "0":  # no leading zeros
                    continue
                cand = int(cand_str)
                if self._is_valid_signature(cand) and self._is_exact_multiple(cand):
                    candidates.add(cand)

        if len(candidates) == 1:
            return next(iter(candidates))
        if self.debug_mode and candidates:
            print(
                f"[DEBUG] Substitution for {value} ambiguous: "
                f"{sorted(candidates)} — refusing to guess"
            )
        return None

    def _is_valid_signature(self, value: int) -> bool:
        """Check if a value is in valid signature range.
        
        Args:
            value: Integer to validate
            
        Returns:
            True if value could be a valid signature
        """
        return MIN_SIGNATURE <= value <= MAX_SIGNATURE
    
    def _is_exact_multiple(self, value: int) -> bool:
        """Check if value is an exact multiple of any known base signature.
        
        Args:
            value: Signature value to check
            
        Returns:
            True if value divides evenly by any known base (with reasonable count)
        """
        for base in self.known_base_signatures:
            if value % base == 0:
                count = value // base
                if 1 <= count <= MAX_CLUSTER_COUNT:
                    return True
        return False
    
    def _try_correct_signature(self, value: int) -> Optional[int]:
        """Try to correct an invalid signature by removing phantom digits.
        
        OCR sometimes reads comma/period separators as digits:
        - "7,400" -> "74400" (comma read as 4)
        - "6.000" -> "60000" (period read as 0)
        
        This method tries removing each digit and checks if the result
        is a valid exact multiple of a known base signature.
        
        Args:
            value: Invalid signature value to correct
            
        Returns:
            Corrected value if found, None otherwise
        """
        value_str = str(value)
        
        # Only try correction for values that are "too large" (5+ digits)
        # Phantom digit insertion makes 4-digit numbers into 5-digit
        if len(value_str) < 5:
            return None
        
        # Try removing each digit position
        candidates = []
        for i in range(len(value_str)):
            corrected_str = value_str[:i] + value_str[i+1:]
            if corrected_str and corrected_str[0] != '0':  # No leading zeros
                try:
                    corrected = int(corrected_str)
                    if self._is_valid_signature(corrected) and self._is_exact_multiple(corrected):
                        candidates.append(corrected)
                except ValueError:
                    pass
        
        if candidates:
            # Prefer candidate with lowest count (more realistic)
            # e.g., 7400 = 4× M-type (1850) is more likely than 7440 = 62× small ground (120)
            def min_count(v):
                counts = [v // b for b in self.known_base_signatures if v % b == 0 and 1 <= v // b <= 100]
                return min(counts) if counts else 999
            
            best = min(candidates, key=min_count)
            if self.debug_mode:
                print(f"[DEBUG] Corrected {value} -> candidates: {candidates} -> best: {best} (count={min_count(best)})")
            return best
        
        return None
    
    def match_signature(self, signature: int) -> List[Dict[str, Any]]:
        """Match a signature value to possible targets, including estimated values."""
        matches = []
        
        # Check for known signature (asteroid types, deposits)
        if signature in self.signature_lookup:
            match_data = {
                'type': 'known',
                'name': self.signature_lookup[signature],
                'signature': signature,
                'confidence': 1.0
            }
            
            if signature in self.signature_to_rock_type:
                rock_type, category = self.signature_to_rock_type[signature]
                match_data['rock_type'] = rock_type
                match_data['category'] = category

            matches.append(match_data)
        
        # Check for salvage panels — exact multiples of 2000
        if signature >= self.salvage_per_panel and signature % self.salvage_per_panel == 0:
            panels = signature // self.salvage_per_panel
            matches.append({
                'type': 'salvage',
                'category': 'salvage',
                'name': f'Salvage Panels ({panels}×)',
                'panels': panels,
                'signature': signature,
                'confidence': 1.0,
            })

        # Check for salvage debris types (sized hull pieces from SC 4.7)
        for base_sig, debris_name in self.salvage_debris_types:
            if signature >= base_sig and signature % base_sig == 0:
                count = signature // base_sig
                if 1 <= count <= 20:
                    matches.append({
                        'type': 'salvage_debris',
                        'category': 'salvage_debris',
                        'name': f'{debris_name} ({count}×)',
                        'count': count,
                        'base_signature': base_sig,
                        'signature': signature,
                        'confidence': 1.0,
                    })
        
        # Check for ground deposits (small=120, large=620)
        # These are 100% single mineral per cluster
        if self.ground_deposit_small_base > 0 and signature % self.ground_deposit_small_base == 0:
            count = signature // self.ground_deposit_small_base
            if 1 <= count <= 50:  # Reasonable cluster size
                # Higher confidence for smaller counts
                confidence = 0.9 if count <= 5 else max(0.6, 0.85 - count * 0.01)
                matches.append({
                    'type': 'ground_deposit',
                    'name': f'Small Ground Deposit ({count}x)',
                    'count': count,
                    'base_signature': self.ground_deposit_small_base,
                    'signature': signature,
                    'confidence': confidence,
                    'category': 'ground_deposits',
                    'variant': 'small',
                    'mining_method': 'FPS/Hand mining',
                    'single_mineral': True,
                    'possible_minerals': self.ground_deposit_minerals.copy()
                })
        
        if self.ground_deposit_large_base > 0 and signature % self.ground_deposit_large_base == 0:
            count = signature // self.ground_deposit_large_base
            if 1 <= count <= 30:  # Reasonable cluster size for large deposits
                # Higher confidence for smaller counts
                confidence = 0.9 if count <= 3 else max(0.6, 0.85 - count * 0.02)
                matches.append({
                    'type': 'ground_deposit',
                    'name': f'Large Ground Deposit ({count}x)',
                    'count': count,
                    'base_signature': self.ground_deposit_large_base,
                    'signature': signature,
                    'confidence': confidence,
                    'category': 'ground_deposits',
                    'variant': 'large',
                    'mining_method': 'ROC/Vehicle mining',
                    'single_mineral': True,
                    'possible_minerals': self.ground_deposit_minerals.copy()
                })
        
        # Check ship-mined deposits (asteroids and surface rocks — per-mineral signatures)
        for base_sig, info in self.minable_signatures.items():
            if base_sig == 0:
                continue
            if signature % base_sig == 0:
                count = signature // base_sig
                if 1 <= count <= 100:
                    confidence = 1.0 if count == 1 else max(0.5, 0.9 - count * 0.01)

                    display_name = info['name']
                    if count > 1:
                        display_name = f"{display_name} ×{count}"

                    match_data = {
                        'type': 'ship_mining',
                        'category': 'ship_mining',
                        'name': display_name,
                        'mineral': info.get('mineral', info['name']),
                        'tier': info.get('tier', ''),
                        'count': count,
                        'base_signature': base_sig,
                        'signature': signature,
                        'confidence': confidence,
                        'single_mineral': True,
                    }

                    matches.append(match_data)
        
        # Sort by confidence
        matches.sort(key=lambda x: x.get('confidence', 0), reverse=True)
        
        # Remove duplicates
        seen = set()
        unique = []
        for m in matches:
            key = (m.get('type'), m.get('name'))
            if key not in seen:
                seen.add(key)
                unique.append(m)
        
        return unique
    
    def enable_debug(self, enable: bool = True, output_dir: Optional[Path] = None):
        """Enable debug mode."""
        self.debug_mode = enable
        if output_dir:
            self.debug_dir = output_dir
    
    def _load_image(self, image_path: Path) -> Optional[Image.Image]:
        """Load an image, enforcing a file-size cap and releasing the file handle immediately."""
        try:
            if image_path.stat().st_size > MAX_IMAGE_FILE_SIZE:
                return None
            img = Image.open(image_path)
            img.load()  # force full read into memory; closes the file handle
            return img
        except Exception:
            return None
