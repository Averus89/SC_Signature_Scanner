---
description: Adversarial security assessment of SC Signature Scanner v4.2.1 — what an attacker can exploit and how.
tags: [security, red-team, findings, sc-signature-scanner]
audience: { human: 65, agent: 35 }
purpose: { findings: 90, reference: 10 }
---

# Red Team Report — SC Signature Scanner v4.2.1

**Question**: What can an attacker exploit in SC Signature Scanner v4.2.1, and what is the realistic impact?

---

**Finding**: Three exploitable issues remain. The most significant is an unvalidated URL passed directly to `webbrowser.open()` in two locations — reachable by a network-positioned attacker who can intercept the GitHub API update check. The other two are lower-severity: the screenshot and debug folders accept reparse points (low impact since this app doesn't delete files), and EasyOCR auto-processes any image dropped into the monitored folder (low impact with current Pillow versions, dependency on future CVEs). Several issues flagged in prior code review have already been fixed and are documented as confirmed defences.

---

## Summary Table

| ID | Severity | Title | Location |
|----|----------|-------|----------|
| F-001 | HIGH | Unvalidated URL opened via `webbrowser.open()` | `main.py:1444`, `theme.py:411` |
| F-002 | MEDIUM | Screenshot and debug folders accept reparse points | `main.py:1063`, `main.py:1330` |
| F-003 | MEDIUM | EasyOCR auto-processes attacker-placed image files | `scanner.py:167` |
| F-004 | LOW | Dead `requests` dependency increases attack surface | `requirements.txt:25` |
| F-005 | INFO | Version check uses broad `except Exception` — hides failures | `version_checker.py:81` |

---

## Findings

### F-001 — HIGH: Unvalidated URL opened via `webbrowser.open()`

**Vulnerability**: Open Redirect / Arbitrary Protocol Invocation (CWE-601)

**Locations**:
- `main.py:1444` — inside `exit_and_download()` closure
- `theme.py:411` — `UpdateBanner._open_download()`

**Proof**:

```python
# version_checker.py:65 — URL extracted from GitHub API response, no validation
html_url = data.get('html_url', '')  # attacker controls this via MITM

# main.py:1444 — passed directly to browser
webbrowser.open(download_url)

# theme.py:411 — same URL stored and opened on user click
webbrowser.open(self.download_url)
```

The update check fires at app startup (`main.py:116`) over HTTPS to `api.github.com`. The `html_url` field from the response is stored and later handed to `webbrowser.open()` without validating that the scheme is `https://` and the host ends with `github.com`.

Attack path:
1. Position attacker on the network path (Wi-Fi AP, ISP-level, or DNS poisoning)
2. Return crafted JSON: `{"tag_name": "v99.0.0", "html_url": "file:///C:/Windows/System32/cmd.exe"}`
3. App determines update is available, stores the URL, presents the "Exit and Download" dialog
4. User clicks — `webbrowser.open('file:///C:/Windows/System32/cmd.exe')` executes on Windows

Alternative payloads that `webbrowser.open()` passes to the OS shell on Windows:
- `ms-settings:` URIs open system settings dialogs without prompting
- `file://` paths execute `.bat`, `.hta`, `.ps1` files directly in some Windows configurations
- Registered protocol handlers (Steam, Discord, etc.) can be invoked with attacker-controlled arguments

**Impact**: A network-positioned attacker causes the app to open an arbitrary OS URI on user interaction. On Windows, this can execute files or invoke protocol handlers with attacker-controlled arguments. No user privileges needed beyond being on the same network segment.

**Remediation**:

```python
# version_checker.py — add after extracting html_url
from urllib.parse import urlparse

def _validate_release_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return (
            parsed.scheme in ('https', 'http')
            and parsed.netloc.endswith('github.com')
        )
    except Exception:
        return False

# Then in check_for_updates():
if html_url and _validate_release_url(html_url):
    return (is_newer, latest_ver, html_url)
else:
    return (False, None, None)
```

The same validation is needed in `UpdateBanner._open_download()` (`theme.py:408`) and the `exit_and_download()` closure (`main.py:1442`) as defence-in-depth.

---

### F-002 — MEDIUM: Screenshot and debug folders accept reparse points

**Vulnerability**: Junction/Symlink Following (CWE-61)

**Locations**:
- `main.py:1063` — screenshot folder existence check only
- `main.py:1330` — debug folder set from `filedialog.askdirectory()`

**Proof**:

```python
# main.py:1063 — only checks existence, not reparse point status
if not folder or not Path(folder).exists():
    messagebox.showerror("Error", "Please select a valid screenshot folder")
    return

# Watchdog then monitors whatever the path resolves to
self.monitor = ScreenshotMonitor(folder=folder, ...)
```

A non-admin user can create a directory junction:
```cmd
mklink /J "C:\Users\victim\Pictures\SC_Screenshots" "C:\sensitive\path"
```

If the app is configured to monitor this path:
- The watchdog observer monitors the junction target (`C:\sensitive\path`)
- `_on_new_screenshot` is called for any file appearing in the sensitive path
- In debug mode, OCR output images are written to `scanner.debug_dir` — if the debug folder is a junction, debug outputs land in the junction target

**Impact**: Lower than the ShaderCacheNuke equivalent because this app is read-only during normal monitoring (no deletion). However, debug mode writes files to the configured debug folder. If an attacker can convince a user to set the debug folder to a junction, debug images are written to the attacker's chosen target. Also: sensitive files appearing in the monitored path are automatically read by PIL/EasyOCR.

**Remediation**:

```python
import stat

def _is_reparse_point(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        return bool(path.stat().st_file_attributes & 0x400)  # FILE_ATTRIBUTE_REPARSE_POINT
    except OSError:
        return True

# In _start_monitoring(), after existence check:
if _is_reparse_point(Path(folder)):
    messagebox.showerror("Error", "Screenshot folder cannot be a symlink or junction.")
    return
```

Apply the same check in `_browse_debug_folder()`.

---

### F-003 — MEDIUM: EasyOCR auto-processes attacker-placed image files

**Vulnerability**: Unvalidated File Input to Third-Party Processing Pipeline (CWE-20)

**Location**: `scanner.py:167` (`self._load_image(image_path)`)

**Proof**:

```python
# monitor.py:34 — accepts any file with these extensions
VALID_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}

# scanner.py:167 — immediately loaded by PIL
img = self._load_image(image_path)

# scanner.py (internal) — passed through numpy, cv2, EasyOCR model
enhanced = self._enhance_for_ocr(sig_crop)
signatures, ocr_text, confidence = self._ocr_signature(enhanced)
```

Any file placed in the monitored screenshot folder with a valid extension is:
1. Opened by `PIL.Image.open()` (arbitrary format parsing)
2. Converted to numpy array and upscaled
3. Processed through OpenCV morphological operations
4. Passed through the EasyOCR deep learning model

**Impact**: Depends entirely on the vulnerability status of the installed PIL, numpy, cv2, and EasyOCR versions. PIL has had decompression bomb (CVE-2021-27921) and format-specific issues. The `requirements.txt` specifies `Pillow>=10.0.0` which includes `MAX_IMAGE_PIXELS` protection by default (catches billion-pixel bombs), but does not prevent all image parsing vulnerabilities. A targeted attacker with knowledge of a Pillow CVE for the victim's installed version could achieve code execution by dropping a crafted image.

This is rated MEDIUM rather than HIGH because:
- Requires a CVE in the installed Pillow/numpy/cv2/torch version
- Attacker must write a file to the user's screenshot folder (requires local access or another vulnerability)
- `PIL.Image.MAX_IMAGE_PIXELS` mitigates the most common decompression bomb class

**Remediation**:

1. Pin dependency versions in `requirements.txt` (use `==` not `>=`) and update on a schedule
2. Add a file size check before loading:
```python
def _load_image(self, image_path: Path) -> Optional[Image.Image]:
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
    if image_path.stat().st_size > MAX_FILE_SIZE:
        return None
    # ... existing load logic
```
3. Consider wrapping `Image.open()` in a subprocess with a timeout for truly untrusted inputs (higher effort)

---

### F-004 — LOW: Dead `requests` dependency increases attack surface

**Vulnerability**: Unnecessary Dependency (supply chain surface)

**Location**: `requirements.txt:25`

**Proof**:

```
# requirements.txt:25
requests>=2.31.0
```

`requests` is not imported by any active source module. It was used by the removed `regolith_api.py` and `pricing.py` files. It remains in `requirements.txt` and is therefore bundled into the PyInstaller `.exe`, adding ~400KB and the entire `requests` + `urllib3` + `certifi` + `charset_normalizer` dependency tree to the attack surface.

**Impact**: Low. No active code path uses `requests`. But every bundled library is a potential CVE surface, and `requests` has had vulnerabilities in its dependency chain (e.g., `urllib3` CVEs). The unused package also creates confusion about what the app actually needs.

**Remediation**: Remove line 25 (`requests>=2.31.0`) from `requirements.txt`.

---

### F-005 — INFO: Version check swallows all exceptions

**Vulnerability**: Overly Broad Exception Handling (CWE-390)

**Location**: `version_checker.py:81`

**Proof**:

```python
except Exception as e:
    print(f"Error checking for updates: {e}")
    return (False, None, None)
```

`except Exception` catches `MemoryError`, `KeyboardInterrupt` (no, that's `BaseException`), and importantly any logic error or unexpected response format. A network error and a programming bug are handled identically — both silently return `(False, None, None)`.

**Impact**: Update check failures are invisible to the user. A malformed GitHub API response (e.g., from an attacker injecting a non-JSON response to abort the check) produces no visible feedback. Low severity because the failure mode is safe (no update shown), not dangerous.

**Remediation**: Narrow to specific exceptions:
```python
except (urllib.error.URLError, TimeoutError):
    return (False, None, None)  # Network failure — silent
except (json.JSONDecodeError, KeyError, ValueError) as e:
    import logging
    logging.warning("Version check: malformed response — %s", e)
    return (False, None, None)
```

---

## Attack Chains

### Chain A — MITM → Arbitrary URI Execution (HIGH)

```
Network attacker
    → intercepts HTTPS to api.github.com (or poisons DNS)
    → returns {"tag_name":"v99.0.0","html_url":"file:///C:/path/payload.bat"}
    → app shows "Update available: v99.0.0" dialog
    → user clicks "Exit and Download"
    → webbrowser.open("file:///C:/path/payload.bat")
    → Windows executes the batch file
```

This chain requires only F-001 and depends on: (a) attacker being network-positioned, and (b) user clicking the download button. The dialog is prominent and most users will click it when told an update is available. No authentication bypass or privilege escalation needed.

### Chain B — Screenshot Folder Junction + Debug Write (LOW)

```
Local attacker (non-admin, same machine)
    → mklink /J "C:\Users\victim\SC_shots" "C:\TargetDir"
    → convinces victim to use this as screenshot folder
    → victim enables debug mode with debug folder also junctioned
    → app writes OCR debug images to C:\TargetDir
```

Requires local access and user interaction to configure both paths. Low practical severity.

---

## Confirmed Defences (Failed Attacks)

The following issues were present in earlier versions or flagged by prior code review. They have been fixed and verified in the current codebase.

| Issue | Status | Evidence |
|-------|--------|---------|
| Thread safety in `_on_new_screenshot` | ✔ Fixed | `main.py:1183` — all UI updates via `self.root.after(0, _ui_update)` |
| Multiple `tk.Tk()` roots for OverlayPopup | ✔ Fixed | `overlay.py:43` — `self._root = root` (passed in), `tk.Toplevel(self._root)` |
| `os._exit(0)` bypassing cleanup | ✔ Fixed | `main.py:1447` — uses `sys.exit(0)` |
| `os.system()` shell injection in debug folder open | ✔ Fixed | `main.py:1315-1320` — `os.startfile()` on Windows, `subprocess.run([...])` on others |
| Bare `except:` clauses in overlay/splash | ✔ Fixed | All `except:` now `except tk.TclError:` or `except (tk.TclError, RuntimeError):` |

---

## Gaps

- **No runtime testing performed** — all findings are based on static code analysis. Exploit severity ratings are code-path assessments, not empirically verified execution.
- **EasyOCR model security** — PyTorch model files are loaded from `~/.EasyOCR/model/`. If an attacker can replace these files (requires local write access to the user profile), the model load could be exploited. Not analysed; requires adversarial ML tooling.
- **PyInstaller bundle** — the frozen `.exe` bundles all dependencies. The bundle itself is not signed (no Authenticode). A man-in-the-middle between the user and the GitHub Releases download could substitute a malicious exe. Out of scope for this assessment.

---

## Remediation Priority

| Priority | Finding | Fix Effort |
|----------|---------|-----------|
| 1 | F-001 — URL validation in update flow | ~20 lines, 3 locations |
| 2 | F-003 — File size guard before PIL load | ~5 lines |
| 3 | F-002 — Reparse point check on folder selection | ~10 lines, 2 locations |
| 4 | F-004 — Remove `requests` from requirements.txt | 1 line |
| 5 | F-005 — Narrow exception handling in version_checker | ~5 lines |

---

*Assessment based on static analysis of all source modules. No live system was accessed. Authorization: project owner.*
