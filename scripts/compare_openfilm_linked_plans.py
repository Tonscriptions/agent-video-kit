"""Compare native whole-clip planning with an already acquired OpenFilm tree.

No packages are installed. Node is used only as a fixed upstream test oracle,
not by the product. Supply the original tree and the previously audited copy
whose only change is removal of timecode.ts's React Hook.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'product/src'))
from ai_ad_editor.edit_planner import build_edit_plan, SOURCE


def sha(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


def freeze(path):
    return {p.relative_to(path).as_posix(): sha(p) for p in sorted(path.rglob('*')) if p.is_file()}


def cases():
    out = []
    def clip(cid, a, b, **extra):
        return {'id': cid, 'asset_id': 'source', 'timeline_start_tick': a, 'duration_tick': b-a,
                'source_in_tick': 0, 'source_out_tick': b-a, **extra}
    for family in ('remove_local', 'remove_sync', 'remove_linkage', 'close_sync', 'close_linkage'):
        for seed in range(12):
            rng = random.Random(seed+5107)
            shots = []
            at = rng.randrange(0, 4)*1000
            for i in range(6):
                span = rng.randrange(2, 5)*1000
                shots.append(clip(f'shot_{i}', at, at+span))
                at += span + (rng.randrange(1, 4)*1000 if family.startswith('close') else 0)
            riders = [clip(f'rider_{i}', c['timeline_start_tick']+250,
                           c['timeline_start_tick']+c['duration_tick']-250) for i, c in enumerate(shots)]
            voice = [clip(f'voice_{i}', c['timeline_start_tick']+500,
                          c['timeline_start_tick']+c['duration_tick']) for i, c in enumerate(shots)]
            tracks = [
                {'id': 'main', 'kind': 'video', 'order': 0, 'clips': shots},
                {'id': 'titles', 'kind': 'subtitle', 'order': 1, 'clips': riders},
                {'id': 'voice', 'kind': 'audio', 'order': 2, 'clips': voice},
                {'id': 'music', 'kind': 'audio', 'order': 3, 'clips': [clip('bed', 0, at)]},
                {'id': 'locked', 'kind': 'audio', 'order': 4, 'locked': True, 'clips': [clip('fixed', at, at+1000)]},
            ]
            p = {'project': {'id': 'reference'}, 'settings': {'timebase': {'ticks_per_second': 1000, 'display_fps': {'num': 30, 'den': 1}}},
                 'assets': [], 'sequences': [{'id': 'seq', 'name': 'seq', 'duration_tick': at+1000, 'tracks': tracks}]}
            options = {'sync': family.endswith('sync'), 'linkage': family.endswith('linkage')}
            request = ({'action': 'close_gaps', 'track_id': 'main', 'options': options} if family.startswith('close') else
                       {'action': 'remove', 'clip_ids': [f'shot_{rng.randrange(1, 5)}'], 'options': {**options, 'ripple': True}})
            out.append({'id': f'{family}-{seed:02}', 'project': p, 'request': request})
    for family in ('link', 'unlink'):
        for seed in range(10):
            p = copy.deepcopy(out[seed]['project'])
            if family == 'unlink':
                p['sequences'][0]['tracks'][0]['clips'][0]['link_id'] = 'g'
                p['sequences'][0]['tracks'][2]['clips'][0]['link_id'] = 'g'
            request = {'action': family, 'clip_ids': ['shot_0', 'voice_0'] if family == 'link' else ['shot_0']}
            out.append({'id': f'{family}-{seed:02}', 'project': p, 'request': request})
    return out


WORKER = r'''import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';
import { readFileSync } from 'node:fs';
const [tree, input] = process.argv.slice(2);
const p = await import(pathToFileURL(resolve(tree, 'packages/openfilm/studio/ui/src/lib/timeline-edit.ts')));
const { applyOps } = await import(pathToFileURL(resolve(tree, 'packages/openfilm/studio/server/ops.mjs')));
const rows = JSON.parse(readFileSync(input, 'utf8'));
const outputs = rows.map(({id,project,request}) => {
  const source = project.sequences[0].tracks;
  const pictures = source.filter(t => t.kind !== 'audio').sort((a,b) => b.order-a.order);
  const audio = source.filter(t => t.kind === 'audio').sort((a,b) => a.order-b.order);
  const ordered = [...pictures,...audio];
  const model = ordered.map((t,index) => ({index,role:t.kind==='audio'?'audio':t.kind==='subtitle'?'mg':'video',
    locked:!!t.locked,clips:t.clips.map(c => ({id:c.id,startMs:c.timeline_start_tick,
      endMs:c.timeline_start_tick+c.duration_tick,inMs:c.source_in_tick,speed:c.speed??1,sourceMs:1e9,
      ...(c.link_id?{link:c.link_id}:{})}))}));
  const film = {stage:{w:160,h:90},tracks:ordered.map(t => ({nativeTrackId:t.id,locked:!!t.locked,
    clips:t.clips.map(c => ({id:c.id,src:c.id+'.mp4',at:c.timeline_start_tick/1000,
      time:[c.source_in_tick/1000,c.source_out_tick/1000],...(c.link_id?{attrs:{'data-link':c.link_id}}:{})}))}))};
  const opts = request.options??{};
  const ids = request.clip_ids??[];
  const track = model.find(t => ordered[t.index].id===(request.track_id??'main')).index;
  let plan;
  if(request.action==='remove') plan = p.planRemove(model,p.linkedIds(model,ids),{...opts,ripple:opts.ripple??false});
  else if(request.action==='close_gaps') plan=p.planCloseTrackGaps(model,track,opts);
  else if(request.action==='link') plan={ops:p.planLink(model,ids),shortMs:0};
  else if(request.action==='unlink') plan={ops:p.planUnlink(model,ids),shortMs:0};
  else throw new Error('Unsupported oracle action');
  const result = applyOps(film,plan.ops);
  const positions={};const links=new Map();
  for(const t of result.tracks)for(const c of t.clips){
    const a=Math.round((c.at??0)*1000);const d=Math.round((c.time[1]-c.time[0])/(c.speed??1)*1000);
    positions[c.id]=[t.nativeTrackId??null,a,a+d];
    const link=c.attrs?.['data-link'];
    if(link){const group=links.get(link)??[];group.push(c.id);links.set(link,group);}
  }
  const groups=[...links.values()].map(g=>g.sort()).sort((a,b)=>JSON.stringify(a).localeCompare(JSON.stringify(b)));
  return {id,positions,groups,short_tick:Math.round(plan.shortMs),ops:plan.ops};
});
process.stdout.write(JSON.stringify(outputs));
'''


def native(case):
    candidate, plan = build_edit_plan(case['project'], 'seq', case['request'])
    positions = {}
    links = {}
    for t in candidate['sequences'][0]['tracks']:
        for c in t['clips']:
            a = c['timeline_start_tick']
            positions[c['id']] = [t['id'], a, a+c['duration_tick']]
            if c.get('link_id'):
                links.setdefault(c['link_id'], []).append(c['id'])
    groups = sorted([sorted(ids) for ids in links.values()])
    return {'id': case['id'], 'positions': positions, 'groups': groups, 'short_tick': plan['short_tick']}, plan


def run(source, adapted, output, work, node):
    if output.exists() or work.exists():
        raise ValueError('Use fresh output and work directories')
    expected = json.loads((ROOT/'docs/validation/evidence/openfilm-reuse-20261017/verification.json').read_text(encoding='utf-8'))
    before = freeze(source)
    assert before == expected['source_sha256']
    adapted_before = freeze(adapted)
    changed = [p for p in before if before[p] != adapted_before.get(p)]
    assert set(before) == set(adapted_before) and changed == expected['adapted_changed_files']
    assert adapted_before[changed[0]] == expected['adapted_hook_sha256']
    output.mkdir(parents=True); work.mkdir(parents=True)
    fixture = cases(); save(output/'inputs.json', fixture)
    worker = work/'upstream-plans.mjs'; worker.write_text(WORKER, encoding='utf-8', newline='\n')
    shutil.copyfile(worker, output/'upstream-plans.mjs')
    env = os.environ.copy()
    for key in ('NODE_OPTIONS', 'NODE_PATH', 'NODE_COMPILE_CACHE'):
        env.pop(key, None)
    for key in ('TEMP', 'TMP', 'TMPDIR'):
        env[key] = str(work)
    version = subprocess.check_output([node, '--version'], env=env).decode().strip()
    command = [node, '--experimental-strip-types', str(worker), str(adapted), str(output/'inputs.json')]
    result = subprocess.run(command, cwd=work, env=env, capture_output=True, timeout=180)
    (output/'upstream.stdout.log').write_bytes(result.stdout)
    (output/'upstream.stderr.log').write_bytes(result.stderr)
    assert result.returncode == 0, result.stderr.decode('utf-8', 'replace')
    upstream = json.loads(result.stdout)
    ours = []; plans = []; failures = []
    for case, reference in zip(fixture, upstream, strict=True):
        actual, plan = native(case); ours.append(actual); plans.append(plan)
        for key in ('id', 'positions', 'groups', 'short_tick'):
            if actual[key] != reference[key]:
                failures.append({'case': case['id'], 'field': key, 'actual': actual[key], 'upstream': reference[key]})
    save(output/'native-results.json', ours); save(output/'native-plans.json', plans)
    assert freeze(source) == before and freeze(adapted) == adapted_before
    record = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'source': SOURCE, 'node_version': version,
              'case_count': len(fixture), 'matched_cases': len(fixture)-len({f['case'] for f in failures}), 'failures': failures,
              'command': command, 'exit_code': result.returncode, 'source_files_verified': len(before), 'source_unchanged': True,
              'adapted_only_change': changed, 'native_product_module_sha256': sha(ROOT/'product/src/ai_ad_editor/edit_planner.py'),
              'script_sha256': sha(Path(__file__)), 'worker_sha256': sha(worker),
              'scope': '80 selected whole-clip data comparisons, not upstream full tests or product regression or encoded media',
              'deliberate_differences_not_compared': ['zero-tolerance-integer-ticks-versus-1ms-touch', 'locked-link-member-atomic-rejection',
                    'per-track-sync-opt-out', 'single-gap-no-single-track-fallback', 'merge-complete-existing-link-groups',
                    'processing-compatible-lanes-and-audio-effect-bus-rejection', 'native-file-subtitle-offsets-and-reference-rebinding'],
              'browser_or_gui_opened': False, 'installed_dependencies': 0, 'provider_calls': 0,
              'files': {p.name: {'sha256': sha(p), 'bytes': p.stat().st_size} for p in sorted(output.iterdir()) if p.is_file()}}
    save(output/'verification.json', record)
    print(json.dumps({k: record[k] for k in ('case_count', 'matched_cases', 'failures', 'source_files_verified')}, ensure_ascii=False))
    assert not failures


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'adapted', 'output', 'work'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--node', default=shutil.which('node'))
    args = parser.parse_args()
    run(args.source.resolve(), args.adapted.resolve(), args.output.resolve(), args.work.resolve(), args.node)
