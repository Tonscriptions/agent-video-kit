import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readdirSync, statSync, readFileSync, writeFileSync, mkdirSync, utimesSync } from 'node:fs';
import { extname, join } from 'node:path';
const FILM_FILE = 'film.html';
const WORKER_MEMORY = 1.5 * 2 ** 30;
const RESERVE = 2 * 2 ** 30;
const FRAMES_PER_WORKER = 60;
const MAX_WORKERS = 4;
const SOUNDS = new Set(['.mp3', '.wav', '.m4a', '.aac', '.ogg', '.oga', '.opus', '.flac', '.aif', '.aiff', '.aifc', '.vtt', '.srt']);
const MOST_FILES = 20_000;
const VERSION = 1;
export function defaultWorkers({ cores, available } = machine(), frames = Infinity) {
  return Math.max(1, Math.min(MAX_WORKERS, cores - 1, Math.floor((available - RESERVE) / WORKER_MEMORY), Math.floor(frames / FRAMES_PER_WORKER)));
}
export function projectPrint(root) {
  const hash = createHash('sha1');
  let seen = 0;
  /** @param {string} dir @param {string} rel */
  const walk = (dir, rel) => {
    let names;
    try { names = readdirSync(dir, { withFileTypes: true }); } catch { return; }
    names.sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
    for (const d of names) {
      if (d.name.startsWith('.') || seen > MOST_FILES) continue;
      const path = rel ? `${rel}/${d.name}` : d.name;
      if (d.isDirectory()) { walk(join(dir, d.name), path); continue; }
      if (path === FILM_FILE || SOUNDS.has(extname(d.name).toLowerCase())) continue;
      seen += 1;
      try { const s = statSync(join(dir, d.name)); hash.update(`${path}\0${s.size}\0${Math.round(s.mtimeMs)}\n`); } catch { /* gone meanwhile */ }
    }
  };
  walk(root, '');
  return hash.digest('hex');
}
export function previewKey(root, a, b, fps, height, print = projectPrint(root)) {
  let film = '';
  try { film = readFileSync(join(root, FILM_FILE), 'utf8'); } catch { /* none: nothing renders */ }
  return createHash('sha1').update(`${VERSION}\0${film}\0${print}\0${a}\0${b}\0${fps}\0${height}`).digest('hex').slice(0, 20);
}
function askKey(ask) {
        const { preset, label, ...rest } = /** @type {ExportAsk & { preset?: string }} */ (ask);
        const same = ask.kind === 'video' || ask.kind === 'gif' ? JSON.stringify(rest, Object.keys(rest).sort()) : null;
return same;
}

const checks = [];
function check(name, actual, expected) {
  assert.deepEqual(actual, expected, name);
  checks.push({ name, actual, expected, passed: true });
}
const GiB = 2 ** 30;
check('workers-high-memory-capped', defaultWorkers({cores: 8, available: 16 * GiB}, 600), 4);
check('workers-zero-memory-still-one', defaultWorkers({cores: 8, available: 0}, 600), 1);
check('workers-one-core-still-one', defaultWorkers({cores: 1, available: 16 * GiB}, 600), 1);
check('workers-short-job', defaultWorkers({cores: 8, available: 16 * GiB}, 59), 1);
check('workers-frame-budget', defaultWorkers({cores: 8, available: 16 * GiB}, 120), 2);
check('workers-memory-budget', defaultWorkers({cores: 8, available: 5 * GiB}, 600), 2);
const base = { kind: 'video', codec: 'h264', shortEdge: 1080, fps: 30, range: [0, 4] };
check('signature-platform-label-ignored', askKey({...base, preset:'A', label:'a'}) === askKey({...base, preset:'B', label:'b'}), true);
check('signature-object-key-order', askKey(base) === askKey({range:[0,4], fps:30, shortEdge:1080, codec:'h264', kind:'video'}), true);
check('signature-different-custom-names-prevent-reuse', askKey({...base,name:'A'}) === askKey({...base,name:'B'}), false);
check('signature-resolution-separated', askKey(base) === askKey({...base,shortEdge:720}), false);
check('signature-fps-separated', askKey(base) === askKey({...base,fps:24}), false);
check('signature-codec-separated', askKey(base) === askKey({...base,codec:'hevc'}), false);
check('signature-range-separated', askKey(base) === askKey({...base,range:[0,5]}), false);
const root = process.argv[2];
mkdirSync(root, { recursive: true });
writeFileSync(join(root, FILM_FILE), '<section></section>');
const asset = join(root, 'title.html'), fixed = new Date('2026-10-01T00:00:00.000Z');
writeFileSync(asset, '<p>A</p>'); utimesSync(asset, fixed, fixed);
const contentBefore = createHash('sha256').update(readFileSync(asset)).digest('hex');
const printBefore = projectPrint(root), keyBefore = previewKey(root, 0, 4, 30, 360);
writeFileSync(asset, '<p>B</p>'); utimesSync(asset, fixed, fixed);
const contentAfter = createHash('sha256').update(readFileSync(asset)).digest('hex');
check('cache-asset-content-changed', contentBefore !== contentAfter, true);
check('cache-project-fingerprint-stale', printBefore === projectPrint(root), true);
check('cache-preview-key-stale', keyBefore === previewKey(root, 0, 4, 30, 360), true);
console.log(JSON.stringify({ checks, scope: 'isolated original declarations; not full upstream modules, exports or rendering',
  cache: { contentBefore, contentAfter, printBefore, printAfter:projectPrint(root), keyBefore, keyAfter:previewKey(root,0,4,30,360) } }));
