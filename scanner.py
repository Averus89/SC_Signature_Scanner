#!/usr/bin/env python3
"""
Signature scanner for SC Signature Scanner.
Detects signature values from Star Citizen screenshots using OCR.

Requires a scan region to be configured in Settings.

OCR Engine: EasyOCR (deep learning based)
- First run downloads ~115MB of model files
- Subsequent runs use cached models locally
- No external binary dependencies
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Any, Optional, Tuple
from PIL import Image
import numpy as np

import cv2

import paths

import region_selector

# EasyOCR import - lazy initialization
HAS_EASYOCR = False
EASYOCR_ERROR = None

# Pillow 10.0.0+ removed ANTIALIAS, but EasyOCR still uses it
# Add compatibility shim before importing easyocr
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.Resampling.LANCZOS

try:
    import easyocr
    HAS_EASYOCR = True
except ImportError as e:
    EASYOCR_ERROR = str(e)
    print(f"Warning: EasyOCR not installed. OCR disabled. Error: {e}")

# Signature validity range
MIN_SIGNATURE = 100
MAX_SIGNATURE = 200_000

# OCR image processing
MIN_OCR_DIMENSION = 64       # upscale threshold (pixels)
MIN_COMPONENT_AREA = 50      # smallest blob kept — removes commas/periods
MAX_COMPONENT_AREA_SMALL = 30  # threshold for 'small' component filter pass
MAX_COMPONENT_AREA_LARGE = 100  # threshold for 'large' component filter pass

# Signature matching
MAX_CLUSTER_COUNT = 100      # sanity cap on rock count (value / base signature)

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
        
        # EasyOCR reader - lazily initialized on first use
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
        """Scan an image for signature values.
        
        Requires fixed scan region (configured in Settings).
        """
        # Check OCR availability
        available, error = self.is_ocr_available()
        if not available:
            return {'error': f'OCR not available: {error}'}
        
        self.last_debug_info = {
            'image_path': str(image_path),
            'debug_files': [],
            'method': None
        }
        
        # Generate timestamp prefix for this scan session
        self._debug_prefix = datetime.now().strftime("%Y%m%d_%H%M%S_")
        
        try:
            img = self._load_image(image_path)
            if img is None:
                return {'error': f'Failed to load image: {image_path.name}'}
            
            width, height = img.size
            self.last_debug_info['image_size'] = (width, height)
            
            if self.debug_mode:
                self.debug_dir.mkdir(exist_ok=True)
                img.save(self._debug_path("00_original.png"))
                self.last_debug_info['debug_files'].append(f"{self._debug_prefix}00_original.png")
            
            # Check for fixed region
            if region_selector.is_configured():
                result = self._scan_with_fixed_region(img, width, height)
                if result:
                    self.last_debug_info['method'] = 'fixed_region'
                    return result
                if self.debug_mode:
                    print("[DEBUG] Fixed region scan failed - no signature found")
                return {'error': 'No signature detected in scan region'}
            
            # No scan region configured
            return {'error': 'Scan region not configured. Define it in Settings.'}
            
        except Exception as e:
            if self.debug_mode:
                import traceback
                with open(self._debug_path("99_error.txt"), 'w') as f:
                    f.write(traceback.format_exc())
            return {'error': str(e)}
    
    def _scan_with_fixed_region(self, img: Image.Image, width: int, height: int) -> Optional[Dict[str, Any]]:
        """Scan using pre-configured fixed region."""
        region = region_selector.load_region()
        if not region:
            return None
        
        x1, y1, x2, y2 = region
        
        # Validate region is within image bounds
        x1 = max(0, min(x1, width - 1))
        y1 = max(0, min(y1, height - 1))
        x2 = max(0, min(x2, width))
        y2 = max(0, min(y2, height))
        
        if x2 <= x1 or y2 <= y1:
            if self.debug_mode:
                print(f"[DEBUG] Invalid fixed region: ({x1}, {y1}) to ({x2}, {y2})")
            return None
        
        if self.debug_mode:
            print(f"[DEBUG] Using fixed region: ({x1}, {y1}) to ({x2}, {y2})")
        
        return self._scan_region(img, x1, y1, x2, y2, "fixed")
    
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
                f.write(f"OCR engine: EasyOCR\n")
                f.write(f"OCR text: {ocr_text}\n")
                f.write(f"OCR confidence: {confidence:.2f}\n")
                f.write(f"Signatures found: {signatures}\n")
        
        if signatures:
            primary_sig = max(signatures)
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
        
        Processing steps:
        1. Convert to RGB numpy array
        2. Upscale small regions for better detection
        3. Remove small connected components (commas, periods, noise)
           - Commas/periods are ~5-20 pixels, digits are 100+ pixels
           - This prevents OCR from misreading punctuation as digits
        
        Args:
            img: Cropped region containing signature
        
        Returns:
            Numpy array (RGB) ready for EasyOCR
        """
        # Ensure RGB
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Upscale small regions for better detection
        scale = 1
        if img.width < MIN_OCR_DIMENSION or img.height < MIN_OCR_DIMENSION:
            scale = max(MIN_OCR_DIMENSION // min(img.width, img.height), 2)
            img = img.resize(
                (img.width * scale, img.height * scale),
                Image.Resampling.LANCZOS
            )
        
        img_array = np.array(img)
        
        # Remove small connected components (commas, periods, noise)
        # This prevents OCR from misreading punctuation as digits
        img_array = self._remove_small_components(img_array)
        
        return img_array
    
    def _remove_small_components(self, img_array: np.ndarray, min_area: int = MIN_COMPONENT_AREA) -> np.ndarray:
        """Remove small connected components from image.
        
        Commas and periods are tiny (~5-20 pixels) compared to digits (100+ pixels).
        By removing small components, we prevent OCR from misreading punctuation.
        
        Args:
            img_array: RGB numpy array
            min_area: Minimum component area to keep (pixels). Default 50.
        
        Returns:
            Cleaned RGB numpy array with small components removed
        """
        # Convert to grayscale
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        
        # Binary threshold - find dark elements (text) on light background
        # Use adaptive threshold for varying backgrounds
        # THRESH_BINARY_INV: dark pixels become white (foreground)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Find connected components
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary, connectivity=8)
        
        # Create mask of components to keep (large enough to be digits)
        mask = np.zeros(binary.shape, dtype=np.uint8)
        
        removed_count = 0
        kept_count = 0
        
        for i in range(1, num_labels):  # Skip background (label 0)
            area = stats[i, cv2.CC_STAT_AREA]
            if area >= min_area:
                # Keep this component
                mask[labels == i] = 255
                kept_count += 1
            else:
                removed_count += 1
        
        if self.debug_mode:
            print(f"[DEBUG] Component filter: kept {kept_count}, removed {removed_count} (min_area={min_area})")
        
        # Apply mask to original image
        # Where mask is 0 (removed components), replace with background color
        # Estimate background as median color of non-text pixels
        bg_mask = binary == 0  # Original background pixels
        if np.any(bg_mask):
            bg_color = np.median(img_array[bg_mask], axis=0).astype(np.uint8)
        else:
            bg_color = np.array([128, 128, 128], dtype=np.uint8)  # Fallback gray
        
        # Create output image
        result = img_array.copy()
        
        # Where we removed components (mask is 0 but binary had content), fill with background
        removed_pixels = (binary == 255) & (mask == 0)
        result[removed_pixels] = bg_color
        
        if self.debug_mode and removed_count > 0:
            # Save debug image showing what was removed
            debug_removed = img_array.copy()
            debug_removed[removed_pixels] = [255, 0, 0]  # Red for removed pixels
            debug_pil = Image.fromarray(debug_removed)
            debug_pil.save(self._debug_path("04a_removed_components.png"))
            self.last_debug_info['debug_files'].append(f"{self._debug_prefix}04a_removed_components.png")
        
        return result
    
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
        
        Args:
            img_array: RGB numpy array to OCR
        
        Returns:
            Tuple of (list of signature values, raw OCR text, confidence)
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
            
            # Extract text and confidence
            texts = []
            confidences = []
            
            for detection in results:
                # detection = (bbox, text, confidence)
                if len(detection) >= 3:
                    bbox, text, conf = detection[0], detection[1], detection[2]
                    texts.append(text)
                    confidences.append(conf)
            
            combined_text = ' '.join(texts)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            # Extract signature values
            signatures = self._extract_signatures(combined_text)
            
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
                # Try to correct (phantom digit from comma/period separator)
                corrected = self._try_correct_signature(value)
                if corrected and corrected not in signatures:
                    if self.debug_mode:
                        print(f"[DEBUG] Signature corrected: {value} -> {corrected}")
                    signatures.append(corrected)
                elif self.debug_mode:
                    print(f"[DEBUG] Signature {value} invalid and uncorrectable")
        
        return signatures
    
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
