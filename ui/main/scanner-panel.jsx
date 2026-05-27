// Scanner module — folder monitoring + detection log + reveal animation
const { useState, useEffect, useRef } = React;

function ScannerPanel({
  detections, monitoring, toggleMonitoring, simulateDetection,
  screenshotFolder, setScreenshotFolder, browseFolder, bridgeReady, latest,
  scanMode = 'folder', setScanMode = () => {}, liveStatus = {},
  liveRegionConfigured = false,
}) {
  const [scrolling, setScrolling] = useState(true);
  const logRef = useRef(null);
  useEffect(() => {
    if (scrolling && logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [detections, scrolling]);

  return (
    <div className="scanner-grid">
      <div className="scanner-left">
        <Panel title="TARGET PROFILE" code="TGT-01" accent="var(--amber)" status={latest ? <LED state={latest.match ? 'green' : 'red'} label={latest.match ? 'LOCK' : 'NO LOCK'} /> : <LED state="amber" label="STANDBY" />}>
          <RevealCard latest={latest} />
        </Panel>
      </div>

      <div className="scanner-right">
        <Panel title="MONITOR CONTROL" code="MON-02" accent="var(--amber)">
          <div className="mon-mode-toggle" style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
            <MrButton
              small
              primary={scanMode === 'folder'}
              onClick={() => setScanMode('folder')}
              disabled={!bridgeReady}
            >FOLDER</MrButton>
            <MrButton
              small
              primary={scanMode === 'live'}
              onClick={() => setScanMode('live')}
              disabled={!bridgeReady}
            >LIVE</MrButton>
          </div>
          {scanMode === 'folder' && (
            <div className="mon-folder">
              <div className="mon-label">SCREENSHOT FOLDER</div>
              <div className="mon-folder-row">
                <input className="mr-input" value={screenshotFolder} onChange={e => setScreenshotFolder(e.target.value)} />
                <MrButton small icon="▸" onClick={browseFolder} disabled={!bridgeReady}>BROWSE</MrButton>
              </div>
            </div>
          )}
          {scanMode === 'live' && (
            <div className="mon-live-status" style={{ marginBottom: 12 }}>
              <Readout
                label="STAR CITIZEN"
                value={liveStatus.scStatus === 'running' ? 'DETECTED' :
                       liveStatus.scStatus === 'minimized' ? 'MINIMIZED' : 'NOT RUNNING'}
                accent={liveStatus.scStatus === 'running' ? 'var(--green)' :
                        liveStatus.scStatus === 'minimized' ? 'var(--amber)' : 'var(--red)'}
                glow
              />
              <Readout
                label="LIVE REGION"
                value={liveRegionConfigured ? 'CALIBRATED' : 'NOT SET'}
                accent={liveRegionConfigured ? 'var(--green)' : 'var(--red)'}
                glow
              />
            </div>
          )}
          <div className="mon-state">
            <div className={`mon-status ${monitoring ? 'on' : 'off'}`}>
              <div className="mon-pulse"><span /><span /><span /></div>
              <div>
                <div className="mon-status-label">
                  {!monitoring ? 'STANDBY' :
                   scanMode === 'live' ? (
                     liveStatus.captureStatus === 'running' ? 'LIVE · 30 Hz' :
                     liveStatus.captureStatus === 'waiting' ? 'WAITING FOR SC' :
                     liveStatus.captureStatus === 'idle_minimized' ? 'IDLE (MINIMIZED)' :
                     liveStatus.captureStatus === 'error' ? 'ERROR' :
                     'STARTING'
                   ) : 'MONITORING'}
                </div>
                <div className="mon-status-sub">{detections.length} signatures processed</div>
              </div>
            </div>
            <div className="mon-actions">
              <MrButton primary={!monitoring} danger={monitoring} onClick={toggleMonitoring} disabled={!bridgeReady} icon={monitoring ? '■' : '▶'}>
                {monitoring ? 'HALT' : 'ENGAGE'}
              </MrButton>
              <MrButton onClick={simulateDetection} disabled={!bridgeReady} icon="◉">PING</MrButton>
            </div>
          </div>
        </Panel>

        <Panel title="DETECTION LOG" code="LOG-03" accent="var(--amber)" status={<span className="log-count">{detections.length} ENTRIES</span>}>
          <div className="log-stream" ref={logRef}>
            {detections.length === 0 && <div className="log-empty">— Awaiting signal —</div>}
            {detections.map((d, i) => <LogEntry key={d.id} entry={d} idx={i} />)}
          </div>
        </Panel>
      </div>
    </div>
  );
}

function LogEntry({ entry }) {
  const m = entry.match;
  const t = window.TIERS[m?.tier] || window.TIERS.unknown;
  const type = m?.cat ? m.cat.toUpperCase() : '—';
  const count = m?.count && m.count > 1 ? `×${m.count}` : '×1';
  const classification = m?.nameOnly || m?.name || '— NO LOCK —';
  return (
    <div className={`log-entry ${m ? 'hit' : 'miss'}`} style={{ '--tier': t.color }}>
      <div className="log-time">{entry.time}</div>
      <div className="log-type">{type}</div>
      <div className="log-qty" style={{ color: t.color }}>{m ? count : ''}</div>
      <div className="log-class" style={{ color: m ? '#fff' : 'var(--red)' }}>{classification}</div>
      <div className="log-sig">{entry.sig.toLocaleString()}</div>
    </div>
  );
}

// The reveal card — slams in with parallax + scan sweep when latest changes
function RevealCard({ latest, tweak }) {
  const [revealKey, setRevealKey] = useState(0);
  useEffect(() => {
    if (latest) setRevealKey(k => k + 1);
  }, [latest?.id]);

  if (!latest) {
    return (
      <div className="reveal-empty">
        <div className="reveal-placeholder">
          <Stencil size="lg">AWAITING SIGNAL</Stencil>
          <div className="reveal-sub">No signature read since session start. Press <b>ENGAGE</b> or <b>PING</b> to test.</div>
        </div>
      </div>
    );
  }

  const m = latest.match;
  const t = window.TIERS[m?.tier] || window.TIERS.unknown;

  return (
    <div className={`reveal-card ${m ? 'has-match' : 'no-match'}`} key={revealKey} style={{ '--tier': t.color, '--tier-soft': t.accent }}>
      <div className="reveal-bg-pulse" />
      <div className="reveal-scan-sweep" />
      <div className="reveal-grid">
        <div className="reveal-holo">
          <HoloRock tier={m?.tier || 'unknown'} sig={latest.sig} name={m?.name || '?'} />
        </div>
        <div className="reveal-info">
          <div className="reveal-tier-row">
            <span className="reveal-tier-chip" style={{ background: t.color }}>{t.label}</span>
            <span className="reveal-cat">{m?.cat?.toUpperCase() || 'UNKNOWN'} · MINING</span>
          </div>
          <div className="reveal-name">
            {m
              ? <>
                  <span>{m.nameMain || m.name}</span>
                  {m.nameSubtitle && <span className="reveal-name-sub">{m.nameSubtitle}</span>}
                </>
              : 'NO LOCK'}
          </div>
          <div className="reveal-sig-block">
            <div className="reveal-sig-label">SIGNATURE READ</div>
            <div className="reveal-sig-value">{latest.sig.toLocaleString()}</div>
          </div>
          <div className="reveal-meta">
            <Readout label="EXPECTED" value={m ? m.sig.toLocaleString() : '—'} accent={t.color} />
            <Readout
              label="CONF"
              value={latest.ocrConfidence != null ? `${Math.round(latest.ocrConfidence * 100)}%` : '—'}
              accent={t.color}
            />
            <Readout label="CAT" value={m?.cat?.toUpperCase() || '—'} accent={t.color} />
          </div>
          {m && <div className="reveal-notes">{m.notes}</div>}
          {latest.collisions && latest.collisions.length > 0 && (
            <div className="reveal-collisions">
              <span className="collision-label">⚠ COLLISION:</span>
              {latest.collisions.map(c => <span key={c.name} className="collision-chip">{c.name}</span>)}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Signature index — grouped by tier, sorted by signature value within each group
function SignatureIndex({ activeSig }) {
  const TIER_ORDER = ['legendary', 'epic', 'rare', 'uncommon', 'common', 'ground_s', 'ground_l', 'salvage'];
  const tiers = window.TIERS;
  const groups = TIER_ORDER.map(k => ({
    key: k,
    tier: tiers[k],
    entries: window.ALL_SIGNATURES.filter(e => e.tier === k).sort((a, b) => a.sig - b.sig),
  })).filter(g => g.entries.length);

  return (
    <div className="sig-index">
      {groups.map(g => (
        <section key={g.key} className="sig-group" style={{ '--tier': g.tier.color }}>
          <header className="sig-group-header">
            <div className="sig-group-meta">
              <span className="sig-group-label">{g.tier.label}</span>
              <span className="sig-group-range">{g.tier.range}</span>
            </div>
            <span className="sig-group-count">{g.entries.length} ENTRIES</span>
          </header>
          <div className="sig-group-rows">
            {g.entries.map(e => {
              const active = activeSig != null && Math.abs(e.sig - activeSig) <= 8;
              return (
                <div key={e.sig + e.name} className={`sig-row ${active ? 'active' : ''}`}>
                  <span className="sig-row-sig">{e.sig.toLocaleString()}</span>
                  <span className="sig-row-name">{e.name}</span>
                  <span className="sig-row-notes" title={e.notes}>{e.notes}</span>
                </div>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}

Object.assign(window, { ScannerPanel, LogEntry, RevealCard, SignatureIndex });
