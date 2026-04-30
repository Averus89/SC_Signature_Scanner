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

function OverlayCard({ payload, draggable }) {
  if (!payload) return null;
  const m = payload.match || {};
  const t = TIERS[m.tier] || TIERS.unknown;
  const cls = "ovc" + (draggable ? " pywebview-drag-region" : "");
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
      <div className="ovc-name">{m.name || "NO LOCK"}</div>
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
      <div className="ovc-progress"><div className="ovc-progress-fill" /></div>
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
    name: "Gold + Borase + Bexalite",
    cat: "ship",
    notes: "Mid-tier · sig 3585",
  },
};

function OverlayApp() {
  const [payload, setPayload] = useState(null);
  const [placing, setPlacing] = useState(false);

  useEffect(() => {
    window.onOverlayDetection = (p) => {
      setPlacing(false);
      setPayload(p);
    };
    window.onPlacementMode = (active) => {
      setPlacing(!!active);
      setPayload(active ? SAMPLE_PAYLOAD : null);
    };
    return () => {
      delete window.onOverlayDetection;
      delete window.onPlacementMode;
    };
  }, []);

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

  return (
    <div className="overlay-root">
      <OverlayCard payload={payload} draggable={placing} />
      {placing && (
        <PlacementToolbar onSave={confirmPlacement} onCancel={cancelPlacement} />
      )}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<OverlayApp />);
