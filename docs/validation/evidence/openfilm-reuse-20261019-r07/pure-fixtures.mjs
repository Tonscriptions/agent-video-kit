import assert from 'node:assert/strict';
import { mkdirSync, readFileSync, statSync, utimesSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';
const [source, scratch] = process.argv.slice(2);
const load = (name) => import(pathToFileURL(join(source, name)).href);
const rows = await load('studio/server/track-layout.mjs');
const enc = await load('src/encoders.mjs');
const doctor = await load('src/doctor.mjs');
const problems = await load('src/problems.mjs');
const diag = await load('studio/server/diagnostics.mjs');
const cover = await load('studio/server/cover.mjs');
const cache = await load('studio/server/preview-cache.mjs');
const passed = [];
const check = (id, fn) => { fn(); passed.push(id); };
check('F01-row-labels', () => assert.deepEqual(rows.rowBadges(['mg','video','mg','audio','video','audio']), ['P2','V2','P1','A1','V1','A2']));
check('F02-video-audio-only', () => assert.equal(rows.trackKind({clips:[{src:'a.mp4',sound:true}]}), 'audio'));
check('F03-one-ms-tolerance-and-immutable-input', () => {
  const blocks = [{id:'a',startMs:0,endMs:1000},{id:'b',startMs:999,endMs:2000}];
  const before = structuredClone(blocks);
  assert.deepEqual(rows.layerBlocks(blocks).map(r => r.map(c => c.id)), [['a','b']]);
  assert.deepEqual(blocks, before);
  assert.equal(rows.layerBlocks([blocks[0], {...blocks[1], startMs:998}]).length, 2);
});
check('F04-encoder-options-only', () => {
  const a = enc.hardwareOptions('hevc_nvenc', 8000000, {gop:59.94});
  assert.equal(a[a.indexOf('-g')+1], '60');
  assert.equal(a[a.indexOf('-tag:v')+1], 'hvc1');
  assert.equal(enc.proresOptions('prores_ks', true).pix, 'format=yuva444p10le');
});
check('F05-decoder-policy-only', () => {
  assert.deepEqual(enc.decoderCandidates('win32'), [['-hwaccel','d3d11va'],['-hwaccel','cuda']]);
  assert.deepEqual(enc.decoderCandidates('linux', []), [['-hwaccel','cuda']]);
});
check('F06-color-metadata-only', () => {
  assert.deepEqual(enc.h264ColorTags({color_primaries:'bt709',color_transfer:'iec61966-2-1',color_space:'bt709',color_range:'tv'}),
    ['-bsf:v','h264_metadata=colour_primaries=1:transfer_characteristics=13:matrix_coefficients=1:video_full_range_flag=0']);
  assert.deepEqual(enc.h264ColorTags({color_transfer:'constructor'}), []);
});
check('F07-agent-names-without-env-values', () => {
  const a = doctor.agentHints({CODEX_SANDBOX:'fixture-private-value', PATH:'x'});
  assert.deepEqual(a.agents, ['Codex']);
  assert.ok(!JSON.stringify(a).includes('fixture-private-value'));
});
check('F08-renderer-and-report-helpers-only', () => {
  assert.equal(doctor.softwareRenderer('ANGLE SwiftShader'), true);
  assert.equal(doctor.softwareRenderer('NVIDIA RTX'), false);
  assert.match(doctor.formatReport([{label:'ffmpeg',text:'missing',problem:'configure local path'}]), /configure local path/);
});
check('F09-fixture-redaction', () => {
  assert.ok(!problems.redact('Bearer abcdefghijklmnop ana@example.com').includes('abcdefghijklmnop'));
  assert.ok(!problems.redact('Bearer abcdefghijklmnop ana@example.com').includes('ana@example.com'));
});
check('F10-turn-payload-omission', () => {
  const raw = JSON.stringify({kind:'prompt',t:1,agent:'fixture',text:'fixture-private-words'})+'\n'+
    JSON.stringify({kind:'update',t:2,update:{sessionUpdate:'tool_call',toolCallId:'a',name:'exec_command',rawInput:{cmd:'fixture-private-command'}}});
  const out = diag.turnLogForFile(raw, false);
  assert.ok(!out.includes('fixture-private-'));
  assert.ok(out.includes('exec_command'));
});
check('F11-cover-header-recognition-not-decoding', () => {
  assert.equal(cover.pictureType(Buffer.from('89504e470d0a1a0a', 'hex')), 'png');
  assert.equal(cover.pictureType(Buffer.from('plain text')), null);
});
mkdirSync(scratch, {recursive:true});
writeFileSync(join(scratch, 'film.html'), '<section><iframe src="a.html"></iframe></section>');
writeFileSync(join(scratch, 'a.html'), '<body>AAAA</body>');
const key = () => cache.previewKey(scratch, 0, 1, 30, 540);
check('F12-preview-key-parameters', () => {
  assert.equal(key(), key());
  assert.notEqual(key(), cache.previewKey(scratch, 0, 2, 30, 540));
  assert.notEqual(key(), cache.previewKey(scratch, 0, 1, 30, 720));
});
check('F13-normal-file-change-invalidates', () => {
  const before = key();
  const at = statSync(join(scratch, 'a.html')).mtimeMs;
  writeFileSync(join(scratch, 'a.html'), '<body>LONGER CONTENT</body>');
  utimesSync(join(scratch, 'a.html'), new Date(at+2000), new Date(at+2000));
  assert.notEqual(key(), before);
});
// A negative suitability check, deliberately retained separately from passing cases.
const p = join(scratch, 'a.html');
const fixedTime = new Date(1700000000000);
writeFileSync(p, '<body>AAAA</body>'); utimesSync(p, fixedTime, fixedTime);
const hash = () => createHash('sha256').update(readFileSync(p)).digest('hex');
const beforeKey = key(), beforeHash = hash();
writeFileSync(p, '<body>BBBB</body>'); utimesSync(p, fixedTime, fixedTime);
const afterKey = key(), afterHash = hash();
assert.notEqual(beforeHash, afterHash);
assert.equal(beforeKey, afterKey);
console.log(JSON.stringify({status:'completed_scoped_pure_fixtures',passed,passed_count:passed.length,
  negative_suitability_checks:[{id:'N01-same-size-restored-mtime',expected_for_avk:'content change invalidates cache',
    actual:'same key despite different SHA-256',accepted_for_direct_avk_reuse:false,beforeKey,afterKey,beforeHash,afterHash}],
  actual_media_rendered:false,hardware_probe_executed:false,doctor_executed:false}));
