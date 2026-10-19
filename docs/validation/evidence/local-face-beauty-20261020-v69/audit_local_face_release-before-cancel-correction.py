"""Bind V69 actual evidence, publication bytes and terminal release gates."""
from __future__ import annotations
import argparse
import ast
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import urllib.parse
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/local-face-beauty-20261020-v69'


def read(path):return json.loads(path.read_bytes())
def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--candidate',action='store_true')
    args=parser.parse_args();output=args.output.resolve();assert not output.exists()
    inputs={};current=frozen();assert len(current)==212
    def bind(path):
        path=Path(path);assert path.is_file();inputs[path.relative_to(ROOT).as_posix()]=sha(path)
    def receipt(name):
        path=BASE/name;bind(path);return read(path)
    def frozen_success(value):
        assert value['frozen_equal'] and value['frozen_before']==value['frozen_after']==current
    dev=receipt('native-r5/verification.json');install=receipt('installed-r1/verification.json')
    actual=receipt('installed-r1/media/verification.json');controls=receipt('controls-r1/verification.json')
    for value in (dev,install,actual,controls):frozen_success(value)
    assert install['status']=='passed' and install['all_rgba_and_pcm_equal_development']
    assert install['packaged_files']==142 and install['isolated_cli_calls']==19 and install['isolated_module_calls']==1
    assert len(install['installed_product_files'])==142
    assert controls['status']=='passed_native_cpu_controls_no_new_model_forwards' and controls['model_forwards']==0
    assert len(controls['checks'])==20 and all(c['passed'] for c in controls['checks'])
    for item in controls['controls'].values():
        path=ROOT/item['path'];bind(path);assert sha(path)==item['sha256'] and path.stat().st_size==item['bytes']
        assert 0 < item['changed_rgb_pixels'] <= item['support_pixels'] < 512*512
    bind(ROOT/controls['contact']['path']);assert sha(ROOT/controls['contact']['path'])==controls['contact']['sha256']
    for folder,value in ((BASE/'native-r5',dev),(BASE/'installed-r1/media',actual)):
        assert value['status']=='passed_native_cli_contract_quality_separate' and len(value['calls'])==26
        assert len(value['checks'])==39 and all(c['passed'] for c in value['checks'])
        assert (value['detector_forwards'],value['landmark_forwards'])==(24,20)
        assert value['process_cleanup']['all_children_reaped'] and not value['process_cleanup']['active_after_cleanup']
        assert not value['quality_accepted'] and not value['full_capcut_parity'] and not value['mediapipe_executed']
        report=read(folder/'scan-report.json');bind(folder/'scan-report.json')
        response=report['response'];frames=response['frames']
        assert len(frames)==24 and response['detector_forwards']==24 and response['landmark_forwards']==20
        assert response['providers']==['CPUExecutionProvider'] and response['blocked_network_events']==[]
        assert not any(f['faces'] for f in frames[10:14])
        assert {f['face_id'] for r in frames[:10] for f in r['faces']}.isdisjoint({f['face_id'] for r in frames[14:] for f in r['faces']})
        for call in value['calls']:
            assert call['exit_code']==call['expected_exit']
            if call['stdout_file']:
                path=folder/call['stdout_file'];bind(path);assert sha(path)==call['stdout_sha256']
            path=folder/call['stderr_file'];bind(path);assert sha(path)==call['stderr_sha256']
        for name,code in (('precancel','CANCELLED'),('timeout','FACE_TIMEOUT'),('scan-cancel-owned-worker','CANCELLED')):
            call=next(c for c in value['calls'] if c['name']==name);error=read(folder/call['stdout_file'])['errors'][0]
            cleanup=error['diagnostics']['process_cleanup']
            assert error['code']==code and cleanup['all_children_reaped'] and not cleanup['active_after_cleanup']
            if name=='scan-cancel-owned-worker':
                seen=call['cancellation_trigger']['observed_owned_children']
                assert seen and set(seen)&set(cleanup['seen_pids']) and call['cancellation_trigger']['written']
        for name in ('retouch-neutral','retouch-controls','retouch-saved-recipe'):
            path=folder/(name+'-worker-report.json');bind(path);worker=read(path)['response']
            assert worker['model_forwards']==0 and worker['output_frames']==worker['source_clock_frames_checked']==24
            assert worker['alpha_mismatches']==worker['protected_pixel_mismatches']==0
            assert len(worker['output_rgba_sha256'])==24 and len(worker['audio_pcm'])==1
            assert all(p['source']==p['output'] for p in worker['audio_pcm'])
        for item in value['media']:
            path=ROOT/item['path'];bind(path);assert sha(path)==item['sha256'] and path.stat().st_size==item['bytes']
    for name in ('source-decode','neutral-decode','retouched-decode','recipe-replay-decode'):
        a=next(c for c in actual['calls'] if c['name']==name);b=next(c for c in dev['calls'] if c['name']==name)
        assert (a['stdout_sha256'],a['stdout_bytes'])==(b['stdout_sha256'],b['stdout_bytes'])
    for name in ('retouch-neutral','retouch-controls','retouch-saved-recipe'):
        assert read(BASE/'native-r5'/(name+'-worker-report.json'))['response']['audio_pcm']==read(BASE/'installed-r1/media'/(name+'-worker-report.json'))['response']['audio_pcm']
    for call in install['calls']:
        for label in ('stdout','stderr'):
            path=BASE/'installed-r1'/call[label];bind(path);assert sha(path)==call[label+'_sha256']
    media=receipt('media-inventory-r2.json');assert media['status']=='passed' and len(media['public_files'])==62 and len(media['final_media_probes'])==18
    for item in media['public_files']:
        path=ROOT/item['path'];bind(path);assert sha(path)==item['sha256'] and path.stat().st_size==item['bytes']
    assert media['generator_sha256']==sha(ROOT/'scripts/audit_local_face_media.py')
    static=receipt('static-review-r1.json');assert static['reviewed'] and len(static['files'])==4
    assert not static['continuous_playback_reviewed'] and not static['audio_listening_reviewed'] and not static['natural_dynamic_beauty_quality_accepted']
    for item in static['files']:assert sha(ROOT/item['path'])==item['sha256']
    provenance=receipt('upstream-provenance.json');assert provenance['commit']=='50c09741897010faad721a218b2bbe14ecad6251'
    assert len(provenance['models'])==2 and not provenance['models_redistributed_in_wheel']
    for item in provenance['saved_source_files']:
        path=ROOT/item['saved'];bind(path);assert sha(path)==item['sha256']
    for name in ('probe-r1-failure.json','probe-r2-failure.json','probe-r3-failure.json','probe-r4.json',
                 'native-r2/verification.json','native-r3/verification.json','native-r3/visual-export-failure.json',
                 'native-r4/verification.json','media-audit-r1-failure.json','preserved-worker-reports-r1.json'):
        receipt(name)
    skills=receipt('skills-r1.json');mapping=read(ROOT/'video-cut-install-manifest.json');bind(ROOT/'video-cut-install-manifest.json')
    assert skills['skill_count']==mapping['skill_count']==17 and skills['local_links_checked']==256
    assert mapping['current_audit']['record_sha256']==sha(BASE/'skills-r1.json')
    assert mapping['current_audit']['candidate']==args.candidate
    for row in skills['results']:
        path=ROOT/'skills'/row['skill']/'SKILL.md';bind(path);assert sha(path)==row['sha256']
        assert row['installed_directory_resolves_to_repo'] and row['validator_exit_code']==0
        registered=next(r for r in mapping['skills'] if r['name']==row['skill']);assert registered['skill_md_sha256']==row['sha256'][7:]
    full=read(BASE/'full-r1.json')
    if not args.candidate:
        assert full['methods']==1536 and full['exit_code']==0 and full['terminal_ok'] and full['skipped']==0
        frozen_success(full);bind(BASE/'full-r1.json');bind(BASE/'full-r1.log');assert sha(BASE/'full-r1.log')==full['log_sha256']
        tree=ast.parse((ROOT/'product/tests/test_local_face.py').read_text(encoding='utf8'))
        methods=[n.name for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')];assert len(methods)==16
        log=(BASE/'full-r1.log').read_text(encoding='utf8');assert all(re.search(r'^'+name+r' .*\.\.\. ok$',log,re.M) for name in methods)
    documents=[ROOT/'README.md',ROOT/'docs/README.md',ROOT/'docs/validation/离线人脸锚点与局部修饰实测_2026-10-20.md',
               ROOT/'docs/specs/离线人脸锚点与局部修饰契约_v0.1_2026-10-20.md',ROOT/'docs/third-party/OpenSeeFace模型与原生SDK取舍_2026-10-20.md']
    for path in documents:
        bind(path);text=path.read_text(encoding='utf8')
        if path.name=='README.md':
            text=text.split('<!-- V69-CURRENT -->',1)[1].split('<!-- /V69-CURRENT -->',1)[0]
        for raw in re.findall(r'!?\[[^\]]*\]\(([^\s)]+)\)',text):
            value=urllib.parse.unquote(raw.split('#',1)[0])
            if value and not re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:',value):assert (path.parent/value).exists(),(path,value)
    for name in ('probe_openseeface_native','smoke_local_face','verify_local_face_install','probe_local_face_controls',
                 'audit_local_face_media','sync_local_face_documents','audit_local_face_release','finalize_local_face'):
        bind(ROOT/'scripts'/(name+'.py'))
    value={'status':'candidate_checks_passed_full_pending' if args.candidate else 'passed','checked_at_utc':datetime.now(timezone.utc).isoformat(),
           'frozen_inputs':current,'bound_files':inputs,'full_methods':None if args.candidate else full['methods'],
           'native_cli_calls':16,'installed_cli_calls':19,'installed_module_calls':1,'packaged_files':142,'skills':17,'skill_links':256,
           'quality_accepted':False,'full_capcut_parity':False,'force_push':False}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({k:value[k] for k in ('status','full_methods','packaged_files','skills','skill_links')}))


if __name__=='__main__':main()
