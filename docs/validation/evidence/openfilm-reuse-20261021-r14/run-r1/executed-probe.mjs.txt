// Research observations for OpenFilm 53156ac5; not a product acceptance suite.
import assert from 'node:assert/strict';
import { nleFps, nleRate, frameSpan, planNleTimeline, xmemlDocument } from './packages/openfilm/studio/server/nle.mjs';
import { fcpxmlDocument } from './packages/openfilm/studio/server/fcpxml.mjs';
import { fitImages } from './apps/desktop/src/pi-config.mjs';

const facts = { w: 320, h: 180, fps: 25, duration: 10, hasVideo: true, hasAudio: false };
const picture = { id: 'shot', kind: 'video', src: 'source.mov', path: 'E:/review/source.mov', at: 0, end: 2,
  from: 1, speed: 1, track: 0, hidden: false, facts };
const options = { title: 'Local reuse review', fps: 30, audio: 'clips', media: 'link', mediaDir: 'E:/review/media' };
const plan = (patch = {}) => planNleTimeline({ stage: { w: 320, h: 180 }, duration: 2,
  pictures: [{ ...picture, ...patch }], sounds: [] }, options);
const job = (value) => value.files.find((f) => f.id === value.video[0].clips[0].fileId).job.kind;
const rows = [];
const observe = (id, value, implication) => rows.push({ id, value, implication });

const fps = [48, 90, 120].map((input) => ({ input, selected: nleFps(input) }));
assert.deepEqual(fps.map((x) => x.selected), [50, 60, 60]);
observe('OF14-B01', fps, 'Nearest-rate helper changes unsupported rates; a host adapter must reject or explicitly approve conversion.');
const span = frameSpan(0, 0.001, nleRate(30));
observe('OF14-B02', span, 'Subframe requests follow the upstream frame quantization; do not silently substitute for integer author ticks.');

const ordinary = plan();
assert.equal(job(ordinary), 'link');
observe('OF14-B03', { job: job(ordinary), sourceInFrames: ordinary.video[0].clips[0].in,
  timelineRate: ordinary.rate, sourceFactsRate: ordinary.files[0].video.fps },
  'Mixed-rate source/timebase semantics require actual target-editor open and re-render checks, not XML string assertions.');

for (const [id, patch] of [['speed', { speed: 1.5 }], ['rotation', { box: { r: 12 } }],
  ['css-look', { styled: true }], ['fade', { faded: true }], ['html', { kind: 'page', facts: null }]]) {
  const value = plan(patch);
  assert.equal(job(value), 'render');
  observe('OF14-B04-' + id, { job: job(value), file: value.files[0] },
    'A baked render job preserves an intended look only after execution; the original effect is not retained as editable NLE parameters.');
}

const hidden = plan({ hidden: true });
assert.equal(hidden.video[0].clips[0].enabled, false);
observe('OF14-B05', { clipsRetained: hidden.video[0].clips.length, enabled: hidden.video[0].clips[0].enabled },
  'Disabled clips can remain editable rather than being silently removed.');

const unknown = plan({ effects: [{ type: 'rgb_curves', points: '0/0 1/0.5' }] });
assert.equal(job(unknown), 'link');
observe('OF14-B06', { job: job(unknown), effectPreserved: JSON.stringify(unknown).includes('rgb_curves') },
  'Agent Project effects are outside this typed input contract. The adapter must classify or bake them; extra properties alone do not preserve effects.');

const fcpxml = fcpxmlDocument(ordinary);
const xmeml = xmemlDocument(ordinary);
assert.match(fcpxml, /colorSpace="1-1-1 \(Rec\. 709\)"/);
observe('OF14-B07', { rec709Hardcoded: true, fcpxmlBytes: Buffer.byteLength(fcpxml), xmemlBytes: Buffer.byteLength(xmeml),
  fcpxmlFormat: fcpxml.match(/<format id="format-[^>]+>/)?.[0], xmemlFileRate: xmeml.match(/<file id=[\s\S]*?<rate>[\s\S]*?<\/rate>/)?.[0] },
  'The serializer has no verified HDR/color-management parity. FCPXML and legacy xmeml are distinct formats.');

const messages = [
  { role: 'assistant', content: [{ type: 'toolCall', id: 'one', name: 'read', arguments: { path: 'frame-one.png' } }] },
  { role: 'toolResult', toolCallId: 'one', toolName: 'read', content: [{ type: 'image', data: 'A'.repeat(8), mimeType: 'image/png' }] },
  { role: 'user', content: 'x'.repeat(20000) },
];
const before = JSON.stringify(messages);
const fitted = fitImages(messages, 4);
assert.equal(JSON.stringify(messages), before);
assert.equal(fitted.kept, 0);
assert.ok(JSON.stringify(fitted.messages).includes('x'.repeat(20000)));
observe('OF14-B08', { keptImageBase64: fitted.kept, fullSerializedRequestBytes: Buffer.byteLength(JSON.stringify(fitted.messages)), originalUnchanged: true },
  'The image budget does not bound full request bytes, tokens, text, or retained conversation memory. Add independent host limits.');

console.log(JSON.stringify({ status: 'observed', observations: rows, generatedProductMedia: false,
  downstreamEditorRun: false, actualModelOrNetworkCalls: 0 }, null, 2));
