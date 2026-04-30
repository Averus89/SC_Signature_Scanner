// Region / Settings / Codex / Overlay panels
const { useState, useEffect, useRef } = React;

// ============ REGION PANEL ============
function RegionPanel({ region, setRegion }) {
  const [drag, setDrag] = useState(null);
  const stageRef = useRef(null);

  const onDown = (e) => {
    const r = stageRef.current.getBoundingClientRect();
    setDrag({ x0: e.clientX - r.left, y0: e.clientY - r.top, x1: e.clientX - r.left, y1: e.clientY - r.top });
  };
  const onMove = (e) => {
    if (!drag) return;
    const r = stageRef.current.getBoundingClientRect();
    setDrag(d => ({ ...d, x1: e.clientX - r.left, y1: e.clientY - r.top }));
  };
  const onUp = () => {
    if (drag) {
      const x = Math.min(drag.x0, drag.x1), y = Math.min(drag.y0, drag.y1);
      const w = Math.abs(drag.x1 - drag.x0), h = Math.abs(drag.y1 - drag.y0);
      if (w > 8 && h > 8) setRegion({ x: Math.round(x*5), y: Math.round(y*5), w: Math.round(w*5), h: Math.round(h*5) });
    }
    setDrag(null);
  };

  const box = drag ? {
    left: Math.min(drag.x0, drag.x1),
    top: Math.min(drag.y0, drag.y1),
    width: Math.abs(drag.x1 - drag.x0),
    height: Math.abs(drag.y1 - drag.y0),
  } : null;

  return (
    <div className="region-grid">
      <Panel title="SCAN REGION CALIBRATION" code="REG-05" accent="var(--amber)">
        <div className="region-instructions">
          <Stencil>STEP 01</Stencil> Drag a rectangle over the in-game signature value.
          <br /><Stencil>STEP 02</Stencil> Confirm. Calibration persists across sessions.
        </div>
        <div className="region-stage" ref={stageRef}
             onMouseDown={onDown} onMouseMove={onMove} onMouseUp={onUp} onMouseLeave={onUp}>
          <div className="region-fake-hud">
            <div className="hud-readout">
              <div className="hud-label">SIGNATURE</div>
              <div className="hud-value">3,900</div>
            </div>
            <div className="hud-corner tl" /><div className="hud-corner tr" />
            <div className="hud-corner bl" /><div className="hud-corner br" />
            <div className="hud-noise" />
          </div>
          {box && <div className="region-selection" style={box}><span>{box.width.toFixed(0)}×{box.height.toFixed(0)}</span></div>}
          {region && !drag && (
            <div className="region-saved" style={{ left: region.x/5, top: region.y/5, width: region.w/5, height: region.h/5 }}>
              <span>SAVED</span>
            </div>
          )}
          <div className="region-crosshair" />
        </div>
      </Panel>

      <Panel title="REGION DATA" code="REG-DAT" accent="var(--amber)">
        <div className="region-data">
          <Readout label="ORIGIN" value={region ? `${region.x},${region.y}` : '—'} />
          <Readout label="SIZE"   value={region ? `${region.w}×${region.h}` : '—'} />
          <Readout label="STATUS" value={region ? 'LOCKED' : 'UNSET'} accent={region ? 'var(--green)' : 'var(--red)'} glow />
        </div>
        <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
          <MrButton small onClick={() => setRegion(null)}>CLEAR</MrButton>
          <MrButton small primary onClick={() => setRegion({ x: 2360, y: 358, w: 405, h: 158 })}>USE LAST KNOWN</MrButton>
        </div>
      </Panel>
    </div>
  );
}

// ============ SETTINGS PANEL ============
function SettingsPanel({ settings, setSettings, browseDebugFolder, bridgeReady }) {
  const upd = (k, v) => setSettings(s => ({ ...s, [k]: v }));
  const stageRef = useRef(null);
  const [dragging, setDragging] = useState(false);

  const onCardDown = (e) => {
    e.preventDefault();
    setDragging(true);
  };
  useEffect(() => {
    if (!dragging) return;
    const onMove = (e) => {
      const r = stageRef.current.getBoundingClientRect();
      const fx = (e.clientX - r.left) / r.width;
      const fy = (e.clientY - r.top) / r.height;
      const x = Math.max(0, Math.min(3840, Math.round(fx * 3840)));
      const y = Math.max(0, Math.min(2160, Math.round(fy * 2160)));
      setSettings(s => ({ ...s, popupX: x, popupY: y }));
    };
    const onUp = () => setDragging(false);
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
  }, [dragging, setSettings]);

  return (
    <div className="settings-grid">
      <Panel title="OVERLAY POSITION" code="OVR-06" status={<span className="log-count">DRAG TO PLACE</span>}>
        <div className="settings-instructions">
          <Stencil>STEP 01</Stencil> Grab the overlay and drag it to the desired position on the game screen.
          <br /><Stencil>STEP 02</Stencil> Position persists across sessions.
        </div>
        <div className="settings-screen" ref={stageRef}>
          <div className="screen-label">VIEWPORT 3840 × 2160</div>
          <div className="screen-grid" />
          <div className={`screen-handle ${dragging ? 'dragging' : ''}`}
               onMouseDown={onCardDown}
               style={{
                 left: `${(settings.popupX / 3840) * 100}%`,
                 top: `${(settings.popupY / 2160) * 100}%`,
               }}>
            <div className="screen-handle-card">
              <div className="shc-tier-bar" />
              <div className="shc-name">SIGNATURE</div>
              <div className="shc-val">3,900</div>
            </div>
          </div>
        </div>
        <div className="settings-row">
          <Readout label="X" value={settings.popupX} />
          <Readout label="Y" value={settings.popupY} />
          <MrButton small onClick={() => setSettings(s => ({ ...s, popupX: 1920, popupY: 1080 }))}>CENTER</MrButton>
        </div>
      </Panel>

      <Panel title="OVERLAY BEHAVIOR" code="OVR-07">
        <div className="settings-stack">
          <label className="lbl">DURATION
            <input type="range" min="1" max="30" value={settings.duration} onChange={e => upd('duration', +e.target.value)} />
            <span className="val">{settings.duration}s</span>
          </label>
          <label className="lbl">SCALE
            <input type="range" min="50" max="200" value={settings.scale} onChange={e => upd('scale', +e.target.value)} />
            <span className="val">{settings.scale}%</span>
          </label>
          <label className="lbl row">
            <input type="checkbox" checked={settings.debug} onChange={e => upd('debug', e.target.checked)} />
            <span>ENABLE DEBUG OUTPUT</span>
          </label>
        </div>
        <div style={{ marginTop: 12 }}>
          <MrButton small disabled title="Available in Phase 3 (overlay window migration)">TEST OVERLAY</MrButton>
        </div>
      </Panel>

      <Panel title="STORAGE" code="STO-08">
        <div className="settings-stack">
          <div className="mon-folder">
            <div className="mon-label">DEBUG OUTPUT FOLDER</div>
            <div className="mon-folder-row">
              <input
                className="mr-input"
                value={settings.debugFolder || ''}
                onChange={e => upd('debugFolder', e.target.value)}
                placeholder="(unset — debug output disabled)"
              />
              <MrButton small icon="▸" onClick={browseDebugFolder} disabled={!bridgeReady}>BROWSE</MrButton>
            </div>
          </div>
          <Readout label="OCR ENGINE" value="EasyOCR" accent="var(--green)" />
          <Readout label="SC PATCH" value="4.7+" />
        </div>
      </Panel>
    </div>
  );
}

// ============ CODEX PANEL ============
function CodexPanel({ filter, setFilter }) {
  const cats = ['all', 'ship', 'ground', 'salvage'];
  const entries = window.ALL_SIGNATURES.filter(e => filter === 'all' ? true : e.cat === filter);
  return (
    <div className="codex-grid">
      <Panel title="MINERAL & TARGET CODEX" code="CDX-09" accent="var(--amber)" status={<span>{entries.length} ENTRIES</span>}>
        <div className="codex-tabs">
          {cats.map(c => (
            <button key={c} className={`codex-tab ${filter === c ? 'active' : ''}`} onClick={() => setFilter(c)}>
              {c.toUpperCase()}
            </button>
          ))}
        </div>
        <div className="codex-list">
          {entries.map(e => {
            const t = window.TIERS[e.tier];
            return (
              <div key={e.sig + e.name} className="codex-row" style={{ '--tier': t.color }}>
                <span className="codex-sig">{e.sig.toLocaleString()}</span>
                <span className="codex-tier" style={{ color: t.color }}>{t.label}</span>
                <span className="codex-name">{e.name}</span>
                <span className="codex-notes">{e.notes}</span>
              </div>
            );
          })}
        </div>
      </Panel>
    </div>
  );
}

// ============ OVERLAY PREVIEW (HUD module) ============
function OverlayPreview({ latest, settings }) {
  const sample = latest || { sig: 3584, match: { tier: 'rare', name: 'Borase + Bexalite', cat: 'ship', notes: 'Mid-tier · 12.5K cluster' }, time: '00:00:00' };
  return (
    <Panel title="IN-GAME OVERLAY PREVIEW" code="HUD-10" accent="var(--amber)"
           status={<span className="log-count">CONFIGURE IN SETTINGS</span>}>
      <div className="hud-stage">
        <div className="hud-stage-bg" />
        <div className="hud-stage-vignette" />
        <div className="hud-stage-cockpit" />
        <div className="hud-stage-card-wrap" style={{ transform: `translate(-50%,-50%) scale(${settings.scale / 100})` }}>
          <OverlayCard latest={sample} />
        </div>
      </div>
      <div className="hud-stats">
        <Readout label="POSITION" value={`${settings.popupX},${settings.popupY}`} />
        <Readout label="DURATION" value={`${settings.duration}s`} />
        <Readout label="SCALE" value={`${settings.scale}%`} />
      </div>
    </Panel>
  );
}

function OverlayCard({ latest }) {
  if (!latest) return <div className="overlay-card empty"><Stencil>AWAITING SIGNAL</Stencil></div>;
  const m = latest.match;
  const t = window.TIERS[m?.tier] || window.TIERS.unknown;
  return (
    <div className="overlay-card" style={{ '--tier': t.color }}>
      <div className="ovc-corners">
        <span className="ovc-corner tl" /><span className="ovc-corner tr" />
        <span className="ovc-corner bl" /><span className="ovc-corner br" />
      </div>
      <div className="ovc-rivets" />
      <div className="ovc-header">
        <span className="ovc-code">SIG-{latest.sig}</span>
        <span className="ovc-tier" style={{ color: t.color }}>{t.label}</span>
      </div>
      <div className="ovc-name">{m?.name || 'NO LOCK'}</div>
      <div className="ovc-sig-readout">
        <span className="ovc-sig-label">CROSS-SECTION</span>
        <span className="ovc-sig-val">{latest.sig.toLocaleString()}</span>
      </div>
      <div className="ovc-meta">
        <span>{m?.cat?.toUpperCase() || '—'}</span>
        <span className="ovc-dot" />
        <span>{m?.notes?.split('—')[0] || ''}</span>
      </div>
      <div className="ovc-progress"><div className="ovc-progress-fill" /></div>
    </div>
  );
}

// ============ INDEX PANEL ============
// Top-level signatures module — class -> tier -> entries
function IndexPanel({ activeSig }) {
  const [section, setSection] = React.useState('ship');
  const [activeTier, setActiveTier] = React.useState('legendary');
  const tiers = window.TIERS;

  const SECTIONS = [
    { id: 'ship',    label: 'SHIP MINING',   sub: 'PER-MINERAL', tiers: ['legendary','epic','rare','uncommon','common'] },
    { id: 'ground',  label: 'GROUND',        sub: 'BY SIZE',     tiers: ['ground_l','ground_s'] },
    { id: 'salvage', label: 'SALVAGE',       sub: 'BY HULL',     tiers: ['salvage'] },
  ];

  const currentSection = SECTIONS.find(s => s.id === section);
  const currentTierKey = currentSection.tiers.includes(activeTier) ? activeTier : currentSection.tiers[0];
  const currentTier = tiers[currentTierKey];

  const entriesFor = (tk) => {
    if (tk === 'salvage') return window.SALVAGE;
    if (tk === 'ground_s' || tk === 'ground_l') return window.GROUND.filter(g => g.tier === tk);
    return window.ALL_SIGNATURES.filter(e => e.tier === tk).sort((a,b) => a.sig - b.sig);
  };
  const currentEntries = entriesFor(currentTierKey);

  const switchSection = (sid) => {
    setSection(sid);
    setActiveTier(SECTIONS.find(s => s.id === sid).tiers[0]);
  };

  return (
    <div className="idx-grid">
      <Panel title="SIGNATURE INDEX" code="IDX" accent="var(--amber)" parallax={false}
             status={<span className="log-count">{window.ALL_SIGNATURES.length} ENTRIES · {SECTIONS.length} CLASSES</span>}>
        <div className="idx-classbar">
          {SECTIONS.map(s => {
            const count = s.tiers.reduce((a, tk) => a + entriesFor(tk).length, 0);
            return (
              <button key={s.id} className={`idx-class ${section === s.id ? 'active' : ''}`} onClick={() => switchSection(s.id)}>
                <span className="idx-class-sub">{s.sub}</span>
                <span className="idx-class-label">{s.label}</span>
                <span className="idx-class-count">{count}</span>
              </button>
            );
          })}
        </div>

        <div className="idx-body">
          <aside className="idx-rail">
            <div className="idx-rail-header">TIERS</div>
            {currentSection.tiers.map(tk => {
              const t = tiers[tk];
              const ents = entriesFor(tk);
              const isActive = currentTierKey === tk;
              return (
                <button key={tk} className={`idx-rail-item ${isActive ? 'active' : ''}`}
                        style={{ '--tier': t.color }}
                        onClick={() => setActiveTier(tk)}>
                  <span className="idx-rail-bar" />
                  <span className="idx-rail-label">{t.label}</span>
                  <span className="idx-rail-range">{t.range}</span>
                  <span className="idx-rail-count">{ents.length}</span>
                </button>
              );
            })}
          </aside>

          <div className="idx-detail" style={{ '--tier': currentTier.color }}>
            <header className="idx-detail-head">
              <div className="idx-detail-head-l">
                <span className="idx-detail-eyebrow">{currentSection.label}</span>
                <h2 className="idx-detail-title">{currentTier.label}</h2>
              </div>
              <div className="idx-detail-head-r">
                <div className="idx-detail-stat">
                  <span className="idx-detail-stat-l">RANGE</span>
                  <span className="idx-detail-stat-v">{currentTier.range}</span>
                </div>
                <div className="idx-detail-stat">
                  <span className="idx-detail-stat-l">COUNT</span>
                  <span className="idx-detail-stat-v">{currentEntries.length}</span>
                </div>
              </div>
            </header>

            {section === 'ground' && currentTierKey === currentSection.tiers[0] && <GroundCallout />}

            <div className="idx-entries">
              <div className="idx-entries-head">
                <span>SIG</span>
                <span>{section === 'salvage' ? 'CLASS' : 'NAME'}</span>
                <span>NOTES</span>
              </div>
              {currentEntries.map(e => {
                const active = activeSig != null && Math.abs(e.sig - activeSig) <= 8;
                return (
                  <div key={e.sig + e.name} className={`idx-entry ${active ? 'active' : ''}`}>
                    <span className="idx-entry-sig">{e.sig.toLocaleString()}</span>
                    <span className="idx-entry-name">{e.name}</span>
                    <span className="idx-entry-notes">{e.notes}</span>
                  </div>
                );
              })}
            </div>

            {section === 'salvage' && (
              <div className="idx-footnote">
                ⚠ Hull panels stack — total = 2,000 × N. Capital debris (3,000) collides with FPS ground deposits.
              </div>
            )}
          </div>
        </div>
      </Panel>
    </div>
  );
}

function GroundCallout() {
  const minerals = ['Hadanite','Dolivine','Aphorite','Beradom','Glacosite','Feynmaline','Jaclium','Sadaryx','Janalite','Saldynium','Carinite'];
  return (
    <div className="idx-callout">
      <span className="idx-callout-tag">FYI</span>
      <span className="idx-callout-text">100% single mineral per cluster — sig identifies size, not type. Visual ID required.</span>
      <div className="idx-callout-chips">
        {minerals.map(m => <span key={m} className="idx-chip">{m}</span>)}
      </div>
    </div>
  );
}

Object.assign(window, { RegionPanel, SettingsPanel, CodexPanel, OverlayPreview, OverlayCard, IndexPanel });
