// Extracted from openfilm/examples@2e8f47866bc2d32305cd5d97adcffd7480df2297
// one-prompt/src/px/stroke.js; OpenFilm and Giacomo Magnanini MIT; see bundled licenses.
export function drawStrokeText(c, st, len) {
  let head = null;
  c.beginPath();
  for (let i = 0; i < st.strokes.length; i++) {
    const s0 = st.startLen[i];
    if (s0 >= len) break;
    const pts = st.strokes[i], L = st.lens[i];
    const remain = len - s0;
    c.moveTo(pts[0].x, pts[0].y);
    let j = 1;
    for (; j < pts.length && L[j] <= remain; j++) c.lineTo(pts[j].x, pts[j].y);
    if (j < pts.length) {
      const a = pts[j - 1], b = pts[j];
      const u = (remain - L[j - 1]) / Math.max(1e-6, L[j] - L[j - 1]);
      const x = a.x + (b.x - a.x) * u, y = a.y + (b.y - a.y) * u;
      c.lineTo(x, y);
      head = { x, y, angle: Math.atan2(b.y - a.y, b.x - a.x) };
    } else {
      const a = pts[pts.length - 2] ?? pts[0], b = pts[pts.length - 1];
      head = { x: b.x, y: b.y, angle: Math.atan2(b.y - a.y, b.x - a.x) };
    }
  }
  c.stroke();
  return head;
}

/**
 * Map song time -> written length so each char is written while its word is sung.
 * `charTimes[i]` = [start, end] time for char i (e.g. derived from word timings).
 */
export function writtenLength(st, charTimes, t) {
  let len = 0;
  for (let i = 0; i < st.charRange.length; i++) {
    const [a, b] = st.charRange[i];
    const [t0, t1] = charTimes[i] ?? [Infinity, Infinity];
    if (t >= t1) len = b;
    else if (t > t0) { len = a + (b - a) * ((t - t0) / Math.max(1e-3, t1 - t0)); break; }
    else break;
  }
  return len;
}
