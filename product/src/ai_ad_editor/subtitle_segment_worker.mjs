// Fixed local JSON adapter. The adjacent upstream module is MIT licensed;
// its exact original bytes and license are distributed with this package.
import { readFileSync } from 'node:fs';
import { segmentLine, alignTranslation, replacePiece, subtitleEnd, subtitleCells,
  SUBTITLE_SEGMENT_RULES } from './openfilm_subtitle_segments.mjs';

const PROTOCOL = 'agent-video-subtitle-segment-v1';
const cpToUnit = (text, index) => [...text].slice(0, index).join('').length;
const unitToCp = (text, index) => [...text.slice(0, index)].length;

function timed(line) {
  return { text: line.text, startMs: 0, endMs: line.duration_ms,
    ...(line.marks?.length ? { marks: line.marks.map(m => ({
      index: cpToUnit(line.text, m.index), startMs: m.start_ms })) } : {}) };
}

function pieces(line, R) {
  const raw = segmentLine(line, R);
  const translation = line.translation === undefined ? null : alignTranslation(line.translation, raw, R);
  return { raw, translation, public: raw.map((p, i) => ({
    part: p.part, text: p.text, display_text: subtitleEnd(p.text),
    from: unitToCp(line.text, p.from), to: unitToCp(line.text, p.to),
    start_ms: p.startMs, end_ms: p.endMs, cells: subtitleCells(subtitleEnd(p.text)),
    marks: (p.marks ?? []).map(m => ({ index: unitToCp(p.text, m.index), start_ms: m.startMs })),
    ...(translation ? { translation: { text: translation[i].text,
      from: unitToCp(line.translation, translation[i].from),
      to: unitToCp(line.translation, translation[i].to) } } : {}),
  })) };
}

function processLine(source, edits, R) {
  const line = timed(source);
  if (source.translation !== undefined) line.translation = source.translation;
  const initial = pieces(line, R);
  const changes = [];
  for (const target of ['text', 'translation']) {
    const chosen = edits.filter(e => e.target === target);
    if (!chosen.length) continue;
    if (target === 'translation' && line.translation === undefined) throw Error('Translation missing');
    const original = target === 'text' ? line.text : line.translation;
    const ranges = chosen.map(e => {
      const p = initial.raw[e.part];
      if (!p) throw Error('Correction part missing');
      const span = target === 'text' ? p : initial.translation[e.part];
      return { ...e, from: span.from, to: span.to, startMs: p.startMs };
    }).sort((a, b) => b.from - a.from || b.to - a.to);
    for (let i = 1; i < ranges.length; i++) {
      if (ranges[i].to > ranges[i - 1].from || ranges[i].from === ranges[i - 1].from)
        throw Error('Overlapping corrections, including a shared translation');
    }
    let current = target === 'text' ? line : { text: original, startMs: 0, endMs: line.endMs };
    let leadingShift = 0;
    for (const e of ranges) {
      const span = { from: e.from - leadingShift, to: e.to - leadingShift };
      const removedLead = current.text.length - current.text.trimStart().length;
      const next = replacePiece(current, span, e.text, e.startMs);
      changes.push({ target, part: e.part, before: original.slice(e.from, e.to), after: e.text,
        from: unitToCp(original, e.from), to: unitToCp(original, e.to) });
      current = { ...current, text: next.text, marks: next.marks ?? [] };
      leadingShift += removedLead;
    }
    if (target === 'text') { line.text = current.text; line.marks = current.marks; }
    else line.translation = current.text;
  }
  if (!line.text.trim()) throw Error('Correction removed the entire line; remove the line explicitly instead');
  const result = pieces(line, R);
  return { id: source.id, text: line.text,
    marks: (line.marks ?? []).map(m => ({ index: unitToCp(line.text, m.index), start_ms: m.startMs })),
    ...(line.translation !== undefined ? { translation: line.translation } : {}),
    pieces: result.public, changes, ...(edits.length ? { before_pieces: initial.public } : {}) };
}

try {
  const request = JSON.parse(readFileSync(0, 'utf8'));
  if (request.protocol !== PROTOCOL || request.network !== 'disabled') throw Error('Invalid offline protocol');
  const [major, minor] = process.versions.node.split('.').map(Number);
  if (major < 22 || (major === 22 && minor < 2)) throw Error('Node >=22.2 required');
  const R = { ...SUBTITLE_SEGMENT_RULES, ...request.rules,
    weight: { ...SUBTITLE_SEGMENT_RULES.weight, ...request.rules?.weight },
    cost: { ...SUBTITLE_SEGMENT_RULES.cost, ...request.rules?.cost } };
  const edits = request.edits ?? [];
  const lines = request.lines.map(line => processLine(line, edits.filter(e => e.line_id === line.id), R));
  process.stdout.write(JSON.stringify({ protocol: PROTOCOL, status: 'succeeded', network: 'disabled',
    versions: { node: process.versions.node, icu: process.versions.icu, unicode: process.versions.unicode },
    rules: R, lines }));
} catch (e) {
  process.stdout.write(JSON.stringify({ protocol: PROTOCOL, status: 'failed', network: 'disabled',
    message: String(e.message ?? e) }));
  process.exitCode = 2;
}
