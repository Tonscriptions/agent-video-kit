import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { BrowserPool } from './browser-pool.mjs';
import { mixGraph } from './shared.mjs';
import { prores709 } from './encoders.mjs';
import { nleFps, nleRate, frameSpan, planNleTimeline } from './nle.mjs';

const observations = [];
const add = (id, evidence) => observations.push({ id, evidence });

const [software, apple] = [prores709('prores_ks', true), prores709('prores_videotoolbox', true)];
assert.match(software.pix, /out_color_matrix=bt709/);
assert.match(software.pix, /yuva444p10le/);
assert.match(apple.pix, /^format=bgra,/);
add('color-output-options', { software, apple, scope: 'Options only; no pixel, Apple encoder or HDR acceptance' });

const mono = mixGraph([{ file: 'voice.wav', at: 0, from: 0, to: 1, speed: 1, volume: 1, channels: 1 }], 1);
const stereo = mixGraph([{ file: 'stereo.wav', at: 0, from: 0, to: 1, speed: 1, volume: 1, channels: 2 }], 1);
assert.match(mono.filter, /pan=stereo\|c0=c0\|c1=c0/);
assert.doesNotMatch(stereo.filter, /pan=stereo/);
add('mono-and-stereo-plans', { mono, stereo, scope: 'Graph strings only; no PCM decode or listening' });

const duplicate = mixGraph([
  { file: 'same.wav', at: 0, from: 0, to: 1, speed: 1, volume: 1, channels: 1 },
  { file: 'same.wav', at: 1, from: 2, to: 3, speed: 1, volume: 0.5, channels: 1 },
], 2);
assert.equal(duplicate.inputs.filter(x => x === '-i').length, 1);
assert.match(duplicate.filter, /asplit=2/);
add('duplicate-audio-inputs', duplicate);

let started = 0, closed = 0;
const pool = new BrowserPool({ start: async () => {
  started++;
  return { isConnected: () => true, close: async () => { closed++; } };
} });
const both = await Promise.all([pool.take(2), pool.take(2)]);
assert.equal(pool.size, 4);
await pool.close();
assert.equal(closed, 4);
add('pool-global-capacity', { started, maximumSimultaneousMocks: 4, closed,
  conclusion: 'No independent global capacity cap; each caller must reserve a bounded budget', mockOnly: true });

const picture = { id: 'a', kind: 'video', src: 'a.webm', path: join('C:', 'inputs', 'a.webm'),
  at: 0, end: 1, from: 0, speed: 1, track: 0, hidden: false,
  facts: { w: 160, h: 96, fps: 25, duration: 1, hasVideo: true, hasAudio: false, alpha: true } };
const opts = { title: 'test', fps: 30, audio: 'clips', media: 'copy', mediaDir: join('C:', 'output', 'media') };
const film = { stage: { w: 160, h: 96 }, duration: 1, pictures: [picture], sounds: [] };
const alpha = planNleTimeline(film, { ...opts, alpha: 'png' });
assert.ok(alpha.files.some(f => f.job.kind === 'transcode' && f.job.to === 'png'));
assert.ok(alpha.files.every(f => f.path === join(opts.mediaDir, f.name)));
add('nle-png-alpha-native-paths', { files: alpha.files, scope: 'Planning only; no MOV encoded or target NLE opened' });

add('nle-rate-and-short-span', { requested: [48, 90, 120], chosen: [48, 90, 120].map(nleFps),
  tinySpan: frameSpan(0, 0.001, nleRate(30)) });

const seekable = readFileSync(new URL('./original-seekable.mjs.txt', import.meta.url), 'utf8');
const baseMatch = seekable.match(/const copyBase = [\s\S]*?\n  join\([^\n]+\);/);
assert.ok(baseMatch);
const declaration = baseMatch[0];
assert.ok(declaration.includes('stat.size') && declaration.includes('stat.mtimeMs'));
assert.doesNotMatch(declaration, /readFile/);
const hash = b => createHash('sha1').update(b).digest('hex').slice(0, 12);
const copyBase = new Function('join', 'hash', 'VERSION', declaration + '\nreturn copyBase;')(join, hash, 2);
const a = Buffer.from('original-A'), b = Buffer.from('original-B');
const identity = { size: a.length, mtimeMs: 1700000000000 };
const first = copyBase('C:/same.mp4', 'C:/project', identity);
const second = copyBase('C:/same.mp4', 'C:/project', { size: b.length, mtimeMs: identity.mtimeMs });
assert.notEqual(createHash('sha256').update(a).digest('hex'), createHash('sha256').update(b).digest('hex'));
assert.equal(first, second);
add('proxy-content-identity', { declaration, first, second, changedContentSameMetadata: true,
  scope: 'Original pure cache-key declaration evaluated; no actual cached proxy reused' });

console.log(JSON.stringify({ status: 'passed-scoped-source-observations', observations,
  browserTabsOpened: 0, actualBrowsersStarted: 0, nativeMediaCommands: 0,
  productFeatureAccepted: false }, null, 2));
