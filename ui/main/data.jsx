// Mining signature data — extracted from the SC_Signature_Scanner project
// SC 4.7 per-mineral system

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

const MINERALS = [
  // Legendary
  { sig: 3170, name: 'Quantainium', tier: 'legendary', cat: 'ship',  notes: '+ Beryl 10–20%' },
  { sig: 3185, name: 'Stileron',    tier: 'legendary', cat: 'ship',  notes: '+ Taranite 10–20%' },
  { sig: 3200, name: 'Savrilium',   tier: 'legendary', cat: 'ship',  notes: '+ Gold 10–20%' },
  // Epic
  { sig: 3370, name: 'Ouratite',    tier: 'epic', cat: 'ship', notes: '+ Agricium 10–20%' },
  { sig: 3385, name: 'Riccite',     tier: 'epic', cat: 'ship', notes: '+ Laranite 10–20%' },
  { sig: 3400, name: 'Lindinium',   tier: 'epic', cat: 'ship', notes: '+ Tungsten 10–20%' },
  // Rare
  { sig: 3540, name: 'Beryl',       tier: 'rare', cat: 'ship', notes: 'pure 50–100%' },
  { sig: 3555, name: 'Taranite',    tier: 'rare', cat: 'ship', notes: 'pure 50–100%' },
  { sig: 3570, name: 'Borase',      tier: 'rare', cat: 'ship', notes: '+ Gold + Bexalite' },
  { sig: 3585, name: 'Gold',        tier: 'rare', cat: 'ship', notes: '+ Borase + Bexalite' },
  { sig: 3600, name: 'Bexalite',    tier: 'rare', cat: 'ship', notes: '+ Gold + Borase' },
  // Uncommon
  { sig: 3825, name: 'Laranite',    tier: 'uncommon', cat: 'ship', notes: '+ Tungsten 10–20%' },
  { sig: 3840, name: 'Aslarite',    tier: 'uncommon', cat: 'ship', notes: '+ Titanium + Agricium' },
  { sig: 3855, name: 'Titanium',    tier: 'uncommon', cat: 'ship', notes: '+ Aslarite + Agricium' },
  { sig: 3870, name: 'Tungsten',    tier: 'uncommon', cat: 'ship', notes: '+ Laranite 10–20%' },
  { sig: 3885, name: 'Agricium',    tier: 'uncommon', cat: 'ship', notes: '+ Titanium + Aslarite' },
  { sig: 3900, name: 'Torite',      tier: 'uncommon', cat: 'ship', notes: 'pure 50–100%' },
  // Common
  { sig: 4180, name: 'Hephaestanite',tier: 'common', cat: 'ship', notes: '+ Quartz + Silicon' },
  { sig: 4195, name: 'Tin',         tier: 'common', cat: 'ship', notes: '+ Copper 10–20%' },
  { sig: 4210, name: 'Quartz',      tier: 'common', cat: 'ship', notes: '+ Hephaestanite + Silicon' },
  { sig: 4225, name: 'Corundum',    tier: 'common', cat: 'ship', notes: '+ Aluminium 10–20%' },
  { sig: 4240, name: 'Copper',      tier: 'common', cat: 'ship', notes: '+ Tin 10–20%' },
  { sig: 4255, name: 'Silicon',     tier: 'common', cat: 'ship', notes: '+ Hephaestanite + Quartz' },
  { sig: 4270, name: 'Iron',        tier: 'common', cat: 'ship', notes: 'pure 50–100%' },
  { sig: 4285, name: 'Aluminum',    tier: 'common', cat: 'ship', notes: '+ Corundum 10–20%' },
  { sig: 4300, name: 'Ice',         tier: 'common', cat: 'ship', notes: 'pure 50–100%' },
];

const GROUND = [
  { sig: 3000, name: 'Small Ground Deposit', tier: 'ground_s', cat: 'ground', notes: 'FPS / Hand mining — single mineral, 100% pure' },
  { sig: 4000, name: 'Large Ground Deposit', tier: 'ground_l', cat: 'ground', notes: 'ROC / Vehicle — single mineral, 100% pure' },
];

const SALVAGE = [
  { sig: 1700, name: 'Small Debris',   tier: 'salvage', cat: 'salvage', notes: 'Avenger-class wreck' },
  { sig: 1850, name: 'Medium Debris',  tier: 'salvage', cat: 'salvage', notes: 'Ares Inferno-class wreck' },
  { sig: 2000, name: 'Hull Panel',     tier: 'salvage', cat: 'salvage', notes: '2000 × N panels — active scrap' },
  { sig: 2400, name: 'Large Debris',   tier: 'salvage', cat: 'salvage', notes: 'C2 Hercules-class wreck' },
  { sig: 3000, name: 'Capital Debris', tier: 'salvage', cat: 'salvage', notes: '890 Jump-class — collides w/ FPS ground' },
];

const ALL_SIGNATURES = [...MINERALS, ...GROUND, ...SALVAGE].sort((a,b) => a.sig - b.sig);

// Sample fictional detection stream — used by the demo monitor
const SAMPLE_STREAM = [
  { sig: 3200, file: 'ScreenShot-2026-04-29_14-22-08-A4F.jpg' },
  { sig: 3900, file: 'ScreenShot-2026-04-29_14-23-41-9C2.jpg' },
  { sig: 4270, file: 'ScreenShot-2026-04-29_14-25-19-DD0.jpg' },
  { sig: 3585, file: 'ScreenShot-2026-04-29_14-26-55-12B.jpg' },
  { sig: 4000, file: 'ScreenShot-2026-04-29_14-28-10-7E1.jpg' },
  { sig: 3170, file: 'ScreenShot-2026-04-29_14-30-02-8AA.jpg' },
  { sig: 2400, file: 'ScreenShot-2026-04-29_14-31-44-3F6.jpg' },
  { sig: 3855, file: 'ScreenShot-2026-04-29_14-33-26-B17.jpg' },
  { sig: 4225, file: 'ScreenShot-2026-04-29_14-35-09-D9D.jpg' },
  { sig: 3370, file: 'ScreenShot-2026-04-29_14-37-22-4E0.jpg' },
];

// Tolerance window for OCR signature matching
function lookupSignature(sig, contextHint /* 'space' | 'ground' | 'salvage' | null */) {
  const tol = 8;
  let best = null;
  let bestDist = Infinity;
  for (const e of ALL_SIGNATURES) {
    const d = Math.abs(e.sig - sig);
    if (d < bestDist && d <= tol) {
      best = e;
      bestDist = d;
    }
  }
  if (!best) return null;
  // Resolve known collisions
  const collisions = ALL_SIGNATURES.filter(x => Math.abs(x.sig - best.sig) <= tol && x !== best);
  return { match: best, collisions };
}

Object.assign(window, { TIERS, MINERALS, GROUND, SALVAGE, ALL_SIGNATURES, SAMPLE_STREAM, lookupSignature });
