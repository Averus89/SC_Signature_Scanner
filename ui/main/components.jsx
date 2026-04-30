// Industrial mining-rig UI primitives
// Chamfered panels, riveted edges, stenciled labels, parallax glass

const { useState, useEffect, useRef, useMemo, useCallback } = React;

// ============ PARALLAX HOOK ============
function useParallax(strength = 8) {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const onMove = (e) => {
      const r = el.getBoundingClientRect();
      const cx = r.left + r.width / 2;
      const cy = r.top + r.height / 2;
      const dx = (e.clientX - cx) / r.width;
      const dy = (e.clientY - cy) / r.height;
      const s = (window.__parallaxStrength ?? 1) * strength;
      el.style.setProperty('--px', `${(-dx * s).toFixed(2)}deg`);
      el.style.setProperty('--py', `${(dy * s).toFixed(2)}deg`);
    };
    const onLeave = () => {
      el.style.setProperty('--px', '0deg');
      el.style.setProperty('--py', '0deg');
    };
    window.addEventListener('mousemove', onMove);
    el.addEventListener('mouseleave', onLeave);
    return () => {
      window.removeEventListener('mousemove', onMove);
      el.removeEventListener('mouseleave', onLeave);
    };
  }, [strength]);
  return ref;
}

// ============ CHAMFERED PANEL ============
// SVG path for a chamfered (notched-corner) rectangle
function chamferPath(w, h, c = 14) {
  return `M${c} 0 H${w-c} L${w} ${c} V${h-c} L${w-c} ${h} H${c} L0 ${h-c} V${c} Z`;
}

function Panel({ children, title, code, status, accent, className = '', style = {}, parallax = false, dense = false }) {
  const ref = useParallax(parallax ? 5 : 0);
  return (
    <div ref={ref} className={`mr-panel ${className}`} style={{ ...style, '--accent': accent || 'var(--amber)' }}>
      <div className="mr-panel-frame">
        <div className="mr-panel-bg" />
        <div className="mr-panel-grain" />
        <div className="mr-panel-corners">
          <span className="mr-corner tl" /><span className="mr-corner tr" />
          <span className="mr-corner bl" /><span className="mr-corner br" />
        </div>
        {title && (
          <div className="mr-panel-header">
            <div className="mr-panel-title">
              {code && <span className="mr-panel-code">{code}</span>}
              <span className="mr-panel-name">{title}</span>
            </div>
            {status && <div className="mr-panel-status">{status}</div>}
          </div>
        )}
        <div className={`mr-panel-body ${dense ? 'dense' : ''}`}>{children}</div>
      </div>
    </div>
  );
}

// ============ RIVETED BAR — top status strip ============
function RivetBar({ children, className = '' }) {
  return (
    <div className={`mr-rivet-bar ${className}`}>
      <div className="mr-rivets-left">
        {Array.from({ length: 4 }).map((_, i) => <span key={i} className="mr-rivet" />)}
      </div>
      <div className="mr-rivet-content">{children}</div>
      <div className="mr-rivets-right">
        {Array.from({ length: 4 }).map((_, i) => <span key={i} className="mr-rivet" />)}
      </div>
    </div>
  );
}

// ============ STAT READOUT ============
function Readout({ label, value, unit, accent, glow }) {
  return (
    <div className="mr-readout" style={{ '--accent': accent || 'var(--amber)' }}>
      <div className="mr-readout-label">{label}</div>
      <div className={`mr-readout-value ${glow ? 'glow' : ''}`}>
        {value}
        {unit && <span className="mr-readout-unit">{unit}</span>}
      </div>
    </div>
  );
}

// ============ TOGGLE / BUTTON ============
function MrButton({ children, onClick, primary, danger, active, disabled, icon, small }) {
  const cls = [
    'mr-btn',
    primary && 'primary',
    danger && 'danger',
    active && 'active',
    small && 'small',
    disabled && 'disabled',
  ].filter(Boolean).join(' ');
  return (
    <button className={cls} onClick={disabled ? undefined : onClick} disabled={disabled}>
      <span className="mr-btn-bg" />
      <span className="mr-btn-content">
        {icon && <span className="mr-btn-icon">{icon}</span>}
        <span>{children}</span>
      </span>
    </button>
  );
}

// ============ LED INDICATOR ============
function LED({ state = 'off', label, blink }) {
  return (
    <div className={`mr-led-row state-${state} ${blink ? 'blink' : ''}`}>
      <span className="mr-led" />
      {label && <span className="mr-led-label">{label}</span>}
    </div>
  );
}

// ============ SIGNATURE SPECTRUM (the 3D waveform) ============
// Renders the entire signature range as a horizontal "tape" with bars
// at each known signature. Active sig gets a 3D-extruded bar that pops.
function SignatureSpectrum({ activeSig, height = 180, onPick }) {
  const min = 1500, max = 4500;
  const allEntries = window.ALL_SIGNATURES;
  const tiers = window.TIERS;

  return (
    <div className="mr-spectrum" style={{ height }}>
      <div className="mr-spectrum-stage">
        <div className="mr-spectrum-grid" />
        <div className="mr-spectrum-deck">
          {allEntries.map((e, i) => {
            const x = ((e.sig - min) / (max - min)) * 100;
            const isActive = activeSig != null && Math.abs(e.sig - activeSig) <= 8;
            const t = tiers[e.tier];
            return (
              <div
                key={e.sig + e.name}
                className={`mr-spec-bar ${isActive ? 'active' : ''}`}
                style={{
                  left: `${x}%`,
                  '--bar-color': t.color,
                }}
                onClick={() => onPick && onPick(e)}
                title={`${e.name} · ${e.sig}`}
              >
                <span className="mr-spec-shaft" />
                <span className="mr-spec-cap" />
                {isActive && <span className="mr-spec-pulse" />}
              </div>
            );
          })}
          {/* Tier zone backgrounds */}
          {[
            ['legendary', 3160, 3210],
            ['epic',      3360, 3410],
            ['rare',      3530, 3610],
            ['uncommon',  3815, 3910],
            ['common',    4170, 4310],
          ].map(([k, lo, hi]) => {
            const x1 = ((lo - min) / (max - min)) * 100;
            const x2 = ((hi - min) / (max - min)) * 100;
            return (
              <div key={k} className={`mr-spec-zone zone-${k}`}
                   style={{ left: `${x1}%`, width: `${x2 - x1}%`, '--zone-color': tiers[k].color }} />
            );
          })}
        </div>
        {/* axis ticks */}
        <div className="mr-spectrum-axis">
          {[1500, 2000, 2500, 3000, 3500, 4000, 4500].map(v => {
            const x = ((v - min) / (max - min)) * 100;
            return <div key={v} className="mr-spec-tick" style={{ left: `${x}%` }}><span>{v}</span></div>;
          })}
        </div>
        {/* active marker / scan line */}
        {activeSig != null && (
          <div className="mr-spec-marker" style={{ left: `${((activeSig - min) / (max - min)) * 100}%` }}>
            <div className="mr-spec-marker-line" />
            <div className="mr-spec-marker-tag">{activeSig.toLocaleString()}</div>
          </div>
        )}
      </div>
    </div>
  );
}

// ============ STENCIL TEXT ============
function Stencil({ children, size = 'md', color }) {
  return <span className={`mr-stencil mr-stencil-${size}`} style={{ color }}>{children}</span>;
}

// ============ HOLO TARGET (3D rock for minerals, wreck for salvage) ============
// Seeded RNG so each signature gets a unique-but-stable shape
function mulberry32(seed) {
  return function() {
    let t = seed += 0x6D2B79F5;
    t = Math.imul(t ^ t >>> 15, t | 1);
    t ^= t + Math.imul(t ^ t >>> 7, t | 61);
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}
function hashStr(s) {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
  return h >>> 0;
}

// Per-mineral DNA: each mineral has its own shape personality.
// shape: 'crystal' = prismatic / faceted, 'lumpy' = potato-rock, 'shard' = jagged spike,
//        'cluster' = multi-lobe, 'cubic' = blocky, 'flake' = flat slab.
// stretch: aspect ratio bias (1 = round, >1 = elongated vertical)
// lumpiness: 0..1 noise intensity
// lat/lon: tessellation density (more = smoother, less = chunkier)
// twist: rotational shear per latitude band (rad)
// crystals: optional accent specks count
const MINERAL_DNA = {
  // Legendary — exotic rare crystalline forms
  Quantainium: { shape: 'crystal', stretch: 1.6, lumpiness: 0.18, lat: 8, lon: 8, twist: 0.0, crystals: 8 },
  Stileron:    { shape: 'shard',   stretch: 1.9, lumpiness: 0.15, lat: 6, lon: 6, twist: 0.4, crystals: 6 },
  Savrilium:   { shape: 'cluster', stretch: 1.0, lumpiness: 0.5,  lat: 7, lon: 10, twist: 0.0, crystals: 10 },
  // Epic
  Ouratite:    { shape: 'cubic',   stretch: 0.85, lumpiness: 0.3, lat: 5, lon: 6, twist: 0.0, crystals: 4 },
  Riccite:     { shape: 'crystal', stretch: 1.3, lumpiness: 0.22, lat: 7, lon: 7, twist: 0.0, crystals: 5 },
  Lindinium:   { shape: 'flake',   stretch: 0.55, lumpiness: 0.4, lat: 5, lon: 9, twist: 0.0, crystals: 3 },
  // Rare
  Beryl:       { shape: 'crystal', stretch: 1.7, lumpiness: 0.12, lat: 8, lon: 6, twist: 0.0, crystals: 6 },
  Taranite:    { shape: 'shard',   stretch: 1.5, lumpiness: 0.2,  lat: 6, lon: 7, twist: 0.3, crystals: 4 },
  Borase:      { shape: 'lumpy',   stretch: 1.0, lumpiness: 0.6,  lat: 7, lon: 9, twist: 0.0, crystals: 0 },
  Gold:        { shape: 'lumpy',   stretch: 0.95, lumpiness: 0.7, lat: 7, lon: 11, twist: 0.0, crystals: 0 },
  Bexalite:    { shape: 'cluster', stretch: 1.1, lumpiness: 0.55, lat: 8, lon: 9, twist: 0.0, crystals: 7 },
  // Uncommon
  Laranite:    { shape: 'crystal', stretch: 1.4, lumpiness: 0.25, lat: 7, lon: 6, twist: 0.0, crystals: 4 },
  Aslarite:    { shape: 'lumpy',   stretch: 1.1, lumpiness: 0.55, lat: 7, lon: 9, twist: 0.0, crystals: 0 },
  Titanium:    { shape: 'cubic',   stretch: 1.0, lumpiness: 0.3,  lat: 5, lon: 5, twist: 0.0, crystals: 2 },
  Tungsten:    { shape: 'lumpy',   stretch: 1.0, lumpiness: 0.45, lat: 6, lon: 8, twist: 0.0, crystals: 0 },
  Agricium:    { shape: 'crystal', stretch: 1.25, lumpiness: 0.2, lat: 7, lon: 7, twist: 0.0, crystals: 3 },
  Torite:      { shape: 'lumpy',   stretch: 1.0, lumpiness: 0.5,  lat: 7, lon: 10, twist: 0.0, crystals: 0 },
  // Common — plain potato rocks with mild variation
  Hephaestanite: { shape: 'lumpy',   stretch: 1.0, lumpiness: 0.4, lat: 7, lon: 9, twist: 0.0, crystals: 0 },
  Tin:         { shape: 'lumpy',   stretch: 0.9, lumpiness: 0.45, lat: 6, lon: 8, twist: 0.0, crystals: 0 },
  Quartz:      { shape: 'crystal', stretch: 1.5, lumpiness: 0.15, lat: 7, lon: 6, twist: 0.0, crystals: 5 },
  Corundum:    { shape: 'crystal', stretch: 1.3, lumpiness: 0.2,  lat: 6, lon: 6, twist: 0.0, crystals: 4 },
  Copper:      { shape: 'lumpy',   stretch: 1.0, lumpiness: 0.5,  lat: 6, lon: 9, twist: 0.0, crystals: 0 },
  Silicon:     { shape: 'flake',   stretch: 0.6, lumpiness: 0.3,  lat: 5, lon: 8, twist: 0.0, crystals: 2 },
  Iron:        { shape: 'lumpy',   stretch: 1.0, lumpiness: 0.4,  lat: 7, lon: 9, twist: 0.0, crystals: 0 },
  Aluminum:    { shape: 'lumpy',   stretch: 0.95, lumpiness: 0.4, lat: 6, lon: 8, twist: 0.0, crystals: 0 },
  Ice:         { shape: 'crystal', stretch: 1.2, lumpiness: 0.1,  lat: 8, lon: 7, twist: 0.0, crystals: 6 },
  // Ground deposits — chunky terrain
  'Small Ground Deposit': { shape: 'flake', stretch: 0.45, lumpiness: 0.55, lat: 5, lon: 12, twist: 0.0, crystals: 0 },
  'Large Ground Deposit': { shape: 'flake', stretch: 0.4,  lumpiness: 0.7,  lat: 6, lon: 14, twist: 0.0, crystals: 0 },
};
const DEFAULT_DNA = { shape: 'lumpy', stretch: 1.0, lumpiness: 0.5, lat: 7, lon: 9, twist: 0.0, crystals: 0 };

// Returns: { faces: [[{x,y,z},{x,y,z},{x,y,z}], ...], crystals: [{x,y,z,r}] }
function makeRockMesh(seed, dna) {
  const rng = mulberry32(seed);
  const { shape, stretch, lumpiness, lat, lon, twist } = dna;

  const verts = [];
  for (let i = 0; i <= lat; i++) {
    const phi = (i / lat) * Math.PI;
    const ring = [];
    const twistOff = twist * (i / lat);
    for (let j = 0; j < lon; j++) {
      const theta = (j / lon) * Math.PI * 2 + twistOff;
      let r = 1;

      // Shape-specific radius modulation
      if (shape === 'crystal') {
        // Prismatic: faceted bands; sharp points at top/bottom
        const band = Math.floor((j / lon) * 6);
        r *= 0.85 + (band % 2 === 0 ? 0.15 : 0);
        // Taper toward poles
        r *= Math.sin(phi) * 0.85 + 0.15;
        r *= 1 + (rng() - 0.5) * lumpiness;
      } else if (shape === 'shard') {
        // Long jagged spike: extreme top taper
        const t = i / lat;
        r *= Math.pow(Math.sin(phi), 0.6);
        if (t < 0.25) r *= 0.4 + t * 2;
        r *= 1 + (rng() - 0.5) * lumpiness * 1.4;
      } else if (shape === 'cluster') {
        // Multi-lobe: high-frequency angular bumps
        r *= 0.85 + 0.25 * Math.sin(theta * 3) * Math.sin(phi * 2);
        r *= 1 + (rng() - 0.5) * lumpiness;
      } else if (shape === 'cubic') {
        // Blocky: snap toward octahedral
        const ax = Math.abs(Math.sin(phi) * Math.cos(theta));
        const ay = Math.abs(Math.cos(phi));
        const az = Math.abs(Math.sin(phi) * Math.sin(theta));
        const m = Math.max(ax, ay, az);
        r *= 0.6 + 0.4 * m;
        r *= 1 + (rng() - 0.5) * lumpiness * 0.8;
      } else if (shape === 'flake') {
        // Flat slab: severe Y compression handled by stretch; mild lumps
        r *= 1 + (rng() - 0.5) * lumpiness;
      } else { // lumpy
        r *= 0.78 + rng() * lumpiness * 0.7;
      }

      const sx = Math.sin(phi) * Math.cos(theta) * r;
      const sy = Math.cos(phi) * r * stretch;
      const sz = Math.sin(phi) * Math.sin(theta) * r;
      ring.push({ x: sx, y: sy, z: sz });
    }
    verts.push(ring);
  }

  const faces = [];
  for (let i = 0; i < lat; i++) {
    for (let j = 0; j < lon; j++) {
      const a = verts[i][j];
      const b = verts[i][(j + 1) % lon];
      const c = verts[i + 1][j];
      const d = verts[i + 1][(j + 1) % lon];
      faces.push([a, b, d]);
      faces.push([a, d, c]);
    }
  }

  // Crystal accents — small bright specks studding the surface
  const crystals = [];
  for (let k = 0; k < (dna.crystals || 0); k++) {
    const phi = rng() * Math.PI;
    const theta = rng() * Math.PI * 2;
    const r = 1.05 + rng() * 0.08;
    crystals.push({
      x: Math.sin(phi) * Math.cos(theta) * r,
      y: Math.cos(phi) * r * stretch,
      z: Math.sin(phi) * Math.sin(theta) * r,
      r: 0.06 + rng() * 0.06,
    });
  }
  return { faces, crystals };
}

// Build a wreck silhouette: stretched fuselage + jagged broken fins + window slits
function makeWreckMesh(seed) {
  const rng = mulberry32(seed);
  const faces = [];
  const lat = 6, lon = 8;
  const verts = [];
  for (let i = 0; i <= lat; i++) {
    const phi = (i / lat) * Math.PI;
    const ring = [];
    for (let j = 0; j < lon; j++) {
      const theta = (j / lon) * Math.PI * 2;
      let r = 1;
      // Random damage gouges — chunks missing from hull
      if (rng() > 0.78) r *= 0.45 + rng() * 0.3;
      const sx = Math.sin(phi) * Math.cos(theta) * r * 1.8; // longer fuselage
      const sy = Math.cos(phi) * r * 0.55;
      const sz = Math.sin(phi) * Math.sin(theta) * r * 0.75;
      ring.push({ x: sx, y: sy, z: sz });
    }
    verts.push(ring);
  }
  for (let i = 0; i < lat; i++) {
    for (let j = 0; j < lon; j++) {
      const a = verts[i][j];
      const b = verts[i][(j + 1) % lon];
      const c = verts[i + 1][j];
      const d = verts[i + 1][(j + 1) % lon];
      faces.push([a, b, d]);
      faces.push([a, d, c]);
    }
  }
  // Broken vertical fin (top)
  faces.push([
    { x: 0.2, y: 0.45, z: 0 },
    { x: 1.2, y: 1.05, z: 0.05 },
    { x: 0.7, y: 0.5, z: 0.4 },
  ]);
  faces.push([
    { x: 0.2, y: 0.45, z: 0 },
    { x: 1.2, y: 1.05, z: 0.05 },
    { x: 0.7, y: 0.5, z: -0.4 },
  ]);
  // Snapped wing stub (side, jagged)
  faces.push([
    { x: -0.3, y: -0.3, z: 0 },
    { x: -1.4, y: -0.55, z: -0.2 },
    { x: -0.9, y: -0.35, z: 0.7 },
  ]);
  faces.push([
    { x: -0.3, y: -0.3, z: 0 },
    { x: -1.6, y: -0.4, z: 0.1 },
    { x: -0.9, y: -0.35, z: -0.6 },
  ]);
  // Cockpit nose nub
  faces.push([
    { x: 1.85, y: 0.05, z: 0 },
    { x: 1.6, y: 0.2, z: 0.25 },
    { x: 1.6, y: -0.2, z: 0.25 },
  ]);
  faces.push([
    { x: 1.85, y: 0.05, z: 0 },
    { x: 1.6, y: 0.2, z: -0.25 },
    { x: 1.6, y: -0.2, z: -0.25 },
  ]);
  return { faces, crystals: [] };
}

function rotateY(p, a) { const c = Math.cos(a), s = Math.sin(a); return { x: p.x*c + p.z*s, y: p.y, z: -p.x*s + p.z*c }; }
function rotateX(p, a) { const c = Math.cos(a), s = Math.sin(a); return { x: p.x, y: p.y*c - p.z*s, z: p.y*s + p.z*c }; }
function project(p, scale, cx, cy) { const persp = 1.6 / (1.6 + p.z); return { x: cx + p.x * scale * persp, y: cy + p.y * scale * persp, depth: p.z }; }

function HoloRock({ tier, sig, name, rotateSpeed = 1 }) {
  const tiers = window.TIERS;
  const t = tiers[tier] || tiers.unknown;
  const isWreck = tier === 'salvage' || tier === 'unknown' && /debris|wreck|hull/i.test(name || '');
  const seedKey = (name || '?') + ':' + (sig || 0);
  const dna = MINERAL_DNA[name] || DEFAULT_DNA;
  const mesh = React.useMemo(() => {
    const seed = hashStr(seedKey);
    return isWreck ? makeWreckMesh(seed) : makeRockMesh(seed, dna);
  }, [seedKey, isWreck, dna]);

  const svgRef = useRef(null);
  const facesRef = useRef([]);
  const crystalsRef = useRef([]);
  useEffect(() => {
    let raf, t0 = performance.now();
    const W = 320, H = 220, cx = W/2, cy = H/2 + 4;
    const baseScale = isWreck ? 52 : 64;
    const tick = (now) => {
      const dt = (now - t0) / 1000;
      const sp = (window.__rotSpeed ?? 1) * rotateSpeed;
      const ry = dt * 0.5 * sp;
      const rx = Math.sin(dt * 0.35 * sp) * 0.2;

      const projected = mesh.faces.map(face => {
        const rotated = face.map(p => rotateX(rotateY(p, ry), rx));
        const avgZ = (rotated[0].z + rotated[1].z + rotated[2].z) / 3;
        const ux = rotated[1].x - rotated[0].x, uy = rotated[1].y - rotated[0].y, uz = rotated[1].z - rotated[0].z;
        const vx = rotated[2].x - rotated[0].x, vy = rotated[2].y - rotated[0].y, vz = rotated[2].z - rotated[0].z;
        const nx = uy*vz - uz*vy, ny = uz*vx - ux*vz, nz = ux*vy - uy*vx;
        const nl = Math.sqrt(nx*nx + ny*ny + nz*nz) || 1;
        const lx = -0.4, ly = -0.6, lz = -0.7;
        const dot = (nx*lx + ny*ly + nz*lz) / nl;
        const lit = Math.max(0, Math.min(1, 0.35 + dot * 0.65));
        const projPts = rotated.map(p => project(p, baseScale, cx, cy));
        return { pts: projPts, depth: avgZ, lit, origIdx: 0 };
      }).map((f, i) => ({ ...f, origIdx: i }));

      projected.sort((a, b) => b.depth - a.depth);
      const polys = facesRef.current;
      // Reorder DOM: hidden by setting opacity per painter's order would shuffle indices — 
      // simpler: write points back to original index but apply painter sort via z-index trick
      // Instead, just write to original index with computed opacity (depth handled by listing order is fine for low-poly).
      mesh.faces.forEach((_, i) => {
        const f = projected.find(p => p.origIdx === i);
        const poly = polys[i];
        if (!poly || !f) return;
        poly.setAttribute('points', f.pts.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' '));
        poly.style.opacity = (0.5 + f.lit * 0.5).toFixed(3);
      });
      // Re-append in painter order so back faces draw first
      const parent = polys[0]?.parentNode;
      if (parent) {
        projected.forEach(f => {
          const poly = polys[f.origIdx];
          if (poly) parent.appendChild(poly);
        });
      }

      // Project crystals
      const crys = crystalsRef.current;
      mesh.crystals.forEach((c, i) => {
        const r = rotateX(rotateY(c, ry), rx);
        const p = project(r, baseScale, cx, cy);
        const el = crys[i];
        if (!el) return;
        el.setAttribute('cx', p.x.toFixed(1));
        el.setAttribute('cy', p.y.toFixed(1));
        el.style.opacity = r.z < 0 ? 1 : 0.25; // dim back-face crystals
      });

      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [mesh, rotateSpeed, isWreck]);

  return (
    <div className="mr-holo-stage" style={{ '--tier-color': t.color }}>
      <div className="mr-holo-floor"><div className="mr-holo-grid" /></div>
      <svg ref={svgRef} className="mr-holo-svg" viewBox="0 0 320 220" preserveAspectRatio="xMidYMid meet">
        <defs>
          <radialGradient id={`holo-glow-${tier}`} cx="50%" cy="40%" r="60%">
            <stop offset="0%" stopColor={t.color} stopOpacity="0.42" />
            <stop offset="100%" stopColor={t.color} stopOpacity="0" />
          </radialGradient>
        </defs>
        <ellipse cx="160" cy="118" rx="96" ry="58" fill={`url(#holo-glow-${tier})`} />
        <g className="mr-holo-mesh">
          {mesh.faces.map((_, i) => (
            <polygon
              key={i}
              ref={el => { facesRef.current[i] = el; }}
              fill={t.color}
              stroke={t.color}
              strokeWidth="0.5"
              strokeOpacity="0.7"
              fillOpacity="0.22"
            />
          ))}
          {mesh.crystals.map((c, i) => (
            <circle
              key={`c${i}`}
              ref={el => { crystalsRef.current[i] = el; }}
              r={(c.r * 8).toFixed(1)}
              fill="#fff"
              fillOpacity="0.85"
              style={{ filter: `drop-shadow(0 0 3px ${t.color})` }}
            />
          ))}
        </g>
      </svg>
      <div className="mr-holo-scan" />
      <div className="mr-holo-tag">{isWreck ? 'WRECK · SALVAGE' : `${(dna.shape || 'lumpy').toUpperCase()} · MINERAL`}</div>
    </div>
  );
}

// ============ EXPOSE GLOBALS ============
Object.assign(window, {
  useParallax, Panel, RivetBar, Readout, MrButton, LED,
  SignatureSpectrum, Stencil, HoloRock, chamferPath,
});
