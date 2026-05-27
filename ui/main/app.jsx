// Main app — radial nav + module switching + detection state
const { useState, useEffect, useRef, useCallback } = React;

const MODULES = [
  { id: 'scanner',  label: 'SCANNER',  code: '01', glyph: '◉' },
  { id: 'index',    label: 'INDEX',    code: '02', glyph: '≡' },
  { id: 'region',   label: 'REGION',   code: '03', glyph: '⊞' },
  { id: 'settings', label: 'SETTINGS', code: '04', glyph: '⚙' },
  { id: 'about',    label: 'ABOUT',    code: '05', glyph: 'ⓘ' },
];

function useTime() {
  const [t, setT] = useState(() => new Date());
  useEffect(() => {
    const i = setInterval(() => setT(new Date()), 1000);
    return () => clearInterval(i);
  }, []);
  return t;
}
const fmtTime = (d) => d.toTimeString().slice(0, 8);

function App() {
  const [mod, setMod] = useState('scanner');
  const [monitoring, setMonitoring] = useState(false);
  const [detections, setDetections] = useState([]);
  const [region, setRegion] = useState(null);
  const [regionBusy, setRegionBusy] = useState(false);
  const [ocrEngine, setOcrEngine] = useState('—');
  const [version, setVersion] = useState('');
  const [versionDev, setVersionDev] = useState('');
  const [screenshotFolder, setScreenshotFolder] = useState('');
  const [codexFilter, setCodexFilter] = useState('all');
  const [settings, setSettings] = useState({
    popupX: 1920, popupY: 1080, duration: 10, scale: 100, debug: false, debugFolder: '',
  });
  const settingsSaveTimer = useRef(null);
  const [bridgeReady, setBridgeReady] = useState(
    typeof window !== 'undefined'
    && !!window.pywebview
    && !!window.pywebview.api
    && typeof window.pywebview.api.get_initial_state === 'function'
  );

  const latest = detections[detections.length - 1] || null;
  const time = useTime();

  // Wait for pywebview.api to be injected
  useEffect(() => {
    if (bridgeReady) return;
    const onReady = () => setBridgeReady(true);
    window.addEventListener('pywebviewready', onReady);
    return () => window.removeEventListener('pywebviewready', onReady);
  }, [bridgeReady]);

  // Bootstrap initial state and settings from Python
  useEffect(() => {
    if (!bridgeReady) return;
    Promise.all([
      window.pywebview.api.get_initial_state(),
      window.pywebview.api.get_settings(),
      window.pywebview.api.get_scan_region(),
      window.pywebview.api.get_signature_db(),
    ]).then(([state, sets, reg, db]) => {
      if (state && typeof state.screenshotFolder === 'string') {
        setScreenshotFolder(state.screenshotFolder);
      }
      if (state && state.ocrEngine) setOcrEngine(state.ocrEngine);
      if (state && state.version) setVersion(state.version);
      if (state && state.versionDev) setVersionDev(state.versionDev);
      if (sets) setSettings(sets);
      if (reg) setRegion(reg);
      if (db) {
        window.MINERALS = db.minerals || [];
        window.GROUND = db.ground || [];
        window.SALVAGE = db.salvage || [];
        window.ALL_SIGNATURES = [...window.MINERALS, ...window.GROUND, ...window.SALVAGE]
          .sort((a, b) => a.sig - b.sig);
      }
    }).catch(err => console.error('bootstrap failed', err));
  }, [bridgeReady]);

  const ingestSig = useCallback((sig, file, override) => {
    // Prefer Python-side matches when present (they understand count
    // multiples, salvage panels, debris bases). Fall back to the JS-side
    // codex lookup only when Python returned nothing.
    const pyMatches = override?.pythonMatches;
    let match = null;
    let collisions = [];
    if (pyMatches && pyMatches.length > 0) {
      match = pyMatches[0];
      collisions = pyMatches.slice(1);
    } else if (sig != null) {
      const r = window.lookupSignature(sig);
      match = r?.match || null;
      collisions = r?.collisions || [];
    }

    const entry = {
      id: Date.now() + Math.random(),
      time: fmtTime(new Date()),
      sig: sig ?? 0,
      file: file || `ScreenShot-${Date.now()}.jpg`,
      match,
      collisions,
      ...(override || {}),
    };
    setDetections(d => [...d, entry].slice(-100));
  }, []);

  // Receive detections pushed from Python
  useEffect(() => {
    window.onDetection = (payload) => {
      ingestSig(payload.sig, payload.file, {
        time: payload.time || fmtTime(new Date()),
        error: payload.error || null,
        pythonMatches: payload.matches || [],
        ocrConfidence: payload.ocrConfidence ?? null,
      });
    };
    return () => { delete window.onDetection; };
  }, [ingestSig]);

  // Toggle monitoring through the bridge
  const toggleMonitoring = useCallback(async () => {
    if (!bridgeReady) return;
    try {
      if (monitoring) {
        await window.pywebview.api.stop_monitoring();
        setMonitoring(false);
      } else {
        const result = await window.pywebview.api.start_monitoring();
        if (result && result.ok) {
          setMonitoring(true);
        } else {
          alert(result?.error || 'Failed to start monitoring');
        }
      }
    } catch (err) {
      console.error('toggleMonitoring failed', err);
    }
  }, [bridgeReady, monitoring]);

  const browseFolder = useCallback(async () => {
    if (!bridgeReady) return;
    try {
      const picked = await window.pywebview.api.pick_screenshot_folder();
      if (picked) setScreenshotFolder(picked);
    } catch (err) {
      console.error('pick_screenshot_folder failed', err);
    }
  }, [bridgeReady]);

  const persistFolderEdit = useCallback((value) => {
    setScreenshotFolder(value);
    if (bridgeReady) {
      window.pywebview.api.set_screenshot_folder(value).catch(err =>
        console.error('set_screenshot_folder failed', err));
    }
  }, [bridgeReady]);

  const simulateDetection = useCallback(() => {
    if (!bridgeReady) return;
    window.pywebview.api.test_detection().catch(err =>
      console.error('test_detection failed', err));
  }, [bridgeReady]);

  // Settings: update local state immediately, persist to Python with a 200 ms debounce
  const persistSettings = useCallback((updater) => {
    setSettings(prev => {
      const next = typeof updater === 'function' ? updater(prev) : { ...prev, ...updater };
      if (bridgeReady) {
        if (settingsSaveTimer.current) clearTimeout(settingsSaveTimer.current);
        settingsSaveTimer.current = setTimeout(() => {
          window.pywebview.api.save_settings(next).catch(err =>
            console.error('save_settings failed', err));
        }, 200);
      }
      return next;
    });
  }, [bridgeReady]);

  const browseDebugFolder = useCallback(async () => {
    if (!bridgeReady) return;
    try {
      const picked = await window.pywebview.api.pick_debug_folder();
      if (picked) setSettings(prev => ({ ...prev, debugFolder: picked }));
    } catch (err) {
      console.error('pick_debug_folder failed', err);
    }
  }, [bridgeReady]);

  const pickRegion = useCallback(async () => {
    if (!bridgeReady || regionBusy) return;
    setRegionBusy(true);
    try {
      const result = await window.pywebview.api.pick_region();
      if (result?.ok && result.region) setRegion(result.region);
    } catch (err) {
      console.error('pick_region failed', err);
    } finally {
      setRegionBusy(false);
    }
  }, [bridgeReady, regionBusy]);

  const clearRegion = useCallback(async () => {
    if (!bridgeReady) return;
    try {
      await window.pywebview.api.clear_scan_region();
      setRegion(null);
    } catch (err) {
      console.error('clear_scan_region failed', err);
    }
  }, [bridgeReady]);

  const placeOverlay = useCallback(() => {
    if (!bridgeReady) return;
    window.pywebview.api.enter_overlay_placement_mode().catch(err =>
      console.error('enter_overlay_placement_mode failed', err));
  }, [bridgeReady]);

  const testOverlay = useCallback(() => {
    if (!bridgeReady) return;
    window.pywebview.api.test_overlay().catch(err =>
      console.error('test_overlay failed', err));
  }, [bridgeReady]);

  // PLACE OVERLAY confirms a new (x, y) on the Python side; bridge pushes it
  // back here so the Settings X/Y readouts reflect what was actually saved.
  useEffect(() => {
    if (!bridgeReady) return;
    window.onOverlayPositionSaved = (payload) => {
      if (!payload) return;
      setSettings(prev => ({
        ...prev,
        popupX: payload.popupX ?? prev.popupX,
        popupY: payload.popupY ?? prev.popupY,
      }));
    };
    return () => { delete window.onOverlayPositionSaved; };
  }, [bridgeReady]);

  return (
    <div className="console-root">
      <BackgroundFX />
      <RivetBar className="top-bar">
        <div className="brand-block pywebview-drag-region">
          <div className="brand-lockup">
            <span className="brand-mark">⛏</span>
            <div>
              <div className="brand-name">SIGNATURE SCANNER</div>
              <div className="brand-sub">STAR CITIZEN · TARGET ID</div>
            </div>
          </div>
        </div>
        <div className="top-meta">
          <Readout label="SYS" value="ONLINE" accent="var(--green)" glow />
          <Readout label="UEE STD" value={fmtTime(time)} />
          <Readout label="OCR" value="READY" accent="var(--green)" />
          <Readout label="LATENCY" value="42ms" />
          <WindowControls bridgeReady={bridgeReady} />
        </div>
      </RivetBar>

      <div className="console-body">
        <RadialNav mod={mod} setMod={setMod} version={version} />
        <main className="module-stage">
          {mod === 'scanner' && (
            <ScannerPanel
              detections={detections}
              monitoring={monitoring}
              toggleMonitoring={toggleMonitoring}
              simulateDetection={simulateDetection}
              screenshotFolder={screenshotFolder}
              setScreenshotFolder={persistFolderEdit}
              browseFolder={browseFolder}
              bridgeReady={bridgeReady}
              latest={latest}
            />
          )}
          {mod === 'region' && (
            <RegionPanel
              region={region}
              pickRegion={pickRegion}
              clearRegion={clearRegion}
              bridgeReady={bridgeReady}
              busy={regionBusy}
            />
          )}
          {mod === 'settings' && (
            <SettingsPanel
              settings={settings}
              setSettings={persistSettings}
              browseDebugFolder={browseDebugFolder}
              bridgeReady={bridgeReady}
              placeOverlay={placeOverlay}
              testOverlay={testOverlay}
            />
          )}
          {mod === 'codex' && <CodexPanel filter={codexFilter} setFilter={setCodexFilter} />}
          {mod === 'index' && <IndexPanel activeSig={latest?.sig} />}
          {mod === 'about' && <AboutPanel version={version} versionDev={versionDev} ocrEngine={ocrEngine} bridgeReady={bridgeReady} />}
        </main>
        <TelemetryRail latest={latest} monitoring={monitoring} detections={detections} />
      </div>

      <RivetBar className="bottom-bar">
        <div className="ticker">
          <div className="ticker-content">
            <span>◆ Windowed/Borderless required for in-game overlay</span>
            <span>◆ {detections.length} signatures processed this session</span>
            <span>◆ Region {region ? 'LOCKED' : 'UNSET'}</span>
            <span>◆ {ocrEngine} engine warm</span>
            <span>◆ In memory of Regolith.Rocks — The Industrial Community</span>
          </div>
        </div>
      </RivetBar>
    </div>
  );
}

function RadialNav({ mod, setMod, version }) {
  return (
    <nav className="radial-nav">
      <div className="rn-frame">
        <div className="rn-header">
          <Stencil size="sm">MODULES</Stencil>
        </div>
        <div className="rn-list">
          {MODULES.map(m => (
            <button
              key={m.id}
              className={`rn-item ${mod === m.id ? 'active' : ''} ${m.disabled ? 'disabled' : ''}`}
              onClick={() => !m.disabled && setMod(m.id)}
              disabled={m.disabled}
              title={m.disabled ? 'Coming in a later phase' : undefined}
            >
              <span className="rn-glyph">{m.glyph}</span>
              <span className="rn-text">
                <span className="rn-code">{m.code}</span>
                <span className="rn-label">{m.label}</span>
              </span>
              <span className="rn-rail" />
            </button>
          ))}
        </div>
        <div className="rn-footer">
          <span className="rn-version">{version ? `Version ${version}` : '—'}</span>
        </div>
      </div>
    </nav>
  );
}

function TelemetryRail({ latest, monitoring, detections }) {
  // recent tier histogram
  const counts = { legendary: 0, epic: 0, rare: 0, uncommon: 0, common: 0, salvage: 0 };
  detections.slice(-30).forEach(d => { if (d.match && counts[d.match.tier] != null) counts[d.match.tier]++; });
  const max = Math.max(1, ...Object.values(counts));
  return (
    <aside className="telemetry-rail">
      <Panel title="TELEMETRY" code="TLM" accent="var(--amber)" parallax={false}>
        <div className="tlm-stack">
          <LED state={monitoring ? 'green' : 'amber'} label={monitoring ? 'MONITORING' : 'STANDBY'} blink={monitoring} />
          <LED state="green" label="OCR ENGINE" />
          <LED state="green" label="OVERLAY" />
          <LED state={latest?.match ? 'green' : 'amber'} label={latest?.match ? 'TARGET LOCK' : 'NO TARGET'} />
        </div>
        <div className="tlm-divider" />
        <div className="tlm-section-title">TIER FREQUENCY · LAST 30</div>
        <div className="tlm-hist">
          {Object.entries(counts).map(([k, v]) => {
            const t = window.TIERS[k];
            return (
              <div key={k} className="tlm-bar-row">
                <span className="tlm-bar-label" style={{ color: t.color }}>{t.label}</span>
                <span className="tlm-bar-track"><span className="tlm-bar-fill" style={{ width: `${(v/max)*100}%`, background: t.color }} /></span>
                <span className="tlm-bar-count">{v}</span>
              </div>
            );
          })}
        </div>
        <div className="tlm-divider" />
        <div className="tlm-section-title">LAST READ</div>
        {latest ? (
          <div className="tlm-last">
            <div className="tlm-last-sig">{latest.sig.toLocaleString()}</div>
            <div className="tlm-last-name" style={{ color: window.TIERS[latest.match?.tier || 'unknown'].color }}>
              {latest.match?.name || 'NO LOCK'}
            </div>
            <div className="tlm-last-time">{latest.time}</div>
          </div>
        ) : <div className="tlm-empty">— NO DATA —</div>}
      </Panel>
    </aside>
  );
}

function BackgroundFX() {
  return (
    <div className="bg-fx" aria-hidden>
      <div className="bg-stars" />
      <div className="bg-vignette" />
      <div className="bg-scanlines" />
    </div>
  );
}

function WindowControls({ bridgeReady }) {
  const call = (name) => () => {
    if (!bridgeReady || !window.pywebview?.api?.[name]) return;
    window.pywebview.api[name]();
  };
  return (
    <div className="win-controls">
      <button className="win-btn" onClick={call('minimize_window')} title="Minimize" aria-label="Minimize">—</button>
      <button className="win-btn close" onClick={call('close_window')} title="Close" aria-label="Close">×</button>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
