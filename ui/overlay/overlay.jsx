// Standalone overlay window — tier-aware match card + placement chrome
// Receives data from Python via window.onOverlayDetection / window.onPlacementMode.

const { useState, useEffect } = React;

const TIERS = {
  legendary: { label: "LEGENDARY", color: "#ffd86b" },
  epic:      { label: "EPIC",      color: "#c08bff" },
  rare:      { label: "RARE",      color: "#5fa8ff" },
  uncommon:  { label: "UNCOMMON",  color: "#3effa1" },
  common:    { label: "COMMON",    color: "#9aa3ad" },
  ground_s:  { label: "GROUND·FPS", color: "#ff9d2a" },
  ground_l:  { label: "GROUND·ROC", color: "#ff9d2a" },
  salvage:   { label: "SALVAGE",   color: "#ff6b3a" },
  unknown:   { label: "UNKNOWN",   color: "#ff3b30" },
};

function OverlayCard({ payload, draggable, durationSec }) {
  if (!payload) return null;
  const m = payload.match || {};
  const t = TIERS[m.tier] || TIERS.unknown;
  const cls = "ovc" + (draggable ? " pywebview-drag-region" : "");
  const mineralName = m.nameMain || m.name || "NO LOCK";
  const tierSub = m.nameSubtitle || "";
  return (
    <div className={cls} style={{ "--tier": t.color }}>
      <span className="ovc-corner tl" />
      <span className="ovc-corner tr" />
      <span className="ovc-corner bl" />
      <span className="ovc-corner br" />
      <div className="ovc-head">
        <span>SIG-{payload.sig != null ? payload.sig : "----"}</span>
        <span className="ovc-tier">{t.label}</span>
      </div>
      <div className="ovc-name">{mineralName}</div>
      {tierSub && <div className="ovc-name-sub">{tierSub}</div>}
      <div className="ovc-sig-readout">
        <span className="ovc-sig-label">CROSS-SECTION</span>
        <span className="ovc-sig-val">
          {payload.sig != null ? payload.sig.toLocaleString() : "—"}
        </span>
      </div>
      <div className="ovc-meta">
        <span>{(m.cat || "—").toUpperCase()}</span>
        <span className="ovc-dot" />
        <span>{(m.notes || "").split("—")[0]}</span>
      </div>
      <div className="ovc-progress">
        <div
          className="ovc-progress-fill"
          style={durationSec ? { animationDuration: `${durationSec}s` } : undefined}
        />
      </div>
    </div>
  );
}

function PlacementToolbar({ onSave, onCancel }) {
  return (
    <div className="placement-toolbar">
      <div className="pt-hint">DRAG CARD · CLICK SAVE WHEN PLACED</div>
      <div className="pt-buttons">
        <button className="pt-btn pt-save" onClick={onSave}>✓ SAVE</button>
        <button className="pt-btn pt-cancel" onClick={onCancel}>✗ CANCEL</button>
      </div>
    </div>
  );
}

const SAMPLE_PAYLOAD = {
  sig: 3585,
  match: {
    tier: "rare",
    name: "Gold (Rare)",
    nameMain: "Gold",
    nameSubtitle: "(Rare)",
    cat: "ship",
    notes: "Mid-tier · sig 3585",
  },
};

function OverlayApp() {
  const [payload, setPayload] = useState(null);
  const [placing, setPlacing] = useState(false);
  // Bumping `instance` on each new push forces OverlayCard to unmount and
  // remount, which restarts the progress-bar CSS animation.
  const [instance, setInstance] = useState(0);

  useEffect(() => {
    window.onOverlayDetection = (p) => {
      setPlacing(false);
      setPayload(p);
      setInstance((n) => n + 1);
    };
    window.onPlacementMode = (data) => {
      const active = !!(data && (data === true || data.active));
      const scale = (data && data.scale) || 1;
      setPlacing(active);
      setPayload(active ? { ...SAMPLE_PAYLOAD, scale } : null);
      setInstance((n) => n + 1);
    };
    return () => {
      delete window.onOverlayDetection;
      delete window.onPlacementMode;
    };
  }, []);

  // JS-driven auto-hide. Triggered on every new detection payload (not in
  // placement mode). Replaces the previous Python threading.Timer approach,
  // which was unreliable because Window.hide() doesn't always dispatch
  // cleanly from a non-main thread on WebView2.
  useEffect(() => {
    if (!payload || placing) return;
    const dur = payload.duration;
    if (!dur || dur <= 0) return;
    const id = setTimeout(() => {
      setPayload(null);
      if (window.pywebview && window.pywebview.api && window.pywebview.api.hide_overlay) {
        window.pywebview.api.hide_overlay()
          .catch((err) => console.error("hide_overlay failed", err));
      }
    }, dur * 1000);
    return () => clearTimeout(id);
  }, [payload, placing, instance]);

  const confirmPlacement = () => {
    if (window.pywebview && window.pywebview.api) {
      window.pywebview.api.confirm_overlay_position()
        .catch((err) => console.error("confirm_overlay_position failed", err));
    }
  };

  const cancelPlacement = () => {
    if (window.pywebview && window.pywebview.api) {
      window.pywebview.api.cancel_overlay_placement()
        .catch((err) => console.error("cancel_overlay_placement failed", err));
    }
  };

  if (!payload && !placing) return null;

  // CSS `zoom` scales all descendants — fonts, spacing, borders, animations
  // — and is honored by Chromium-based engines (WebView2). Combined with
  // the bridge resizing the window to base × scale, the card visually
  // grows/shrinks together with its window.
  // Detection mode: card fills the whole window (no body visible).
  // Placement mode: card content-sized + toolbar below (body color shows
  // in any gap, but matches card edges so it stays invisible).
  const scale = (payload && payload.scale) || 1;
  const rootCls = "overlay-root " + (placing ? "placing" : "detection");
  return (
    <div className={rootCls} style={{ zoom: scale }}>
      <OverlayCard
        key={instance}
        payload={payload}
        draggable={placing}
        durationSec={!placing && payload ? payload.duration : null}
      />
      {placing && (
        <PlacementToolbar onSave={confirmPlacement} onCancel={cancelPlacement} />
      )}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<OverlayApp />);
