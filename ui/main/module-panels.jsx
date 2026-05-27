// Region / Settings / Codex / Overlay panels
const { useState } = React;

// ============ REGION PANEL ============
function RegionPanel({ region, pickRegion, pickRegionFromLive, clearRegion, bridgeReady, busy }) {
  const r = region || null;
  return (
    <div className="region-grid">
      <Panel title="SCAN REGION CALIBRATION" code="REG-05" accent="var(--amber)">
        <div className="region-instructions">
          <Stencil>STEP 01</Stencil> Click PICK REGION — choose a screenshot, drag a rectangle over the in-game signature value, click Save.
          <br /><Stencil>STEP 02</Stencil> The scanner reads OCR from this rectangle on every screenshot. Calibration persists across sessions.
        </div>
        <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
          <MrButton small primary onClick={pickRegion} disabled={!bridgeReady || busy}>
            {busy ? 'PICKING…' : 'PICK REGION'}
          </MrButton>
          <MrButton small onClick={pickRegionFromLive} disabled={!bridgeReady || busy}>
            PICK FROM LIVE FRAME
          </MrButton>
          <MrButton small onClick={clearRegion} disabled={!bridgeReady || !r || busy}>CLEAR</MrButton>
        </div>
      </Panel>

      <Panel title="REGION DATA" code="REG-DAT" accent="var(--amber)">
        <div className="region-data">
          <Readout label="TOP-LEFT"     value={r ? `${r.x1}, ${r.y1}` : '—'} />
          <Readout label="BOTTOM-RIGHT" value={r ? `${r.x2}, ${r.y2}` : '—'} />
          <Readout label="SIZE"         value={r ? `${r.width}×${r.height}` : '—'} />
          <Readout label="STATUS"
                   value={r ? 'LOCKED' : 'UNSET'}
                   accent={r ? 'var(--green)' : 'var(--red)'} glow />
        </div>
      </Panel>
    </div>
  );
}

// ============ SETTINGS PANEL ============
function SettingsPanel({
  settings, setSettings, browseDebugFolder, bridgeReady,
  placeOverlay, testOverlay,
}) {
  const upd = (k, v) => setSettings(s => ({ ...s, [k]: v }));

  return (
    <div className="settings-grid">
      <Panel title="OVERLAY POSITION" code="OVR-06" status={<span className="log-count">DRAG TO PLACE</span>}>
        <div className="settings-instructions">
          <Stencil>STEP 01</Stencil> Click PLACE OVERLAY — the live overlay appears on top of the running game.
          <br /><Stencil>STEP 02</Stencil> Drag it where you want, click SAVE. Position persists across sessions.
        </div>
        <div className="settings-row">
          <Readout label="X" value={settings.popupX} />
          <Readout label="Y" value={settings.popupY} />
          <MrButton small onClick={() => setSettings(s => ({ ...s, popupX: 1920, popupY: 1080 }))}>CENTER</MrButton>
        </div>
        <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
          <MrButton small primary onClick={placeOverlay} disabled={!bridgeReady}>PLACE OVERLAY</MrButton>
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
        </div>
        <div style={{ marginTop: 12 }}>
          <MrButton small onClick={testOverlay} disabled={!bridgeReady}>TEST OVERLAY</MrButton>
        </div>
      </Panel>

      <Panel title="LIVE CAPTURE" code="LIV-07b">
        <div className="settings-instructions">
          Knobs apply on next ENGAGE — toggling LIVE mode mid-session picks up new values.
        </div>
        <div className="settings-stack">
          <label className="lbl">PROBE RATE
            <input
              type="range"
              min="5"
              max="60"
              value={settings.liveProbeHz ?? 30}
              onChange={e => upd('liveProbeHz', +e.target.value)}
            />
            <span className="val">{settings.liveProbeHz ?? 30} Hz</span>
          </label>
          <label className="lbl row">
            <input
              type="checkbox"
              checked={!!settings.liveLogNoSignature}
              onChange={e => upd('liveLogNoSignature', e.target.checked)}
            />
            <span>LOG UNMATCHED FRAMES (diagnostic)</span>
          </label>
        </div>
      </Panel>

      <Panel title="DEBUG OUTPUT" code="DBG-08">
        <div className="settings-stack">
          <label className="lbl row">
            <input
              type="checkbox"
              checked={settings.debug}
              onChange={e => upd('debug', e.target.checked)}
            />
            <span>ENABLE DEBUG OUTPUT</span>
          </label>
          <div className="mon-folder">
            <div className="mon-label">OUTPUT FOLDER</div>
            <div className="mon-folder-row">
              <input
                className="mr-input"
                value={settings.debugFolder || ''}
                onChange={e => upd('debugFolder', e.target.value)}
                placeholder="(unset — uses default location next to exe)"
              />
              <MrButton small icon="▸" onClick={browseDebugFolder} disabled={!bridgeReady}>BROWSE</MrButton>
            </div>
          </div>
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

// ============ ABOUT PANEL ============
function AboutPanel({ version, versionDev, ocrEngine, bridgeReady }) {
  // Status pill shows the full dev string (e.g. "6.0.0.dev1"); the radial
  // nav footer + page title use the clean public version.
  const statusVersion = versionDev || version || '—';
  const [updateState, setUpdateState] = React.useState({ phase: 'idle' });

  const checkUpdates = async () => {
    if (!bridgeReady) return;
    setUpdateState({ phase: 'checking' });
    try {
      const r = await window.pywebview.api.check_for_updates();
      if (!r || !r.ok) {
        setUpdateState({ phase: 'error', message: r?.error || 'Update check failed.' });
        return;
      }
      setUpdateState({
        phase: r.isNewer ? 'newer' : 'current',
        latest: r.latestVersion,
        url: r.downloadUrl,
      });
    } catch (err) {
      setUpdateState({ phase: 'error', message: String(err) });
    }
  };

  return (
    <div className="about-grid">
      <Panel
        title="ABOUT"
        code="ABT-05"
        accent="var(--amber)"
        status={<span className="log-count">v{statusVersion}</span>}
      >
        <div className="about-header">
          <span className="about-mark">⛏</span>
          <div className="about-titleblock">
            <div className="about-title">SC SIGNATURE SCANNER</div>
            <div className="about-sub">STAR CITIZEN · TARGET IDENTIFICATION</div>
          </div>
        </div>

        <div className="about-desc">
          Monitors Star Citizen screenshots for signature values and identifies
          potential targets in real-time.
        </div>

        <div className="about-byline">
          Made in 2026 by <strong>Mallachi</strong>, ..All solutions start with a problem worth solving..
        </div>

        <div className="about-memorial">
          ✦ In memory of Regolith.Rocks — The Industrial Community
        </div>

        <div className="about-cols">
          <section className="about-section">
            <div className="about-section-title">HOW TO USE</div>
            <ol className="about-steps">
              <li>Set Star Citizen to Windowed or Borderless</li>
              <li>Define the scan region in <strong>REGION</strong></li>
              <li>Set your screenshot folder in <strong>SCANNER</strong></li>
              <li>Click <strong>ENGAGE</strong> to start monitoring</li>
              <li>In-game: PrintScreen on a signature</li>
              <li>Overlay shows the identification</li>
            </ol>
          </section>

          <section className="about-section">
            <div className="about-section-title">THANKS TO</div>
            <ul className="about-thanks">
              <li><strong>Raychaser</strong> · Regolith.Rocks · The original inspiration </li>
              <li><strong>Your name here?</strong> · Test crew</li>
              <li><strong>Your name here?</strong> · Test crew</li>
              <li>__________________________________________________________</li>
              <li><strong>ToDo in future version</strong></li>
              <li>Ability to decode ship signature values. All ships have unique minimum signature from 3 set angles. This currently creates too many overlapping results between ships when calculating sub-optimal angle of approach. Need better calculation methods.</li>
              <li>Work is in progress to solve this challenge</li>
            </ul>
          </section>
        </div>

        <div className="about-footer">
          <Readout label="OCR ENGINE" value={ocrEngine || '—'} accent="var(--green)" />
          <Readout label="UI" value="React + pywebview" />
          <Readout label="LICENSE" value="MIT" />
        </div>

        <div className="about-update">
          <MrButton
            small
            primary
            onClick={checkUpdates}
            disabled={!bridgeReady || updateState.phase === 'checking'}
          >
            {updateState.phase === 'checking' ? 'CHECKING…' : 'CHECK FOR UPDATES'}
          </MrButton>
          {updateState.phase === 'current' && (
            <span className="about-update-msg ok">
              ✓ Up to date · latest is v{updateState.latest}
            </span>
          )}
          {updateState.phase === 'newer' && (
            <span className="about-update-msg new">
              ◆ New version v{updateState.latest} available
              {updateState.url && (
                <> — <a href={updateState.url} target="_blank" rel="noopener noreferrer">download</a></>
              )}
            </span>
          )}
          {updateState.phase === 'error' && (
            <span className="about-update-msg err">⚠ {updateState.message}</span>
          )}
        </div>
      </Panel>
    </div>
  );
}

Object.assign(window, { RegionPanel, SettingsPanel, CodexPanel, IndexPanel, AboutPanel });
