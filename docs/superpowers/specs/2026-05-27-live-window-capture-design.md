# Live Window Capture — Design

**Date:** 2026-05-27
**Status:** Approved (pending implementation plan)
**Author:** Mallachi (with Claude Code)

## Goal

Eliminate the PrintScreen step. Instead of waiting for a screenshot file to appear in a watched folder, the scanner locates the running `starcitizen.exe` window, captures the calibrated signature region directly from the screen at ~30 Hz, and triggers OCR only when the captured region's content changes and stabilizes. The result is hands-free, near-real-time signature detection while mining.

## Constraints

- Star Citizen must run in Windowed or Borderless Windowed mode. Exclusive fullscreen blocks both desktop capture and the existing always-on-top overlay; this is already documented in the project README.
- EasyOCR (current engine) runs at roughly 5–15 FPS on CPU for a small region. Running OCR on every captured frame is not feasible; change-detection gating is required.
- PyInstaller bundle must continue to ship a single-folder install with no native dependencies the user has to provide manually.

## Decisions

1. **Probe model:** ~30 Hz pixel-hash change-detection on the calibrated region. OCR fires only when the hash is stable for N frames and differs from the last-emitted hash.
2. **Coexistence with existing folder-watch:** Both modes remain available, selected by a toggle in the Scanner module. The folder-watch path is unchanged.
3. **Region coordinates:** Live mode uses a **window-relative** region (origin = top-left of SC client area), persisted in a separate file from the existing screen-pixel region used by folder-watch mode.
4. **SC not running:** Live mode enters a `waiting` state and polls for the window every ~500ms. Auto-resumes when SC appears. Same path handles SC closing mid-session.
5. **Capture API:** `mss` grabs only the ROI (the calibrated region's absolute screen rect), not the full client area. Window is located each tick so the absolute rect tracks window moves.

## Architecture

Two new Python modules and small additions to existing ones.

```
+ window_finder.py     locate the SC window, return its client-area rect
+ live_capture.py      30 Hz probe loop, change-detect, run scanner on change

~ bridge.py            new JS-callable methods + scan_mode state
~ region_selector.py   add "calibrate from live SC frame" entry
~ scanner.py           split scan_image into a PIL-Image-accepting entry
~ config.py            persist scan_mode + window-relative region
~ ui/main/app.jsx      Scanner module mode toggle, REGION module
                       "Calibrate from live frame" button
```

**Unchanged:**

- `monitor.py` — kept for folder-watch mode.
- Overlay window and its `onOverlayDetection` payload shape.
- Database, match logic, OCR pipeline internals.

**Runtime topology:**

```
[Scanner module: ENGAGE]
        │
        ▼
[Bridge.start_engagement()] ──dispatches on scan_mode──┐
                                                       │
        ┌──────────── mode="folder" ──────────────────┘
        ▼
   ScreenshotMonitor (existing, unchanged)
                                                       │
        ┌──────────── mode="live" ────────────────────┘
        ▼
   LiveCapture thread
        │
        │ every ~33ms:
        ▼
   WindowFinder.find_sc_window()
        ├─ None        → state=waiting, sleep 500ms
        ├─ minimized   → state=idle_minimized, sleep 500ms
        └─ found       → mss.grab(roi_abs_rect) → hash → stable change?
                                                       │
                                              yes ────►scanner.scan_pil_image()
                                                              │
                                                              ▼
                                                       bridge._emit_match(...)
                                                       (shared with folder-watch)
```

**Merge point:** `bridge._emit_match(...)` is the existing internal path the file-watch flow already uses. Detection log, overlay payload, and dedupe behavior are identical across modes. Live mode plugs into the head of the pipeline, not the tail.

## Components

### `window_finder.py`

```python
@dataclass(frozen=True)
class WindowInfo:
    hwnd: int
    client_rect: tuple[int, int, int, int]   # (x, y, w, h) in screen coords
    is_minimized: bool
    is_foreground: bool

def find_sc_window() -> WindowInfo | None: ...
```

- Walks top-level windows via `win32gui.EnumWindows`.
- For each, `win32process.GetWindowThreadProcessId` → `psutil.Process(pid).name()`. Match `"starcitizen.exe"` case-insensitive.
- Backup match by window title (`"Star Citizen"`) if `psutil` enumeration fails.
- `client_rect` is the client area (no title bar / borders) via `GetClientRect` + `ClientToScreen`.
- Typical call cost: ~1–2 ms. Safe to invoke every probe tick.

### `live_capture.py`

```python
class LiveCapture:
    def __init__(self, scanner, bridge, region_window_relative, *,
                 probe_hz: int = 30, stable_frames: int = 3) -> None: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...
    @property
    def status(self) -> Literal["stopped", "waiting", "idle_minimized",
                                "running", "error"]: ...
```

Internals:

- Background daemon `threading.Thread`. Owns its own `mss.mss()` instance (mss is not thread-safe across threads).
- State machine: `stopped → waiting ↔ running ↔ idle_minimized → stopped`; `error` is terminal until re-engaged.
- Loop targets ~33ms per iteration; sleeps the remainder after the tick's work.
- `waiting` and `idle_minimized` tick at ~500ms (no point probing faster).
- Change-detection: `blake2b(raw_bgra, digest_size=8).digest()` on the captured bytes directly — no PIL conversion in the hot path.
- Stability gate: emit OCR only when the new hash has been seen `stable_frames` consecutive times AND differs from `last_emitted_hash`. Tracks `last_seen_hash`/`seen_count` separately from `last_emitted_hash`.
- Empty re-arm: if `scanner.scan_pil_image` returns no signatures, clear `last_emitted_hash` so the next non-blank stable read fires even if the value matches the previous one.
- Window-move handling: when `client_rect` (an `(x, y, w, h)` int tuple from Win32) changes between ticks, recompute the absolute capture rect and clear all hash state. See "Change-detection algorithms" in Data flow for the geometry-vs-content distinction.
- Status changes emitted via callback into the bridge → `onStatusChange(...)` to the main React window.

### Scanner refactor

`scanner.py` today: `scan_image(path: Path)` loads from disk, then processes.

Split into:

```python
def scan_image(self, image_path: Path) -> Optional[dict]:
    img = self._load_image(image_path)
    return self.scan_pil_image(img)

def scan_pil_image(
    self,
    img: Image.Image,
    *,
    region: tuple[int, int, int, int] | None = None,
) -> Optional[dict]:
    ...   # existing logic, optional region overrides scan_region.json lookup
```

Live mode passes the ROI image with `region=(0, 0, w, h)` — the image already starts at the ROI origin, so no further math is needed.

### Region calibration changes

- Today: REGION module opens a file picker, user drags a rect on the loaded screenshot.
- Add: a second entry, "**Calibrate from live SC frame**":
  1. `window_finder.find_sc_window()` — if missing, toast "Star Citizen not running".
  2. One-shot `mss.grab(client_rect)` → `PIL.Image`.
  3. Pass that image to the existing region-selector UI (small refactor: today it only accepts a file path; add an `open_with_image(img, ...)` entry).
  4. Save the resulting rect as **window-relative** to a new file `scan_region_window.json`.

`scan_region.json` (screen-pixel) is untouched and continues to drive folder-watch mode.

### Bridge additions

```python
# JS-exposed
def get_scan_mode(self) -> str                  # "folder" | "live"
def set_scan_mode(self, mode: str) -> dict
def start_engagement(self) -> dict              # dispatches on scan_mode
def stop_engagement(self) -> dict
def calibrate_region_live(self) -> dict
def find_sc_window_status(self) -> dict         # for UI status pill
```

`start_engagement` replaces the current "start monitoring folder" call site and dispatches on `scan_mode`. `LiveCapture.on_status_change` propagates through the bridge to the main window's `onStatusChange(...)`.

### UI additions

- **Scanner module:** a small `[FOLDER ◖ LIVE]` segmented toggle next to ENGAGE. State persisted via `set_scan_mode`. Status pill reflects live state: `WAITING FOR STAR CITIZEN`, `RUNNING — 30 Hz`, `IDLE (MINIMIZED)`, `ERROR`.
- **REGION module:** existing "PICK REGION" stays (file picker). New "PICK FROM LIVE FRAME" button next to it.

## Data flow

### Probe tick (live mode, steady state)

```
loop @ ~30 Hz:
  1. info = window_finder.find_sc_window()
       None        → state = waiting; clear hashes; sleep 500ms; continue
       minimized   → state = idle_minimized; sleep 500ms; continue
       else        → proceed
  2. if info.client_rect != prev_client_rect:        # exact tuple eq on
        # (x, y, w, h) ints — see "Change-detection algorithms" below
        recompute abs_capture_rect from info.client_rect + region_window_rel
        last_seen_hash = None
        seen_count = 0
        last_emitted_hash = None
  3. shot = mss.grab(abs_capture_rect)         # mss.ScreenShot, BGRA
     raw_bgra = bytes(shot.raw)                 # ~w*h*4 bytes
  4. digest = blake2b(raw_bgra, digest_size=8).digest()
  5. if digest == last_seen_hash:  seen_count += 1
     else:                         last_seen_hash, seen_count = digest, 1
  6. if seen_count == stable_frames AND digest != last_emitted_hash:
        img = Image.frombytes("RGB", (shot.width, shot.height),
                              raw_bgra, "raw", "BGRX")
        result = scanner.scan_pil_image(img, region=(0, 0, shot.width, shot.height))
        if result has signatures:
             last_emitted_hash = digest
             bridge._emit_match(result, source="live")
        else:
             last_emitted_hash = None      # blank — re-arm
  7. sleep to next tick boundary
```

**ROI-only capture rationale:** a typical signature region is ~120×30 px; a full 2560×1440 client area is ~1000× larger. Grabbing only the ROI cuts memory-copy and hash work proportionally, keeping the 30 Hz loop near-idle in steady state.

### Change-detection algorithms

There are two distinct "did this change?" comparisons in the probe tick. They look superficially similar but solve different problems and use different algorithms.

#### Layer 1 — Window geometry change (step 2)

**Question:** did the user move or resize the SC window between ticks?

**Inputs:** `info.client_rect` and `prev_client_rect`, each a 4-tuple of integers `(x, y, w, h)` reported by Win32 (`GetClientRect` + `ClientToScreen`). The OS returns whole-pixel values; there is no anti-aliasing or driver jitter at this layer.

**Algorithm:** exact tuple equality (`info.client_rect == prev_client_rect`).

**Why exact is correct:** the values are integers produced by the OS, not by sampling pixels. If the user nudges the window by one pixel, the tuple changes by one; if they don't, it doesn't. No tolerance is appropriate — even a one-pixel shift means the absolute capture rect is wrong and we should re-prime change detection.

#### Layer 2 — Region content change (steps 4–6)

**Question:** did the captured signature region's pixels change in a meaningful way?

**Inputs:** the BGRA bytes of the captured ROI (`shot.raw`, ~w·h·4 bytes for a ~120×30 region — roughly 14 KB).

**Algorithm:** byte-level `blake2b(raw, digest_size=8)` digest, then **strict equality** between consecutive digests, **gated by an N-frame stability counter** (`stable_frames=3`).

**Why not exact equality alone:** you are correct that two captures of the "same" content can differ at the pixel level for reasons that have nothing to do with the signature value:
- HUD animations / fading edges / cursor blink inside the ROI
- Sub-pixel anti-aliasing of digits when the camera moves slightly
- Compositor jitter from other on-screen windows (rare for borderless-windowed SC, but possible)
- GPU driver dithering on some hardware

A naïve "fire OCR whenever the hash changes" would re-fire OCR on every flicker.

**How the stability counter solves it:** the loop tracks `last_seen_hash` (the most recent digest) and `seen_count` (how many ticks in a row that same digest has been observed). OCR fires only when `seen_count == stable_frames` **and** the now-stable digest differs from `last_emitted_hash` (the last digest that produced an emission). Flicker keeps resetting `seen_count` to 1; static content increments it. At 30 Hz with `stable_frames=3`, OCR fires ~100 ms after pixels settle — fast enough to feel live, slow enough to ignore one- and two-frame transients.

**Empty re-arm:** if OCR returns no signatures (the region is blank — between rocks, looking at the sky, etc.), `last_emitted_hash` is cleared. The next stable read fires even if its hash happens to match a previously emitted one. This is what makes the same rock fire again when you look away and back.

#### Pathological case: a region that never stabilizes

If the calibrated region contains continuously animated content (e.g. a spinning HUD element that overlaps the signature box), `seen_count` will never reach `stable_frames` and OCR will never fire. Symptoms: live mode shows "RUNNING — 30 Hz" but the overlay never appears, even when a signature is visible.

The spec does **not** silently work around this. If real-world testing shows it happens, the documented escape valves (in order of cost):
1. Recalibrate the region tighter around the digit-only area in REGION → Calibrate from live frame.
2. Raise `stable_frames` to 4 or 5 (small constant, easy tweak).
3. Replace `blake2b` strict equality with a perceptual / fuzzy hash (e.g. `dhash` or downsample-then-`blake2b`) and compare with a Hamming-distance threshold — but only if 1 and 2 don't resolve it. Fuzzy hashing trades determinism for robustness, and the bug it solves is one we have no evidence of yet (YAGNI).

#### Considered and rejected: OpenCV-based similarity

OpenCV is already a project dependency (`scanner.py` uses `cv2.connectedComponentsWithStats`, etc.) and is bundled in the PyInstaller spec, so reaching for `cv2.absdiff` + thresholded pixel-difference count, `cv2.matchTemplate`, or `opencv-contrib-python`'s `img_hash` module would cost zero additional install weight. We chose **not** to use any of them for the steady-state change detector. Reasons:

- **The problem is temporal, not spatial.** The "slight differences" between two captures of the same HUD content are transient: a mouse cursor crossing the ROI, compositor jitter, a single-frame animation tick. Once they pass, the framebuffer goes byte-identical again. A temporal filter (the N-frame stability counter) absorbs them at lower cost than any per-pixel similarity score, because in steady state the hash matches and the counter just increments — no spatial comparison runs at all.
- **It adds a tunable threshold.** A similarity score needs a cutoff ("at least 98% similar = same"). That cutoff has to be picked, re-tuned per game patch / monitor / GPU, and documented. Byte-hash + stability counter has no such knob; either two frames are identical or they aren't.
- **It costs more CPU every tick, not just on emit.** `cv2.absdiff` followed by `cv2.countNonZero` on a 120×30×4 buffer runs slower than `blake2b` over the same 14 KB and has to run on every probe (we have no per-frame shortcut). The byte hash, by contrast, is near-free and the steady-state loop stays close to idle.
- **A loose threshold can hide real changes.** Adjacent signature values often differ in only one digit — "3540" → "3585" is a handful of pixels on a tight crop. Any threshold permissive enough to ignore anti-aliasing also risks ignoring that. With strict equality + the stability gate, a real digit change always triggers; only persistent animation can confuse it (covered by the escape valves above).

The right time to revisit this decision is if a user reports a region that genuinely never stabilizes (escape valve #3 above), at which point fuzzy hashing — not OpenCV similarity — is the targeted fix.

### Calibration flow

```
JS → bridge.calibrate_region_live()
  1. info = window_finder.find_sc_window()
       None → return {"error": "Star Citizen not running"}
  2. img = mss.grab(info.client_rect) → PIL.Image
  3. region_selector.RegionSelector.open_with_image(img, on_save=cb)
  4. user drags rect → coords already window-relative; persist to
     scan_region_window.json
  5. bridge → onRegionCalibrated(...)
```

### Mode switch flow

```
JS → bridge.set_scan_mode("live" | "folder")
  → persists to config.json
  → if currently engaged: stop active mode, start new mode
  → emits onScanModeChanged
```

### Persisted state

| File | Content | Used by |
|---|---|---|
| `config.json` → `scan_mode` | `"folder"` or `"live"` | both modes |
| `scan_region.json` | screen-pixel rect (existing) | folder mode |
| `scan_region_window.json` | window-relative rect (new) | live mode |

## Error handling

| Failure | Detection | Response |
|---|---|---|
| `starcitizen.exe` not running | `find_sc_window()` returns `None` | State → `waiting`; UI shows "WAITING FOR STAR CITIZEN"; poll every 500ms; auto-resume on appearance. Same path handles SC exiting mid-session. |
| SC window minimized | `info.is_minimized` true | State → `idle_minimized`; sleep 500ms; don't capture. Resumes on restore. |
| Region not configured (live mode) | `scan_region_window.json` missing on engage | Refuse to start. Emit "Live region not calibrated — use REGION → Calibrate from live frame". |
| Region falls outside client rect (user shrunk SC after calibration) | `region.x2 > client_rect.w` or `y2 > h` | Clamp inside client rect. If resulting rect is degenerate (< 10×5 px), pause capture and emit "Live region out of bounds — recalibrate". |
| `mss.grab()` raises (display driver hiccup, monitor disconnected) | try/except around grab | Log via scanner debug channel, skip tick, continue. Three consecutive failures → state `error`; stop until re-engaged. |
| `find_sc_window()` raises (rare; `psutil` access denied, etc.) | try/except around call | Treat as "not found" → `waiting`. Log once. |
| OCR raises | Already wrapped in `scanner.py` | Returns `{'error': ...}`; no signature emitted; loop continues. Identical to today. |
| Capture thread dies unexpectedly | `Thread.is_alive()` check in `find_sc_window_status()` | Reported state `error`. No auto-restart — covers genuine bugs visibly. |
| Multi-monitor: SC on monitor with negative origin (left-of-primary) | `mss` handles natively | No special code. Don't validate-away negative `left`/`top`. |
| PyInstaller bundling | Build-time verification | `mss`, `pywin32`, `psutil` added to `SC_Signature_Scanner.spec` hidden imports + binaries. |

**Non-behaviors:**

- No retry-with-backoff loops. Transient failures resolve on the next tick; persistent failures escalate to `error` state visibly.
- No silent fallback from live to folder mode. The user picked a mode; if it can't run, surface that fact.

## Testing

The project does not currently have a `tests/` directory. Two tracks:

### Unit-testable (pure logic, no display)

- `live_capture._hash_bytes` — deterministic for identical input.
- `live_capture` stability state — synthetic hash sequence drives `seen_count` and `last_emitted_hash` correctly, including the blank-re-arm branch.
- `window_finder` clamp logic — region rect larger than client rect gets clamped; degenerate rects flagged.
- Coordinate math: `(client_rect, region_window_rel) → abs_capture_rect`.
- `scanner.scan_pil_image` with a synthetic image (PIL `ImageDraw` rendering a known signature like `"3540"`) — asserts signature extracted. Decouples scanner from disk I/O.

### Manual / integration (with SC running)

A short checklist (`docs/manual-test-live-capture.md`, written during implementation) the maintainer runs once per release:

1. Cold start, SC closed → ENGAGE in live mode → status `WAITING`. Launch SC → status flips to `RUNNING`.
2. With a known mineable in view, overlay fires within ~150 ms of the signature appearing.
3. Stand on the same rock 10 s → overlay fires exactly once.
4. Look away, then back at the same rock → overlay fires again.
5. Drag the SC window mid-session → no spurious detection during the move; first new stable signature after the move fires correctly.
6. Minimize SC → status `IDLE (MINIMIZED)`; CPU drops; restore → resumes.
7. Resize SC smaller than calibrated region → "out of bounds" message; re-enlarging resumes.
8. Switch mode to folder mid-engagement → live thread stops cleanly, folder watcher starts.
9. Close SC mid-engagement → status returns to `WAITING`, no errors logged.

### Out of scope

- Automated win32 / mss tests (need a display + window — flaky in CI).
- Performance benchmarks beyond eyeballing CPU% in Task Manager.

## New dependencies

- `mss` — fast cross-platform screen capture, MIT, pure-Python with bundled native bindings.
- `pywin32` — Windows API access (window enumeration, client-area geometry). Already a transitive dependency of pywebview on Windows in many setups; pin explicitly.
- `psutil` — process-name lookup by PID. Small, well-maintained.

All three need to be added to `requirements.txt` and the PyInstaller spec.

## Out of scope (deferred)

- Replacing EasyOCR with a faster engine (Option C from brainstorming). The change-detection gate makes 30 Hz feasible with the current engine; revisit only if real-world latency feedback demands it.
- Windows.Graphics.Capture API path for occluded windows. The overlay already requires Windowed/Borderless, so `mss` covers all supported configurations.
- A GPU-accelerated EasyOCR mode toggle — separate concern.
