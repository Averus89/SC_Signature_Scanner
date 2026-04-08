---
description: Cross-reference of red team and code review findings for SC Signature Scanner v4.2.1 — prioritised fix list for the v5.0.0 pass.
tags: [security, code-review, post-review, sc-signature-scanner]
audience: { human: 50, agent: 50 }
purpose: { findings: 70, plan: 30 }
---

# Post-Review Analysis — SC Signature Scanner v4.2.1

**Question**: What are the highest-confidence issues across both assessments, and in what order should they be fixed?

---

**Finding**: Two assessments agree on 4 issues (highest confidence). The red team found 5 findings; the code review found 2 blockers and 10 suggestions — 1 blocker is a crash bug not reachable by security analysis. Combined, the fix list is 18 items: 3 blockers, 7 security/correctness fixes, and 8 quality improvements. The crash bug (`import os` missing) is the single most urgent fix.

---

## Cross-Reference Table

| Finding | Red Team | Code Review | Confidence | Priority |
|---------|----------|-------------|------------|----------|
| `webbrowser.open(download_url)` no URL validation | F-001 (HIGH) | Confirmed present | **High** | P1 |
| `import os` missing — `os.startfile` crashes | — | B-001 (Blocking) | **Confirmed** | P1 |
| `_test_screenshot` freezes GUI during OCR | — | B-002 (Blocking) | **Confirmed** | P1 |
| Reparse point check missing on folder selection | F-002 (MEDIUM) | Confirmed present | **High** | P2 |
| EasyOCR auto-processes any dropped image, no size guard | F-003 (MEDIUM) | S-007 (file handle leak + no guard) | **High** | P2 |
| Broad `except Exception` in version_checker | F-005 (INFO) | Confirmed | Medium | P2 |
| 4-tuple/3-tuple update check disambiguation | — | S-004 | Medium | P2 |
| Dead `requests` dependency | F-004 (LOW) | S-010 | Medium | P3 |
| `HAS_CV2` flag but cv2 called unconditionally | — | S-001 | Medium | P3 |
| Splash creates separate `Tk()` root | — | S-003 | Low | P4 |
| Color constants duplicated in overlay.py | — | S-005 | Low | P4 |
| `RegolithTheme.create_card()` unused dead code | — | S-006 | Low | P4 |
| Magic numbers throughout | — | S-008 | Low | P4 |
| Dead files: pricing.py, regolith_api.py | Prior review | Confirmed | Low | P4 |
| Dead function: paths.py:get_asset_path() | Prior review | Confirmed | Low | P4 |
| `.webp`/`.bmp` missing from existing-file enumeration | — | Minor | Low | P4 |
| `primary_sig = max(signatures)` ignores OCR confidence | — | Minor | Low | P5 |
| Zero test coverage | Prior review | Confirmed | — | Deferred |

---

## Attack Chains

### Chain A — MITM → Arbitrary URI Execution

Requires only F-001. Network-positioned attacker intercepts GitHub API response, injects a `file://` URI as `html_url`, user clicks "Exit and Download" → OS executes arbitrary payload. Fix: validate URL scheme + host in `version_checker.py` and `theme.py:411`.

### Chain B — Missing `import os` + Debug Mode

B-001 is a standalone crash (not a security chain), but in context: debug mode writes OCR output to a folder that has no reparse point protection (F-002). Fixing both in the same pass closes the write-to-junction path entirely.

---

## Findings Unique to Red Team (no code-review counterpart)

| Finding | Note |
|---------|------|
| F-002 — Reparse point on folder selection | Code review focused on the file handle leak (S-007); didn't flag the junction attack angle specifically |

## Findings Unique to Code Review (no red-team counterpart)

| Finding | Note |
|---------|------|
| B-001 — `import os` missing | Not a security issue; pure correctness crash |
| B-002 — `_test_screenshot` blocks UI | Correctness / UX, not exploitable |
| S-001 — `HAS_CV2` guard inconsistency | Crash if OpenCV absent; low real-world impact (it's a hard dep) |
| S-003 — Splash `Tk()` root | Latent Tcl/Tk stability issue |
| S-007 — Image file handle leak | Partially overlaps F-003 (same location); adds Windows file-lock angle |

---

## Prioritised Fix List for v5.0.0

### P1 — Blockers (fix before any release)

1. **Add `import os`** to `main.py` imports — `main.py:23` (1 line)
2. **Thread the test screenshot button** — wrap `_on_new_screenshot` call in `threading.Thread` — `main.py:1196-1207` (~5 lines)
3. **Validate `download_url`** before `webbrowser.open()` — add `_validate_release_url()` to `version_checker.py`; apply in `theme.py:411` and `main.py:1444` (~20 lines, 3 locations)

### P2 — Security / Correctness

4. **Reparse point guard** on screenshot folder and debug folder — `main.py:1063`, `main.py:1330` (~10 lines, reuse pattern from ShaderCacheNuke)
5. **File size + eager load guard** in `scanner.py:_load_image` — add 50MB cap, call `img.load()` to close file handle (~8 lines)
6. **Narrow `except Exception`** in `version_checker.py:81` to `urllib.error.URLError`, `TimeoutError`, `json.JSONDecodeError`, `KeyError`
7. **Fix 4-tuple/3-tuple disambiguation** — split `_update_check_result` and `_update_check_error` into separate attributes — `main.py:1348-1376`

### P3 — Quality / Dependencies

8. **Remove `requests`** from `requirements.txt`
9. **Delete `pricing.py` and `regolith_api.py`** — confirmed no active imports
10. **Remove `paths.py:get_asset_path()`** — confirmed unused
11. **Fix `HAS_CV2` inconsistency** — make cv2 a hard dependency (it is in requirements.txt) and remove the guard, OR add guard inside `_enhance_for_ocr`

### P4 — Quality Cleanup

12. **Replace duplicate color constants** in `overlay.py` with `RegolithTheme.COLORS` references
13. **Extract magic numbers** to named constants (`MIN_SIGNATURE`, `MAX_SIGNATURE`, `MIN_OCR_DIMENSION`, etc.)
14. **Fix `.webp`/`.bmp` missing** from existing-file enumeration in `_start_monitoring` — `main.py:1080-1082`
15. **Remove or adopt `RegolithTheme.create_card()`** — dead code either way

### P5 — Deferred

- Splash `Tk()` root (S-003) — works in practice; fix in a dedicated UI session
- `primary_sig = max(signatures)` — design question, not a bug
- Test suite — separate workstream

---

## Items Not Fixed in This Pass (and Why)

| Item | Reason |
|------|--------|
| Test suite | Separate workstream; requires design decisions about test fixtures and OCR mocking |
| `main.py` monolith refactor | High effort, low risk; out of scope for security/quality hardening pass |
| `RegolithTheme.create_card()` adoption | UI refactor; would touch ~60 lines in `_create_ui`, risk of regressions |
| Splash `Tk()` root | Latent issue; works today; fix in dedicated session |

---

## Net Security Posture

**Before this pass**: 5 security findings (1 HIGH, 2 MEDIUM, 1 LOW, 1 INFO), 2 crash bugs, 10+ quality issues.

**After P1–P3 fixes**: 0 HIGH, 0 MEDIUM security findings. Crash bugs eliminated. Dead dependencies removed. Remaining items are quality/maintainability only.
