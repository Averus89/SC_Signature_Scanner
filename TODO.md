# SC Signature Scanner - Status

## Application Version: 3.4.0
## Database Version: 4.6 (for Star Citizen 4.6)
## OCR Engine: EasyOCR (deep learning)

## Mining Categories

### Space Deposits (Asteroids) ✓
Ship mining only (Prospector, MOLE). Mixed mineral composition.
| Type | Signature |
|------|-----------|
| I-type | 4000 |
| C-type | 4700 |
| S-type | 4720 |
| P-type | 4750 |
| M-type | 4850 |
| Q-type | 4870 |
| E-type | 4900 |

### Surface Deposits ✓
Ship mining only (Prospector, MOLE). Mixed mineral composition.
**Note:** All surface deposits share signature 4000 (same as I-type Asteroid). Cannot distinguish by signature alone. CIG bug as of SC 4.6.
| Type | Signature |
|------|-----------|
| All types | 4000 |

### Ground Deposits ✓
ROC or FPS mining. 100% single mineral per cluster.
**Note:** Both variants share signature 3000. CIG bug as of SC 4.6.

| Variant | Base Signature | Primary Method |
|---------|----------------|----------------|
| Small | 3000 | FPS/Hand mining |
| Large | 3000 | ROC/Vehicle mining |

**Minerals:** Hadanite, Dolivine, Aphorite, Beradom, Glacosite, Feynmaline, Jaclium

**Cluster Rules:**
- Each cluster spawns only ONE mineral type at 100% purity
- A mineral spawns as either small OR large deposits, never both in same cluster
- Small deposits can be vehicle-mined with skill
- Large deposits can be FPS-mined collaboratively

### Subsurface Deposits
- Status: NOT IN GAME
- Expected: Late 2026-2027
- First ship: Consolidated Outland Pioneer

### Salvage ✓
- Signature per panel: 2000

---

## Completed ✓
- [x] Database taxonomy finalized (v4.2)
- [x] All signature values verified from 2025 mining survey
- [x] Scanner updated for new ground deposit structure
- [x] PyInstaller build system configured
- [x] Path utilities for frozen exe
- [x] Test code removed
- [x] EasyOCR migration (replaced Tesseract)
- [x] Pillow 10.0.0+ compatibility (ANTIALIAS shim)
- [x] Overlay category matching fixed
- [x] Display names for asteroid types (C → "C-type Asteroid")
- [x] Regolith API integration (rock compositions from cache)
- [x] Pricing integration reads from Regolith cache (single source of truth)
- [x] Build script updated for PyInstaller _internal/ directory structure
- [x] Signature values updated for SC 4.5
- [x] Dead code cleanup (unused methods, unnecessary import guards)
- [x] Removed ship signatures (radar cross-section data) from database
- [x] Consolidated signature values to single source of truth (JSON database)
- [x] Removed hardcoded constants (KNOWN_BASE_SIGNATURES, ROCK_DISPLAY_NAMES, SIGNATURE_TO_ROCK_TYPE)
- [x] Minor cleanup: empty event handler, uninitialized attribute, local import

## In Progress
- [ ] Testing on fresh install

## Completed Recently
- [x] Version control setup (GitHub) - v3.0.0 pushed
- [x] Morphological filtering for OCR (removes commas/periods before scan)
- [x] Startup splash screen with loading status
- [x] Fixed overlay Tkinter crash (tuple pady)
- [x] Fixed NameError crash when easyocr import fails (type hint used `easyocr.Reader`)

## Known Issues
- Signature 4000 collides: I-type Asteroid and all Surface Deposits are indistinguishable
- Ground deposit variants (small/large) both share signature 3000
- These are CIG-side bugs, may be fixed in SC 4.7

## Future Work
- [ ] Re-verify all signature values after SC 4.7 patch
- [ ] GPU acceleration option for OCR (currently CPU-only)
