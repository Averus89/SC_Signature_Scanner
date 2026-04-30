# SC Signature Scanner

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-Support-orange?style=flat&logo=buy-me-a-coffee)](https://buymeacoffee.com/Mallachi)

Real-time signature identification for Star Citizen. Drop a screenshot in your watched folder, the scanner reads the HUD signature with **EasyOCR**, looks the value up against a database extracted from `Game2.dcb`, and shows the match as a tier-colored overlay floating over the running game.

**Version:** 6.0.0
**Author:** Mallachi
**Game Version:** Star Citizen 4.7+

---

## Screenshots

**Scanner module** — Target Profile (the reveal card), Monitor Control, and Detection Log all in one view. The reveal card shows the matched mineral, tier, signature value, and OCR confidence (CONF).

<img src="Images/Main%20page.png" width="700" alt="Scanner module">

**Index module** — Full signature codex grouped by class (Ship Mining / Ground / Salvage) and tier. All entries hydrate live from Python's signature DB, so what you see is exactly what the scanner will match against.

<img src="Images/Signature%20overview.png" width="700" alt="Signature index">

**Region module** — One-time calibration. PICK REGION opens a screenshot, you drag a rectangle over the in-game signature value, click Save. Coordinates are stored screen-relative and the scanner reads OCR from that exact box on every screenshot afterwards.

<img src="Images/Detection%20settings.png" width="700" alt="Scan region calibration">

**Settings module** — Overlay placement (drag-to-place the live overlay onto your game), behavior (duration / scale / debug output), and storage. Scale changes propagate to a live overlay instantly without a relaunch.

<img src="Images/Settings%20section.png" width="700" alt="Settings module">

**About module** — Version, OCR engine, license, and a one-click update check that hits the GitHub releases API.

<img src="Images/About%20section.png" width="700" alt="About module">

**In-game overlay** — Tier-colored card with mineral name, the (Tier) qualifier on a second line at half-size, the cross-section value, and a progress bar that drains over the configured duration. Always-on-top, drag-to-place via PLACE OVERLAY in Settings.

<img src="Images/Popup%20overlay.png" width="320" alt="In-game overlay popup">

---

## What's new in 6.0

- **Full UI rewrite** — React + pywebview replaces the legacy tkinter app. Five focused modules (Scanner / Index / Region / Settings / About) on a sci-fi console aesthetic.
- **Live overlay window** — Standalone always-on-top webview. Drag-to-place over the running game; live scale propagation; 30%-shrunk SAVE/CANCEL toolbar; auto-hide synced to the configured duration.
- **Real DB drives the React UI** — The Index codex and reveal card now hydrate from the same `combat_analyst_db.json` the scanner uses. Ground deposits and salvage debris no longer fall through to "NO LOCK" in the reveal card.
- **Detection log** redesigned — `time | type | count | classification | signature` columns with text-overflow ellipsis so long names truncate cleanly.

---

## Features

### Core scanning
- **EasyOCR** deep-learning OCR with morphological noise filtering for clean HUD digit reads
- **SC 4.7 per-mineral identification** — Legendary through Common tiers, plus secondary minerals at lower concentrations
- **Ground deposit detection** — Distinguishes FPS hand-mining (3000) from ROC/vehicle (4000)
- **Salvage detection** — Hull panels (2000 × N) and sized wreck debris (1700 / 1850 / 2400 / 3000)
- **Configurable scan region** — One-time calibration; the scanner reads only that rectangle every screenshot

### Overlay
- **Standalone webview window** — Frameless, on-top, opaque dark card matching the SC sci-fi palette
- **Drag-to-place** — PLACE OVERLAY in Settings; drop the live card anywhere on screen, click SAVE
- **Live scaling** — Slider in Settings updates a visible overlay instantly (50%–200%)
- **Configurable duration** — 1–30 seconds; the progress bar drains over that exact duration

### Workflow
- **Folder monitoring** via `watchdog` — every new `.png/.jpg/.webp/.bmp` triggers a scan
- **PING** — Manual scan of any image file
- **Detection log** — Time, type, count, classification, signature value
- **Signature codex** — Full DB browseable in the Index module
- **One-click update check** — From the About module; queries GitHub Releases

---

## Requirements

- **Windows 10 / 11** with the **Microsoft Edge WebView2 Runtime** (preinstalled on Win10 1903+ and all Win11)
- **Star Citizen** in Windowed or Borderless Windowed mode (the always-on-top overlay can't paint over exclusive-fullscreen)

---

## Quick Start

### For users (executable)

1. Download `SC_Signature_Scanner_v6.0.0.zip` from the latest release
2. Extract anywhere — no install, no admin
3. Run `SC_Signature_Scanner.exe`
4. Calibrate your scan region in **REGION** (one time)
5. Set your screenshot folder in **SCANNER**, click **ENGAGE**
6. Press **PrintScreen** in-game when a signature is on your HUD

### For developers (Python from source)

```bash
git clone https://github.com/Diftic/SC_Signature_Scanner.git
cd SC_Signature_Scanner
pip install -r requirements.txt
python app_webview.py
```

> First run downloads ~115 MB of EasyOCR model files to `~/.EasyOCR/model/`. Subsequent launches use the local cache.

---

## Signature Reference (SC 4.7+)

> SC 4.7 replaced the old rock-type system (I/C/S/P/M/Q/E) with a per-mineral signature system. The signature value identifies the **dominant mineral** in the rock (40–80% composition); rocks also contain secondary minerals at lower concentrations.

### Ship mining — asteroids & surface deposits

| Tier | Signature Range | Minerals |
|------|----------------|---------|
| **Legendary** | 3170–3200 | Quantainium (3170), Stileron (3185), Savrilium (3200) |
| **Epic** | 3370–3400 | Ouratite (3370), Riccite (3385), Lindinium (3400) |
| **Rare** | 3540–3600 | Beryl (3540), Taranite (3555), Borase (3570), Gold (3585), Bexalite (3600) |
| **Uncommon** | 3825–3900 | Laranite (3825), Aslarite (3840), Titanium (3855), Tungsten (3870), Agricium (3885), Torite (3900) |
| **Common** | 4180–4300 | Hephaestanite (4180), Tin (4195), Quartz (4210), Corundum (4225), Copper (4240), Silicon (4255), Iron (4270), Aluminum (4285), Ice (4300) |

Applies to both asteroids and surface deposits (Prospector / MOLE).

### Ground deposits

100% single mineral per cluster. Signature identifies **size**, not mineral type.

| Variant | Signature | Method |
|---------|-----------|--------|
| Small | 3000 | FPS / Hand mining |
| Large | 4000 | ROC / Vehicle mining |

**Possible minerals:** Hadanite, Dolivine, Aphorite, Beradom, Glacosite, Feynmaline, Jaclium, Sadaryx, Janalite, Saldynium, Carinite

> **Collision:** Large ground deposits (4000) share a signature with Common-tier ship-mining rocks. Context (planet surface vs. space) resolves it.

### Salvage

| Type | Signature | Notes |
|------|-----------|-------|
| Hull Panels / Active Scrap | 2000 | Per panel — 2000 × N |
| Small Debris | 1700 | Avenger-class wrecks, scrap cargo containers |
| Medium Debris | 1850 | Ares Inferno-class wrecks |
| Large Debris | 2400 | C2 Hercules-class wrecks |
| Capital Debris | 3000 | 890 Jump-class wrecks |

> **Collision:** Capital debris (3000) shares a signature with FPS small ground deposits. Context resolves it.

### Undetectable

Vlk Pearls, Vlk Irradiated Pearls, and Flowstone have signature 0 and cannot be detected by this scanner.

---

## Configuration

User settings live in `config.json` next to the .exe (or in the project root when running from source):

| Setting | Description |
|---------|-------------|
| `screenshot_folder` | Path to your Star Citizen screenshots folder |
| `popup_position_x` / `_y` | Overlay position in screen pixels |
| `popup_duration` | Auto-hide delay in seconds (1–30) |
| `popup_scale` | Size multiplier (0.5–2.0) |
| `debug_mode` | Save OCR processing intermediates |
| `debug_folder` | Where to write debug images when debug mode is on |

The OCR scan region is stored separately in `scan_region.json` (set via the REGION module).

---

## File structure

```
SC_Signature_Scanner/
├── SC_Signature_Scanner.exe   # Main executable
├── _internal/                 # PyInstaller-bundled runtime
│   ├── data/combat_analyst_db.json
│   ├── ui/main/               # React main console
│   └── ui/overlay/            # React overlay window
├── config.json                # User settings (created on first run)
└── scan_region.json           # OCR scan region (created on first calibration)
```

---

## Troubleshooting

**"No signature detected"**
- Re-calibrate the scan region in REGION — game UI scale or HUD changes can shift the signature box
- Check the screenshot captured the value clearly (no motion blur, full opacity)

**"OCR not available"**
- First run requires internet to download the ~115 MB EasyOCR model files
- Check `~/.EasyOCR/model/` exists after the initial download completes

**Overlay not appearing over the game**
- Star Citizen must be in **Windowed** or **Borderless Windowed** mode — exclusive fullscreen blocks always-on-top overlays
- Verify the saved overlay position isn't off-screen (Settings → CENTER button resets to 1920×1080)

**Wrong identification — collision-prone signatures**
- Sig **4000** matches Large Ground Deposits AND Common-tier ship rocks → context required
- Sig **3000** matches FPS Ground Deposits AND Capital (890 Jump) wreck debris → context required

**Slow startup**
- Normal — PyTorch + EasyOCR take 15–20 seconds to initialize on first launch
- The splash screen shows progress while loading

---

## Data sources

Signatures extracted directly from Star Citizen game files (`Game2.dcb` via `Data.p4k`) — see the `sc_data_extractor` tooling in the repo history.

---

## Credits

- **Developer:** Mallachi
- **Test crew:** Raychaser (Regolith.Rocks), iambass, Mavyre
- ✦ *In memory of Regolith.Rocks — The Industrial Community*

---

## License

MIT License — Free to use, modify, and distribute. See [LICENSE](LICENSE) for details.

*Not affiliated with Cloud Imperium Games or Roberts Space Industries.*
