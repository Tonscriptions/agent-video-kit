import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';
import { writeFileSync } from 'node:fs';
import assert from 'node:assert/strict';
const [source, adapted, output] = process.argv.slice(2);
const load = (root, file) => import(pathToFileURL(resolve(root, file)));
const { segmentLine, subtitleEnd } = await load(source, 'packages/openfilm/studio/server/subtitle-segments.mjs');
const { planRemove } = await load(adapted, 'packages/openfilm/studio/ui/src/lib/timeline-edit.ts');
const { applyOps } = await load(source, 'packages/openfilm/studio/server/ops.mjs');
const save = (name, value) => writeFileSync(resolve(output, name), JSON.stringify(value, null, 2) + '\n');
const line = {text: '这是一条本地广告，展示 Agent Video Kit，所有媒体在本机处理。', startMs: 0, endMs: 7000};
const pieces = segmentLine(line);
assert.ok(pieces.length >= 2);
for (let i = 0; i < pieces.length; i++) {
  assert.equal(pieces[i].text, line.text.slice(pieces[i].from, pieces[i].to));
  assert.ok(pieces[i].endMs > pieces[i].startMs);
  if (i) assert.ok(pieces[i].startMs >= pieces[i-1].endMs);
}
save('S01-subtitle-input.json', line);
save('S01-subtitle-output.json', {pieces, display_text: pieces.map(p => subtitleEnd(p.text)), timing_source: 'estimated from supplied line range, no ASR or TTS execution', checks: 'source spans, positive duration, no overlap'});
const clip = (id, a, b) => ({id, startMs:a*1000, endMs:b*1000, inMs:0, speed:1, sourceMs:60000});
const model = [
  {index:0, clips:[clip('intro',0,1), clip('remove',1,3), clip('outro',3,5)]},
  {index:1, role:'audio', clips:[clip('voice',3,5)]},
  {index:2, locked:true, role:'audio', clips:[clip('bed',0,5)]},
];
const film = {stage:{w:320,h:180}, tracks:model.map(t => ({...(t.locked?{locked:true}:{}), clips:t.clips.map(c => ({id:c.id, src:c.id+'.mp4', at:c.startMs/1000, time:[0,(c.endMs-c.startMs)/1000]}))}))};
const plan = planRemove(model, ['remove'], {ripple:true,sync:true});
const result = applyOps(structuredClone(film), plan.ops);
const actual = result.tracks.map(t => t.clips.map(c => [c.id,c.at??0,(c.at??0)+(c.time[1]-c.time[0])/(c.speed??1)]));
const expected = [[['intro',0,1],['outro',1,3]],[['voice',1,3]],[['bed',0,5]]];
assert.deepEqual(actual,expected);
assert.equal(plan.shortMs,0);
save('S02-ripple-input.json', {model,film,remove:['remove'],options:{ripple:true,sync:true}});
save('S02-ripple-output.json', {plan,result,actual,expected,checks:'exact expected intervals, synced voice moves by 2s, locked bed unchanged'});
console.log(JSON.stringify({subtitle_pieces:pieces.length,ripple_exact:true}));
