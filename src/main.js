import Lenis from 'lenis';

// One pinned stage, one continuous Blender film. Scroll position picks the frame, so the film plays forward as you
// scroll down and rewinds as you scroll up. Nothing runs on a timer except the idle loop when you rest on the hero.
//
//   film  Scene 01, Enter the universe       frames   1-120
//   hold  the hero frame; at rest the idle loop takes over (rings pulse, dust orbits)
//   film  Scene 02, The shapes arrive         frames 121-260 (the same timeline, carried on)
//   hold  the end of Scene 02
//   film  Scene 03, Gravity                   frames 261-565: the shapes are drawn in and the camera settles low for
//         the moment (the headline inside the system), then the cube breaks away and the shapes follow it; the camera
//         tracks alongside, then comes round ahead. A rest at each of the three, where the words are. The two moves
//         after the moment travel far, so they have the most frames per scroll.
//   film  Scenes 04-06, The creation          frames 566-1000: the system comes to rest and the shapes build the brand's
//         'Structure For Clarity' totem (the scroll builds it); it ignites and the second headline stands beside it;
//         then the camera pulls far back to one glowing shape, for the last words. The footer follows the stage.
const FILMS = [
  { dir: 's01', from: 1, count: 120 },
  { dir: 's02', from: 121, count: 140 },
  { dir: 's03', from: 261, count: 305 },
  { dir: 's04', from: 566, count: 435 },
];
const TOTAL = FILMS.reduce((n, f) => n + f.count, 0);
const SEGMENTS = [                         // scroll length of each part, in viewport heights
  { kind: 'film', a: 0, b: 119, vh: 300 },
  { kind: 'hold', a: 119, b: 119, vh: 70, loop: true },
  { kind: 'film', a: 119, b: 259, vh: 340 },
  { kind: 'hold', a: 259, b: 259, vh: 50 },
  { kind: 'film', a: 259, b: 324, vh: 170 },     // gravity: the shapes are drawn in, the camera settles low
  { kind: 'hold', a: 324, b: 324, vh: 70 },      // the moment: the headline stands inside the system
  { kind: 'film', a: 324, b: 424, vh: 200 },     // the cube breaks away; the camera tracks alongside
  { kind: 'hold', a: 424, b: 424, vh: 50 },
  { kind: 'film', a: 424, b: 564, vh: 220 },     // round ahead, looking back down the spiral
  { kind: 'hold', a: 564, b: 564, vh: 60 },
  { kind: 'film', a: 564, b: 699, vh: 220 },     // it comes to rest; the camera comes round to face it
  { kind: 'film', a: 699, b: 799, vh: 280 },     // the shapes build the totem, one by one, as you scroll
  { kind: 'hold', a: 799, b: 799, vh: 40 },
  { kind: 'film', a: 799, b: 879, vh: 180 },     // it ignites; the dust bursts outward
  { kind: 'hold', a: 879, b: 879, vh: 70 },      // 'And ideas become worlds.'
  { kind: 'film', a: 879, b: 999, vh: 240 },     // far back, to one glowing shape
  { kind: 'hold', a: 999, b: 999, vh: 90 },      // the last words; then the footer
];
const LOOP_L = 96, LOOP_C = 24, LOOP_FPS = 24;
const BASE = import.meta.env.BASE_URL;        // '/' locally and on Netlify, '/squaredc-home/' on GitHub Pages
const loopSrc = i => `${BASE}frames/s01loop/l_${String(i + 1).padStart(4, '0')}.webp`;
const matteSrc = (dir, f) => `${BASE}frames/${dir}/m_${String(f).padStart(4, '0')}.webp`;
function srcOf(i) {                         // global frame index (0-based) -> file
  let k = i;
  for (const f of FILMS) {
    if (k < f.count) return `${BASE}frames/${f.dir}/f_${String(f.from + k).padStart(4, '0')}.webp`;
    k -= f.count;
  }
  return null;
}

const section = document.getElementById('universe');
const stage = section.querySelector('.stage');
const canvas = document.getElementById('film');
const ctx = canvas.getContext('2d', { alpha: false });
const fore = document.getElementById('fore');
const fctx = fore.getContext('2d');
const moments = [...stage.querySelectorAll('.moment')];
const finale = stage.querySelector('.finale');
const notes = [...stage.querySelectorAll('.note')];
const leads = [...stage.querySelectorAll('.lead')];
const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
const totalVh = SEGMENTS.reduce((n, s) => n + s.vh, 0);
section.style.height = `${100 + totalVh}vh`;

// ---------------------------------------------------------------------------------------------- frames
// Each film loads coarse to fine (first and last, then every 16th, 8th, 4th, 2nd, all) so scrolling works from the
// first pass and sharpens as the rest arrive. Scene 01 and its idle loop come first; the headline mattes come last.
const frames = new Array(TOTAL);
const loopFrames = new Array(LOOP_L);
const mattes = {};                          // film frame number -> image: white, alpha = what is in front of the type
let loaded = 0, loopLoaded = 0;
// The tracks of Scene 03 and of Scenes 04-06, one entry per frame: the cube's centre and size on the frame, and the
// corners of that scene's headline plane
const getTrack = dir => fetch(`${BASE}frames/${dir}/track.json`).then(r => (r.ok ? r.json() : null)).catch(() => null);
const trackP = getTrack('s03'), track4P = getTrack('s04');
let track = null, track4 = null;
trackP.then(t => { track = t; forcePaint = true; });
track4P.then(t => { track4 = t; forcePaint = true; });

function coarseToFine(a, b) {
  const out = [], seen = new Set();
  for (const i of [a, b]) { seen.add(i); out.push(i); }
  for (const step of [16, 8, 4, 2, 1]) for (let i = a; i <= b; i += step) if (!seen.has(i)) { seen.add(i); out.push(i); }
  return out;
}
function loadImg(url) {
  return new Promise(resolve => {
    const im = new Image(); im.decoding = 'async';
    im.onload = () => resolve(im); im.onerror = () => resolve(null); im.src = url;
  });
}
async function pool(list, n, job) {
  let next = 0;
  await Promise.all(Array.from({ length: n }, async () => { while (next < list.length) await job(list[next++]); }));
}
function progressBar() { stage.style.setProperty('--lp', (loaded / TOTAL).toFixed(3)); }
async function loadAll() {
  await pool(coarseToFine(0, FILMS[0].count - 1), 6, async i => { frames[i] = frames[i] || await loadImg(srcOf(i)); loaded++; progressBar(); });
  pool([...Array(LOOP_L).keys()], 4, async i => { loopFrames[i] = await loadImg(loopSrc(i)); loopLoaded++; });
  let start = FILMS[0].count;
  for (const f of FILMS.slice(1)) {          // later films in story order, each coarse to fine
    await pool(coarseToFine(start, start + f.count - 1), 6, async i => { frames[i] = await loadImg(srcOf(i)); loaded++; progressBar(); });
    start += f.count;
  }
  stage.style.setProperty('--l', 0);
  for (const [tp, dir] of [[trackP, 's03m'], [track4P, 's04m']]) {
    const t = await tp;
    if (!t) continue;
    const list = []; for (let f = t.fore[0]; f <= t.fore[1]; f++) list.push(f);
    await pool(list, 4, async f => { mattes[f] = await loadImg(matteSrc(dir, f)); });
    forcePaint = true;
  }
}

function nearest(i) {
  if (frames[i]) return frames[i];
  for (let d = 1; d < TOTAL; d++) {
    if (frames[i - d]) return frames[i - d];
    if (frames[i + d]) return frames[i + d];
  }
  return null;
}

// ---------------------------------------------------------------------------------------------- drawing
let forcePaint = true;        // a resize clears the canvas: repaint on the next tick even if the frame is unchanged
function resize() {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = fore.width = Math.round(stage.clientWidth * dpr);
  canvas.height = fore.height = Math.round(stage.clientHeight * dpr);
  moments.forEach(m => m.classList.toggle('flat', stage.clientWidth / stage.clientHeight < 1.2));
  forcePaint = true;
}
function cover(c, im, alpha = 1) {
  const cw = c.canvas.width, ch = c.canvas.height;
  const s = Math.max(cw / im.naturalWidth, ch / im.naturalHeight);       // cover
  const w = im.naturalWidth * s, h = im.naturalHeight * s;
  c.globalAlpha = alpha;
  c.imageSmoothingQuality = 'high';
  c.drawImage(im, (cw - w) / 2, (ch - h) / 2, w, h);
  c.globalAlpha = 1;
}
const paint = (im, alpha) => cover(ctx, im, alpha);

(function grain() {            // film grain: one small noise tile, animated by CSS
  const c = document.createElement('canvas'); c.width = c.height = 160;
  const g = c.getContext('2d'); const d = g.createImageData(160, 160);
  for (let k = 0; k < d.data.length; k += 4) { const v = Math.random() * 255; d.data[k] = d.data[k + 1] = d.data[k + 2] = v; d.data[k + 3] = 255; }
  g.putImageData(d, 0, 0);
  section.querySelector('.grain').style.backgroundImage = `url(${c.toDataURL()})`;
})();

// ---------------------------------------------------------------------------------------------- scroll -> timeline
const clamp01 = x => Math.min(1, Math.max(0, x));
const smooth = x => { x = clamp01(x); return x * x * (3 - 2 * x); };

// Where we are: which segment, how far through it, and the (fractional) frame that maps to.
function locate() {
  const vh = window.innerHeight / 100;
  let y = Math.max(0, -section.getBoundingClientRect().top);
  for (let s = 0; s < SEGMENTS.length; s++) {
    const seg = SEGMENTS[s], len = seg.vh * vh;
    if (y <= len || s === SEGMENTS.length - 1) {
      const t = clamp01(y / len);
      return { s, t, frame: seg.a + (seg.b - seg.a) * t };
    }
    y -= len;
  }
}
// Copy beats, each tied to a point in one segment.
const at = (loc, s, t0, dur) => loc.s > s ? 1 : loc.s < s ? 0 : smooth((loc.t - t0) / dur);
function copy(loc) {
  const st = stage.style;
  const out1 = at(loc, 2, 0.02, 0.12);                         // Scene 01's line clears as Scene 02 begins
  st.setProperty('--a1', (at(loc, 0, 0.5, 0.12) * (1 - out1)).toFixed(3));
  st.setProperty('--a2', (at(loc, 0, 0.55, 0.12) * (1 - out1)).toFixed(3));
  st.setProperty('--b', (at(loc, 0, 0.64, 0.12) * (1 - out1)).toFixed(3));
  const out2 = at(loc, 4, 0.04, 0.14);                         // Scene 02's lines clear as gravity takes over
  st.setProperty('--c1', (at(loc, 2, 0.36, 0.12) * (1 - out2)).toFixed(3)); // Everything starts with a shape.
  st.setProperty('--c2', (at(loc, 2, 0.52, 0.1) * (1 - out2)).toFixed(3));  // An idea.
  st.setProperty('--c3', (at(loc, 2, 0.62, 0.1) * (1 - out2)).toFixed(3));  // A thought.
  st.setProperty('--c4', (at(loc, 2, 0.72, 0.1) * (1 - out2)).toFixed(3));  // A possibility.
  st.setProperty('--h', (1 - at(loc, 0, 0, 0.06)).toFixed(3));
  st.setProperty('--e', at(loc, SEGMENTS.length - 1, 0.45, 0.55).toFixed(3));
}

// ---------------------------------------------------------------------------------------------- scene 03 overlays
// These follow the film frame on screen (not the scroll), so the words stay locked to the picture.
function frameBox() {          // where the cover-fitted 16:9 film sits on the stage, in CSS px
  const W = stage.clientWidth, H = stage.clientHeight, s = Math.max(W / 16, H / 9);
  return { x: (W - 16 * s) / 2, y: (H - 9 * s) / 2, w: 16 * s, h: 9 * s };
}
// The projective map taking the headline's box (bw x bh) onto four points (tl, tr, br, bl), as a CSS matrix3d.
function quadMatrix(q, bw, bh, fb) {
  const [[x0, y0], [x1, y1], [x2, y2], [x3, y3]] = q.map(([x, y]) => [fb.x + x * fb.w, fb.y + y * fb.h]);
  const dx1 = x1 - x2, dx2 = x3 - x2, dx3 = x0 - x1 + x2 - x3;
  const dy1 = y1 - y2, dy2 = y3 - y2, dy3 = y0 - y1 + y2 - y3;
  const den = dx1 * dy2 - dx2 * dy1;
  const g = (dx3 * dy2 - dx2 * dy3) / den, h = (dx1 * dy3 - dx3 * dy1) / den;
  const a = x1 - x0 + g * x1, b = x3 - x0 + h * x3, d = y1 - y0 + g * y1, e = y3 - y0 + h * y3;
  return `matrix3d(${a / bw},${d / bw},0,${g / bw},${b / bh},${e / bh},0,${h / bh},0,0,1,0,${x0},${y0},0,1)`;
}
// The notes: the film frames each one lives on, from the track's two rests (alongside, looking back): each comes in
// over the last stretch before its rest; the first goes as the camera swings away.
const noteBeats = t => [{ a: t.b - 1 - 24, b: t.b - 1 + 8 }, { a: t.c - 1 - 26, b: t.c - 1 + 2 }];
function noteAt(k, idx, T, fb) {
  const el = notes[k], lead = leads[k], beat = T && noteBeats(track)[k];
  const p = T ? smooth((idx - beat.a) / 20) * (1 - smooth((idx - beat.b) / 16)) : 0;
  if (p <= 0.001) { el.style.visibility = 'hidden'; lead.style.opacity = 0; return; }
  const W = stage.clientWidth;
  const cx = fb.x + T.c[0] * fb.w, cy = fb.y + T.c[1] * fb.h, rr = T.r * fb.w;
  const tw = el.offsetWidth, th = el.offsetHeight;
  const L = Math.max(26, rr * 0.75);
  let dir = 1;                                              // out to the upper right, unless that runs off the stage
  if (cx + rr * 0.5 + L + tw + 40 > W - 24) dir = -1;
  const ax = cx + dir * rr * 0.5, ay = cy - rr * 0.5;       // on the cube's shoulder
  const ex = ax + dir * L, ey = ay - L;                     // the elbow
  const fx = ex + dir * (tw + 18);                          // the end of the rule under the words
  const path = lead.firstElementChild, px = lead.lastElementChild;
  path.setAttribute('d', `M${ax},${ay}L${ex},${ey}L${fx},${ey}`);
  const len = Math.SQRT2 * L + tw + 18;
  path.style.strokeDasharray = len; path.style.strokeDashoffset = len * (1 - smooth(p * 1.25));
  px.setAttribute('x', ax - 3); px.setAttribute('y', ay - 3);
  lead.style.opacity = Math.min(1, p * 2);
  el.style.visibility = 'visible';
  const tx = Math.max(24, Math.min(W - 24 - tw, dir > 0 ? ex + 10 : ex - 10 - tw));   // never off the stage
  el.style.transform = `translate(${tx}px,${ey - th - 6}px)`;
  el.style.setProperty('--n', smooth(p * 1.4 - 0.4).toFixed(3));
}
// The two headlines: when each rises in and when it lets go (film frame indices), and whose track carries its plane.
const MOMENTS = [
  { el: moments[0], track: () => track, in1: 296, in2: 304, out: 344, outLen: 26 },   // Ideas attract ideas.
  { el: moments[1], track: () => track4, in1: 852, in2: 860, out: 893, outLen: 30 },  // And ideas become worlds.
];
let shownIdx = -1;
function overlays(idx, force) {
  if (idx === shownIdx && !force) return;
  shownIdx = idx;
  const f = idx + 1;                                        // film frame number
  const fb = frameBox();
  // each headline rises in as the camera settles, then stays where it is in the world and goes with it
  let drawn = false;
  for (const M of MOMENTS) {
    const t = M.track(), T = t && t.frames[f - t.from];
    const m1 = smooth((idx - M.in1) / 18), m2 = smooth((idx - M.in2) / 18), stay = 1 - smooth((idx - M.out) / M.outLen);
    const flat = M.el.classList.contains('flat');
    const on = m1 > 0 && stay > 0 && (flat || (T && T.q));
    M.el.style.visibility = on ? 'visible' : 'hidden';
    M.el.style.opacity = stay.toFixed(3);
    M.el.style.setProperty('--m1', m1.toFixed(3)); M.el.style.setProperty('--m2', m2.toFixed(3));
    if (on && !flat) M.el.style.transform = quadMatrix(T.q, t.box[0], t.box[1], fb);
    // in front of it: the film again, cut by this frame's matte (only with the exact frame and its matte)
    const mt = mattes[f], im = frames[idx];
    if (on && !flat && mt && im) {
      fctx.globalCompositeOperation = 'copy'; cover(fctx, mt);
      fctx.globalCompositeOperation = 'source-in'; cover(fctx, im);
      fctx.globalCompositeOperation = 'source-over';
      drawn = true;
    }
  }
  fore.style.visibility = drawn ? 'visible' : 'hidden';
  // the notes ride with the cube; past the end of Scene 03 they hold its last frame while they fade
  const Tn = track && f >= track.from ? track.frames[Math.min(f - track.from, track.frames.length - 1)] : null;
  notes.forEach((_, k) => noteAt(k, idx, Tn, fb));
  // the finale, under the one shape that remains
  [952, 962, 972, 982, 990].forEach((a, k) => finale.style.setProperty(`--f${k + 1}`, smooth((idx - a) / 18).toFixed(3)));
}

resize();
window.addEventListener('resize', resize);

if (reduced) {
  // Reduced motion: no film. The hero frame, its copy in place, a short page.
  section.style.height = '100vh';
  loadImg(srcOf(119)).then(im => { if (im) paint(im); stage.style.setProperty('--l', 0); });
  copy({ s: 1, t: 1, frame: 119 });
} else {
  const lenis = new Lenis({ lerp: 0.085, smoothWheel: true });
  let cur = 0, lastY = -1, lastMove = 0, mode = 'film', loopT0 = 0, fade = null, shown = null;
  loadImg(srcOf(0)).then(im => { frames[0] = im; loaded++; forcePaint = true; loadAll(); });
  const tick = t => {
    lenis.raf(t);
    const loc = locate();
    if (Math.abs(window.scrollY - lastY) > 0.5) { lastY = window.scrollY; lastMove = t; }
    const target = loc.frame;
    cur += (target - cur) * 0.22;                       // a touch of inertia on top of Lenis: no stepping between frames
    if (Math.abs(target - cur) < 0.01) cur = target;

    // Resting on the hero frame -> the idle loop fades in; any scroll on -> straight back to the film.
    const onHero = SEGMENTS[loc.s].loop && Math.abs(cur - 119) < 0.05;
    if (mode === 'film' && onHero && t - lastMove > 200 && loopLoaded >= LOOP_L * 0.9) {
      mode = 'loop'; loopT0 = t; fade = { from: shown || nearest(119), start: t, dur: 600 };
    } else if (mode === 'loop' && (!onHero || t - lastMove < 50)) {
      mode = 'film'; fade = { from: shown, start: t, dur: 300 };
    }

    let im;
    const idx = Math.round(cur);
    if (mode === 'loop') {
      const k = (Math.floor((t - loopT0) / 1000 * LOOP_FPS) + LOOP_C) % LOOP_L;   // start nearest the film's end
      im = loopFrames[k] || nearest(119);
    } else {
      im = nearest(idx);
    }
    const repaint = forcePaint;
    if (im) {
      if (fade && fade.from) {
        const a = Math.min(1, (t - fade.start) / fade.dur);
        paint(fade.from); paint(im, a * a * (3 - 2 * a));
        if (a >= 1) fade = null;
      } else if (mode === 'loop' || im !== shown || forcePaint) {
        paint(im); forcePaint = false;
      }
      shown = im;
    }
    overlays(mode === 'loop' ? 119 : idx, repaint || im !== frames[idx]);
    copy(loc);
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}
