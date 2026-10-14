# Manual Test Checklist — Live Window Capture

Run this once per release of any change touching `window_finder.py`,
`live_capture.py`, `region_selector.py` (open with `image=`), or the Scanner /
REGION modules in `ui/main/app.jsx` / `ui/main/scanner-panel.jsx` /
`ui/main/module-panels.jsx`.

**Prerequisites:**
- Star Citizen installed and runnable.
- `scan_region_window.json` calibrated against your current SC HUD layout
  (REGION module → PICK FROM LIVE FRAME).

## Scenarios

- [ ] **Cold start, SC closed.** ENGAGE in LIVE mode → status pill reads
  "WAITING FOR SC". Launch SC → status flips to "LIVE · 30 Hz" within
  ~1 second of the game window appearing.

- [ ] **Detection latency.** With a known mineable in view, overlay fires
  within ~150 ms of the signature appearing on the HUD.

- [ ] **No re-fire on static content.** Stand on the same rock 10 seconds →
  overlay fires exactly once. Detection log shows one entry.

- [ ] **Look-away re-arm.** Look away (signature gone) → look back at the
  same rock → overlay fires again. Both detections in the log.

- [ ] **SC behind opaque windows.** Open Windows Settings (or any other
  opaque window) over the SC HUD area. → Detections fire normally. (WGC
  captures SC's swap-chain content regardless of Z-order.)

- [ ] **Transparent overlay active.** Enable NVIDIA / Steam / Discord
  overlay. → Detections fire normally.

- [ ] **Live mode while scanner is foreground.** Click into the Scanner UI
  itself while LIVE is engaged. → Detections continue to fire.

- [ ] **Window-move robustness.** Drag the SC window across the desktop
  mid-session. → First new stable signature after the move fires correctly.

- [ ] **Minimize idle.** Minimize SC → status pill flips to
  "IDLE (MINIMIZED)"; CPU usage drops. Restore → capture resumes.

- [ ] **Region out-of-bounds.** Resize SC smaller than the calibrated
  region. → Status reads "ERROR" with an "out of bounds" message.
  Re-enlarging resumes without re-engaging.

- [ ] **Mid-session mode switch.** While LIVE is running, switch the
  toggle to FOLDER. → Live thread stops cleanly, folder watcher starts.

- [ ] **SC closes mid-session.** Close SC. → Status returns to "WAITING
  FOR SC"; no errors logged. Relaunching SC resumes capture.

- [ ] **WGC unsupported (rare).** On a system without WGC support (very
  old Windows 10 build, exotic graphics driver), ENGAGE in LIVE mode
  surfaces a clear error: "Windows Graphics Capture is not supported on
  this system."
