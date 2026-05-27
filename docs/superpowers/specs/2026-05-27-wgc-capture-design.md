# Windows Graphics Capture (WGC) Migration — Design

**Date:** 2026-05-27
**Status:** Approved (pending implementation plan)
**Author:** Mallachi (with Claude Code)

## Goal

Replace `mss`-based desktop screen-scraping with Windows.Graphics.Capture (WGC) for live capture and for the one-shot region calibration grab. WGC captures the SC window's swap-chain content directly, regardless of Z-order or what other windows overlap the HUD area. This eliminates the entire class of bugs where mss returned the topmost window's pixels instead of SC's pixels, and removes the brittle `WindowFromPoint` occlusion check added in PR #5.

## Motivation

Field bug: live detection produced no real matches and the detection log filled with "No signature detected" entries. Debug captures showed a Windows Settings teal background and an Explorer file listing where the SC HUD should be. Z-order probe confirmed SC was the 4th window from the top at the calibrated capture coordinates. mss-as-implemented is a screen-scrape — it returns whatever window is topmost at the given pixel, not a specific window's content.

PR #5 added a `WindowFromPoint(center_of_capture)` check that refused to capture when SC wasn't the literal topmost hwnd. Working as designed, but counterproductive in practice: transparent always-on-top overlays (NVIDIA, Steam, Discord, our own overlay window) return their own hwnd from WindowFromPoint even though the user sees SC through them. The check now fires false negatives and live mode produces no debug images even when SC is plainly visible.

WGC bypasses both problems: it captures the window's swap-chain content regardless of what's painted on top.

## Constraints

- Windows 10 1903+ required for WGC. Already satisfied by the project's Windows 10/11 requirement.
- `winsdk` is unavailable on Python 3.14. Use the modular `winrt-*` packages (3.2.1) plus the `windows-capture` 2.0.0 PyPI library, which wraps the WGC + D3D11 readback pipeline in a Pythonic API (Rust/PyO3 wheel under the hood).
- The capture region is the full SC client area. WGC does not natively support region-restricted capture; cropping happens after readback (CPU-side for v1, can move GPU-side later if perf demands).
- Frames arrive at the source's refresh rate (game FPS, 60–144). Probe rate stays decoupled: the tick loop reads `self._latest_frame` at the configured `live_probe_hz`; frames between ticks are dropped naturally.

## Decisions

1. **Scope: full replacement.** Drop mss entirely. Both the live probe loop and the one-shot calibration grab move to WGC. No mss-as-fallback.
2. **Foundation: `windows-capture` 2.0.0.** PyPI Python wrapper around WGC + D3D11 readback. Avoids ~500 LOC of hand-rolled COM interop. Adds ~3 MB to the bundle.
3. **Threading: background callback + drop-newest frame slot.** windows-capture runs WGC on its own thread; we store the most recent frame in a single `Optional[tuple[bytes, int, int]]` slot under a `threading.Lock`. The existing tick loop reads that slot at `live_probe_hz` and crops to the ROI in CPU.
4. **Remove the WindowFromPoint occlusion check.** WGC captures SC's content regardless of Z-order, making the check obsolete and counterproductive. Drop the `idle_occluded` Status literal, the `_window_from_point` DI parameter, the `_default_window_from_point` helper, the related tests, and the UI label.

## Architecture

```
+ wgc_capture.py              new — wraps a `windows-capture` session;
                              owns the background frame-callback thread

~ live_capture.py             mss_factory → wgc_session_factory DI swap
                              tick() reads self._latest_frame instead of mss.grab
                              WindowFromPoint occlusion check + idle_occluded REMOVED
                              Status type loses the "idle_occluded" literal

~ bridge.py                   _start_live: pass wgc_session_factory (or rely on default)
                              calibrate_region_live: one-shot WGC instead of mss.grab
                              find_sc_window_status: no longer reports idle_occluded

~ ui/main/scanner-panel.jsx   drop "SC OCCLUDED — FOCUS GAME" branch from status label
~ ui/main/index.html          cache-buster v=44 → v=45

~ requirements.txt            -mss  +windows-capture>=2.0.0
~ SC_Signature_Scanner.spec   hiddenimports: drop mss, add windows-capture
                              + collect_submodules('winrt') for transitive
                              + collect_dynamic_libs('windows_capture')
```

**Unchanged:**

- `window_finder.py` — we still need it to find SC's hwnd for the WGC session.
- `StabilityTracker`, `compute_abs_capture_rect`, scanner integration — the byte pipeline downstream of capture is identical.
- Folder mode (it never used mss).
- All UI except the one dropped status label and the cache-buster.

**Net result:** slightly negative LOC vs current master. The new `wgc_capture.py` is offset by the removed mss path + WindowFromPoint check.

## Components

### `wgc_capture.py` (new)

```python
class WGCError(Exception):
    """Raised when WGC is unsupported or the session fails to start."""


class WGCSession:
    """Wraps a windows-capture session bound to a single hwnd.

    Knows nothing about ROIs, hashes, or OCR. Delivers full-window BGRA
    frames to an `on_frame(raw_bytes, w, h)` callback that runs on the
    library's capture thread.
    """

    def __init__(
        self,
        hwnd: int,
        on_frame: Callable[[bytes, int, int], None],
    ) -> None: ...

    def start(self) -> None:
        """Start the capture session. Raises WGCError if WGC is unsupported
        or the underlying session.start() throws."""

    def stop(self) -> None:
        """Idempotent. Safe from any thread."""

    @property
    def is_active(self) -> bool: ...
```

Internals:

- Owns a `windows_capture.WindowsCapture` instance bound to the SC hwnd.
- Registers `on_frame_arrived` and `on_closed` callbacks per the library's decorator API.
- `start()` calls `GraphicsCaptureSession.IsSupported()` first; raises `WGCError` if False. Wraps `session.start()` in try/except → `WGCError`.
- On frame arrival: extract BGRA bytes + dimensions from the frame object; invoke `self.on_frame(raw, w, h)`.
- `on_closed` clears the active flag — used by `LiveCapture` to react to the SC window closing.

### `LiveCapture` refactor

Constructor signature:

```python
def __init__(
    self,
    *,
    scanner: Any,
    emit: Callable[..., None],
    find_sc_window: Callable[[], Any] = _default_find_sc_window,
    load_window_region: Callable[[], Any] = _default_load_window_region,
    wgc_session_factory: Callable[[int, Callable], Any] = _default_wgc_session_factory,
    probe_hz: int = 30,
    stable_frames: int = 3,
    emit_empty: bool = False,
) -> None: ...
```

Removed: `mss_factory`, `window_from_point`. Added: `wgc_session_factory(hwnd, on_frame) -> WGCSession`.

New instance state:

```python
self._wgc: Optional[WGCSession] = None
self._wgc_hwnd: Optional[int] = None             # which hwnd the session is bound to
self._frame_lock: threading.Lock = threading.Lock()
self._latest_frame: Optional[tuple[bytes, int, int]] = None
self._ticks_without_frame: int = 0               # warming-up vs stuck detection
```

`_run()`:

- No `mss_factory()` call. The WGC session is created lazily inside `tick()` when an SC window is found, so the session lifecycle tracks the SC window lifecycle.
- Cleanup on exit: call `_stop_wgc()` in the finally block.

`tick()`:

1. `find_sc_window()` → `info`.
2. `None` → `_stop_wgc()`, reset tracker, status `waiting`, sleep `_idle_period`.
3. `minimized` → `_stop_wgc()`, status `idle_minimized`, sleep `_idle_period`.
4. `info.hwnd != self._wgc_hwnd` → `_stop_wgc()`, `_start_wgc(info.hwnd)`, reset tracker.
5. With `self._frame_lock`: `frame = self._latest_frame`.
6. If `frame is None`: increment `_ticks_without_frame`. If above threshold (~90 ticks at 30 Hz = 3 sec), status `error` ("WGC session not producing frames"). Otherwise status `running` (warming up), sleep `_tick_period`.
7. Else: reset `_ticks_without_frame = 0`. Clamp ROI via `compute_abs_capture_rect((0, 0, frame_w, frame_h), region_window_rel)`. If degenerate → status `error`, surface "Live region out of bounds — recalibrate".
8. Crop bytes via `_crop_bgra`. Hash. `tracker.observe(...)`.
9. On `stable_change`: build `Image.frombytes` from the ROI bytes, call `scanner.scan_pil_image(img, region=(0, 0, roi_w, roi_h))`. Emit or `empty_rearm` per existing logic.

`stop()`:

- `_stop_event.set()`, `_thread.join(timeout=2.0)`, `_stop_wgc()`, status `stopped`.

### `_crop_bgra(buf, frame_w, frame_h, region)` (pure)

```python
def _crop_bgra(
    buf: bytes,
    frame_w: int,
    frame_h: int,
    region: tuple[int, int, int, int],
) -> tuple[bytes, int, int]:
    """Crop a BGRA pixel buffer to (x1, y1, x2, y2). Returns (roi_bytes, w, h)."""
    x1, y1, x2, y2 = region
    stride = frame_w * 4
    rows = [buf[y * stride + x1 * 4 : y * stride + x2 * 4] for y in range(y1, y2)]
    return (b"".join(rows), x2 - x1, y2 - y1)
```

Pure logic, no IO — fully unit-testable. Lives in `live_capture.py` or `wgc_capture.py` (implementer's choice; the spec assumes `live_capture.py` for cohesion with the tick logic).

### `bridge.py` changes

- `_start_live()`: construct `LiveCapture(scanner=..., emit=self._on_live_result, probe_hz=cfg.get("live_probe_hz", 30), emit_empty=cfg.get("live_log_no_signature", False))`. (Same call shape as today; the `mss_factory` parameter never existed publicly — `LiveCapture` always relied on its default factory.)
- `calibrate_region_live()`: replace the mss-based one-shot:

  ```python
  info = find_sc_window()
  if info is None:
      return {"ok": False, "error": "Star Citizen not running"}

  frame_ready = threading.Event()
  captured: list[tuple[bytes, int, int]] = []
  def cb(raw, w, h):
      if captured:
          return
      captured.append((raw, w, h))
      frame_ready.set()

  session = WGCSession(info.hwnd, on_frame=cb)
  try:
      session.start()
  except WGCError as e:
      return {"ok": False, "error": str(e)}

  ok = frame_ready.wait(timeout=5.0)
  session.stop()

  if not ok:
      return {"ok": False, "error": "WGC didn't deliver a frame in 5 seconds"}

  raw, w, h = captured[0]
  img = Image.frombytes("RGB", (w, h), raw, "raw", "BGRX")
  selector = region_selector.RegionSelector(parent=None)
  selector.open(image=img, save_as_window_relative=True)
  return {"ok": True}
  ```

- `find_sc_window_status()`: `captureStatus` no longer reports `idle_occluded`. No additional code change beyond removing the literal from the Status enum in `live_capture.py`.

### UI

- `ui/main/scanner-panel.jsx`: drop the `liveStatus.captureStatus === 'idle_occluded' ? 'SC OCCLUDED — FOCUS GAME' :` branch from the status-label ternary.
- `ui/main/index.html`: cache-buster `?v=44 → ?v=45` on all `.jsx` and `styles.css` references.

## Data flow

### Probe tick (live mode, steady state)

```
loop @ ~live_probe_hz:
  info = find_sc_window()

  None        → _stop_wgc(); tracker.reset(); status = waiting; idle 500ms
  minimized   → _stop_wgc(); status = idle_minimized; idle 500ms
  hwnd-change → _stop_wgc(); _start_wgc(info.hwnd); tracker.reset(); continue

  if not _wgc.is_active:
      status = error; idle 500ms

  with _frame_lock:
      frame = self._latest_frame

  if frame is None:
      _ticks_without_frame += 1
      if _ticks_without_frame >= _NO_FRAME_ERROR_THRESHOLD:  # default 90 ticks (~3s @ 30Hz)
          status = error
          return _idle_period
      status = running   # warming up
      return _tick_period

  _ticks_without_frame = 0
  raw_bgra, frame_w, frame_h = frame

  abs_roi = compute_abs_capture_rect((0, 0, frame_w, frame_h), region_window_rel)
  if abs_roi is None:
      status = error    # region out of bounds
      return _idle_period

  left, top, roi_w, roi_h = abs_roi
  roi_bytes, _, _ = _crop_bgra(raw_bgra, frame_w, frame_h,
                               (left, top, left + roi_w, top + roi_h))

  digest = blake2b(roi_bytes, digest_size=8).digest()
  decision = self._tracker.observe(digest)
  status = running

  if decision != "stable_change":
      return _tick_period

  img = Image.frombytes("RGB", (roi_w, roi_h), roi_bytes, "raw", "BGRX")
  result = self.scanner.scan_pil_image(img, region=(0, 0, roi_w, roi_h))
  # existing emit / empty_rearm / emit_empty logic, unchanged
```

### Frame delivery (background)

```
WGC callback thread (windows-capture):
  on_frame(raw, w, h):
      with self._frame_lock:
          self._latest_frame = (raw, w, h)
```

Drop-newest semantics. If the game produces frames at 144 Hz and we tick at 30 Hz, we naturally drop ~3.8 frames per tick — no queueing, no growing buffers. Lock held for microseconds.

### Calibration flow

```
JS → bridge.calibrate_region_live()
  1. info = find_sc_window(). None → {"ok": False, "error": "Star Citizen not running"}.
  2. Create WGCSession(info.hwnd, on_frame=cb).
  3. session.start(). On WGCError → {"ok": False, "error": str(e)}.
  4. Wait threading.Event with 5s timeout. Timeout → {"ok": False, "error": "..."}.
  5. session.stop().
  6. Image.frombytes("RGB", (w, h), captured_bytes, "raw", "BGRX").
  7. RegionSelector(parent=None).open(image=img, save_as_window_relative=True).
  8. Return {"ok": True}.
```

### Persisted state (unchanged)

| File | Content | Used by |
|---|---|---|
| `config.json` → `scan_mode`, `live_probe_hz`, `live_log_no_signature` | snake_case live-mode settings | bridge |
| `scan_region.json` | screen-pixel rect | folder mode |
| `scan_region_window.json` | window-relative rect (top-left of client area = origin) | live mode |

The window-relative semantics are identical to the current implementation — calibrations made under mss stay valid under WGC. No user-side migration.

## Error handling

| Failure | Detection | Response |
|---|---|---|
| `windows-capture` missing | `ImportError` at `wgc_capture` module load | `LiveCapture.start()` returns `{"ok": False, "error": "windows-capture dependency missing"}`. Should never happen post-install. |
| `IsSupported()` returns False | `WGCSession.start()` checks before subscribing | Raises `WGCError("Windows Graphics Capture not supported on this system")`. LiveCapture catches, sets status `error`, returns error dict to bridge. |
| Session start raises (driver issue, transient COM failure) | try/except around the underlying `session.start()` | Same as above. Surface the underlying message verbatim. |
| Window closed mid-session | windows-capture's `on_closed` callback OR `find_sc_window()` next tick returns None | `_on_closed` marks session inactive and clears `_latest_frame`. Next `tick()` finds no hwnd → transitions to `waiting`, stops session cleanly. No error to user. |
| Session active but no frames received | `_latest_frame is None` for `_NO_FRAME_ERROR_THRESHOLD` ticks (~3s @ 30Hz) | Status `error`. Counter resets on first frame received. |
| ROI degenerate after clamp to current frame size | `compute_abs_capture_rect` returns None | Status `error`, message "Live region out of bounds — recalibrate via REGION → PICK FROM LIVE FRAME". |
| ROI byte length wrong after crop (defensive) | `len(roi_bytes) != roi_w * roi_h * 4` | Skip the tick. Shouldn't happen — clamp covers it. Cheap insurance. |
| `Image.frombytes` raises (malformed bytes) | try/except around the frombytes + scan_pil_image block | Emit `{"error": "frame decode failed: ..."}` if `emit_empty=True`, else silent. Loop continues. |
| Window-move / resize (client_rect changes) | `info.client_rect != prev_client_rect` (existing logic, repurposed for WGC) | Restart the WGC session for the new geometry. Tracker resets; next stable frame triggers a fresh detection. |
| Frame dimensions changed mid-session (in-game resolution change) | `frame_w/h` differs from previous tick's | Re-clamp the ROI via `compute_abs_capture_rect`. Degenerate → "out of bounds" path above. Otherwise tracker keeps running. |
| OCR raises | Already wrapped in `scanner.py` | Returns `{'error': ...}`; LiveCapture's existing path emits or skips per `emit_empty`. Unchanged. |
| User permission prompt | WGC for a known hwnd does not prompt. | No code path. |

**Non-behaviors (intentional):**

- No silent fallback to mss. Per scope decision; if WGC fails, surface that.
- No retry-with-backoff for session start. Either it works on engage or the user sees the error and re-engages.

**PyInstaller bundling:**

- `windows-capture` ships a native `.pyd` extension (Rust/PyO3). Bundle via `collect_dynamic_libs('windows_capture')` and `hiddenimports = ['windows_capture']`.
- Transitive `winrt-*` packages collected via `hiddenimports += collect_submodules('winrt')`.

## Testing

### Unit tests

**`tests/test_wgc_session.py` (new)** — fake the `windows_capture.WindowsCapture` library object via DI; assert callback wiring, lifecycle correctness, error paths.

- `test_start_raises_when_wgc_unsupported` — fake's `is_supported()` returns False → `WGCSession.start()` raises `WGCError`.
- `test_start_registers_frame_callback` — after start, the fake's frame callback is the session's.
- `test_frame_callback_invokes_on_frame_with_bgra_bytes` — simulate a fake frame; assert the user-supplied `on_frame(raw, w, h)` was called with the right shape.
- `test_stop_is_idempotent` — calling stop twice doesn't raise; calling stop without start doesn't raise.
- `test_on_closed_marks_session_inactive` — fake fires `on_closed`; `WGCSession.is_active` becomes False.

**`tests/test_wgc_crop.py` (new)** — pure `_crop_bgra` tests:

- `test_crop_returns_correct_subrect_bytes`
- `test_crop_handles_full_frame`
- `test_crop_first_pixel_of_row_is_top_left`
- `test_crop_size_matches_region`

**`tests/test_live_capture_loop.py` (rewrite scaffolding)** — replace `FakeMss` + `mss_factory` with `FakeWGCSession` + `wgc_session_factory`. The fake records the `on_frame` callback and exposes `push_frame(raw, w, h)` for tests to inject frames.

Carried over (10):

- `test_status_starts_stopped`
- `test_tick_with_no_window_sets_waiting`
- `test_tick_with_minimized_window_sets_idle_minimized`
- `test_tick_with_visible_window_captures_and_runs_ocr_after_stable_frames`
- `test_empty_ocr_result_re_arms_so_same_hash_fires_again`
- `test_window_move_invalidates_hash_state`
- `test_starts_with_missing_region_sets_error`
- `test_stop_returns_to_stopped`
- `test_emit_empty_true_surfaces_no_signature_to_emit`
- `test_emit_empty_false_suppresses_no_signature_default_behavior`

Deleted (2):

- `test_tick_skips_capture_when_sc_is_occluded_by_another_window` — WindowFromPoint mechanism is gone.
- `test_tick_proceeds_when_sc_is_topmost_at_capture_point` — collapses into the happy-path case.

New (3):

- `test_tick_with_no_frame_yet_remains_running` — session active but `_latest_frame is None` → status stays `running`, no OCR, returns `_tick_period`.
- `test_tick_warming_up_eventually_errors_if_no_frames_arrive` — after `_NO_FRAME_ERROR_THRESHOLD` ticks of no frames, status transitions to `error`.
- `test_roi_clamp_to_smaller_frame_yields_degenerate_error` — push a frame smaller than the calibrated region's bottom-right; expect status `error` with the "out of bounds" message.

### Existing tests (unaffected)

- `test_window_finder.py` (5)
- `test_scanner_pil.py` (3)
- `test_region_selector_storage.py` (4)
- `test_live_capture_stability.py` (7)
- `test_live_capture_geometry.py` (5)
- `test_smoke.py` (1)

### Final tally

37 (current master) − 2 (occlusion check) + 5 (`test_wgc_session`) + 4 (`test_wgc_crop`) + 3 (new live_capture cases) = **47 tests passing**.

### Manual checklist (`docs/manual-test-live-capture.md`)

**New scenarios** (enabled by WGC's occlusion-immunity):

- [ ] **SC behind Windows Settings.** Open Windows Settings (or any opaque window) over the SC HUD area. ENGAGE in LIVE mode. → Detections fire normally. Status pill: `LIVE · 30 Hz`.
- [ ] **Transparent overlay active.** Enable NVIDIA / Steam / Discord overlay (or any always-on-top transparent app). → Detections fire normally.
- [ ] **Live mode while scanner app is foreground.** Click into the Scanner UI itself while LIVE is engaged. → Detections continue to fire.

**Removed:**

- The "SC OCCLUDED — FOCUS GAME" status scenario (state no longer exists).

**Retained:**

- Cold start with SC closed → `WAITING FOR SC`; auto-resume when SC appears.
- Minimize → `IDLE (MINIMIZED)`; restore resumes.
- Window-move mid-session.
- Region out-of-bounds after resize.
- Mode switch FOLDER ↔ LIVE mid-session.
- SC closes mid-session.

## Out of scope (deferred)

- **GPU-side ROI cropping via D3D11 `CopySubresourceRegion`.** Future optimization if CPU usage during live mode is high. Current full-window-readback + CPU-crop is simple, correct, and well within budget for typical SC client sizes (5120×1440×4 = 29 MB per frame at the WGC delivery rate; at 30 Hz tick rate we hash and crop a ~100×49 ROI = ~20 KB).
- **Automated tests against the real `windows-capture` library.** Requires a display + actual WGC support; flaky in CI. Manual checklist covers it.
- **Fallback to mss when WGC unavailable.** Out of scope per the "full replacement" scope decision; revisit only if real user reports come in.
- **Per-window cursor inclusion/exclusion toggle.** windows-capture exposes a `cursor_capture_enabled` flag; not surfaced in the UI for now.
