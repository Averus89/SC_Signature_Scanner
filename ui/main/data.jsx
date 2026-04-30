// UI metadata + signature lookup helper.
// The actual signature tables (minerals/ground/salvage) are NOT defined here —
// they're fetched from the Python bridge on bootstrap (see app.jsx) and
// hydrated into window.MINERALS / GROUND / SALVAGE / ALL_SIGNATURES.
// This file only owns presentational tier metadata and the lookup function
// that operates on whatever's in window.ALL_SIGNATURES at call time.

const TIERS = {
  legendary: { label: 'LEGENDARY', color: '#ffd86b', accent: '#fff3c4', range: '3170–3200' },
  epic:      { label: 'EPIC',      color: '#c08bff', accent: '#e8d4ff', range: '3370–3400' },
  rare:      { label: 'RARE',      color: '#5fa8ff', accent: '#bcdcff', range: '3540–3600' },
  uncommon:  { label: 'UNCOMMON',  color: '#3effa1', accent: '#bdffd8', range: '3825–3900' },
  common:    { label: 'COMMON',    color: '#9aa3ad', accent: '#d6dde4', range: '4180–4300' },
  ground_s:  { label: 'GROUND·FPS',color: '#ff9d2a', accent: '#ffd5a3', range: '3000' },
  ground_l:  { label: 'GROUND·ROC',color: '#ff9d2a', accent: '#ffd5a3', range: '4000' },
  salvage:   { label: 'SALVAGE',   color: '#ff6b3a', accent: '#ffc7b3', range: '1700–3000' },
  unknown:   { label: 'UNKNOWN',   color: '#ff3b30', accent: '#ffb3ae', range: '—' },
};

// Best-effort fallback lookup against the hydrated codex. Python's
// scanner.match_signature is the source of truth on every detection (it
// understands count multiples, salvage panels, debris bases). This is only
// used when no Python matches arrived for a given signature.
function lookupSignature(sig) {
  const all = (typeof window !== 'undefined' && window.ALL_SIGNATURES) || [];
  if (!all.length) return null;

  const tol = 8;
  let best = null;
  let bestDist = Infinity;
  for (const e of all) {
    const d = Math.abs(e.sig - sig);
    if (d < bestDist && d <= tol) {
      best = e;
      bestDist = d;
    }
  }
  if (!best) return null;
  const collisions = all.filter(x => Math.abs(x.sig - best.sig) <= tol && x !== best);
  return { match: best, collisions };
}

// Initialize the codex globals to empty arrays so consumers that read them
// synchronously at render time (e.g. SignatureSpectrum, IndexPanel,
// CodexPanel) don't crash before bootstrap hydrates them.
Object.assign(window, {
  TIERS,
  lookupSignature,
  MINERALS: window.MINERALS || [],
  GROUND: window.GROUND || [],
  SALVAGE: window.SALVAGE || [],
  ALL_SIGNATURES: window.ALL_SIGNATURES || [],
});
