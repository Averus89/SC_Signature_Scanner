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

- [ ] **Window-move robustness.** Drag the SC window across the desktop
  mid-session → no spurious detection during the move; first new stable
  signature after the move fires correctly.

- [ ] **Minimize idle.** Minimize SC → status pill flips to
  "IDLE (MINIMIZED)"; CPU usage drops (verify in Task Manager). Restore →
  capture resumes.

- [ ] **Region out-of-bounds.** Resize SC so the window is smaller than the
  calibrated region's bottom-right corner → status reads "ERROR" with an
  "out of bounds — recalibrate" message. Re-enlarge → capture resumes
  without re-engaging.

- [ ] **Mid-session mode switch.** While LIVE is running, switch the toggle
  to FOLDER → live thread stops cleanly (verify in logs), folder watcher
  starts on the configured screenshot folder.

- [ ] **SC closes mid-session.** Close SC → status returns to "WAITING FOR
  SC"; no errors logged. Relaunching SC resumes capture.

## What's NOT tested by this checklist

- Multi-monitor with negative-origin monitors (covered by unit tests).
- Exclusive-fullscreen SC — explicitly unsupported; same constraint as the
  existing always-on-top overlay.
