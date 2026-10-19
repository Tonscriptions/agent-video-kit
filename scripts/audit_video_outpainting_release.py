"""Bind actual local outpainting, frozen tests, offline bytes and documentation."""
from __future__ import annotations
import argparse
import ast
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import urllib.parse
import zipfile
from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'docs/validation/evidence/video-outpainting-20261019-v66'
REPORT = '本地视频扩图与原画面保护实测_2026-10-19.md'
CONTRACT = '本地视频扩图与原画面保护契约_v0.1_2026-10-19.md'
NATIVE_CONTRACT = 'VACE本地权重读取与原生访问冲突约束_v0.1_2026-10-20.md'


def sha(p): return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_bytes())


def main():
    import numpy as np
    from PIL import Image
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    output=parser.parse_args().output.resolve(); assert not output.exists()
    current=frozen(); files={}; counts={}; media=[]

    def bind(p):
        assert p.is_file(),str(p)
        files[p.relative_to(ROOT).as_posix()]={'sha256':sha(p),'bytes':p.stat().st_size}

    def same(v): return v['frozen_equal'] and v['frozen_before']==v['frozen_after']==current

    def calls(folder, rows, expected_failures=None):
        for row in rows:
            expected=(expected_failures or {}).get(row['name'],row.get('expected_exit',0))
            assert row['exit_code']==expected,row['name']
            for key in ('stdout','stderr'):
                p=folder/row[key]; assert sha(p)==row[key+'_sha256']; bind(p)
            if row.get('stdout_encoding')=='gzip-raw':
                raw=gzip.decompress((folder/row['stdout']).read_bytes())
                assert 'sha256:'+hashlib.sha256(raw).hexdigest()==row['decoded_stdout_sha256']
                assert len(raw)==row['decoded_stdout_bytes']

    for label,n in [('full-r2',1462),('subset-r2',24),('vace-reader-r1',41)]:
        v=read(BASE/(label+'.json'))
        assert same(v) and v['exit_code']==0 and v['terminal_ok'] and v['methods']==n and v['skipped']==0
        assert sha(BASE/(label+'.log'))==v['log_sha256']
        bind(BASE/(label+'.json'));bind(BASE/(label+'.log'))
    assert len(current)==200
    for case in ('lama-direct-r3','lama-harmonic-r2','vace-harmonic-r4','installed-r2/media'):
        folder=BASE/case; v=read(folder/'verification.json')
        assert same(v) and v['status']=='passed_execution_quality_separate'
        assert v['frames']==8 and v['stereo_sample_frames']==48000 and v['model_calls']>0
        assert all(c['passed'] for c in v['checks'])
        assert sha(folder/'executed-generator.py')==v['generator_sha256']
        assert sha(folder/'executed-generator.py')==sha(ROOT/'scripts/smoke_video_outpainting.py')
        calls(folder,v['calls']);bind(folder/'verification.json');bind(folder/'executed-generator.py')
        result=read(folder/'actual-result.json'); worker=result['outpainting']['worker']
        assert worker['model_loaded'] and worker['network']=='disabled' and not worker['blocked_network_events']
        assert result['outpainting']['rgba_roundtrip_verified'];bind(folder/'actual-result.json')
        if v['engine']=='vace':
            sys.path.insert(0,str(ROOT/'product/src'))
            from ai_ad_editor.cuda_admission import validate_execution
            from ai_ad_editor.vace_model import validate_weight_reads
            validate_weight_reads(worker['model_execution'].get('local_weight_reads'))
            registration=next(c for c in v['calls'] if c['name']=='model-register')
            adapter=read(folder/registration['stdout'])['data']['adapter']
            validate_execution(worker['model_execution'],
                text_gpu_budget_mib=adapter['settings']['text_gpu_budget_mib'],
                model_calls=worker['metrics']['model_calls'])
            assert worker['model_execution']['window_input_shapes']==[[5,160,256],[5,160,256]]
            generation=result['asset']['source']['outpainting']['generation']
            assert generation['inference_steps']==30 and generation['window_frames']==5 and generation['window_overlap']==2
        evidence=v['model_evidence']
        assert not evidence['license_status_changed']
        old_proof=folder/'original-model-evidence.json';local_proof=folder/'local-model-evidence.json'
        assert sha(old_proof)==evidence['original_sha256'] and sha(local_proof)==evidence['local_sha256']
        original=read(old_proof);portable=read(local_proof)
        def preserved(old,new):
            if isinstance(old,dict):
                assert set(new)==set(old)
                for k in old:preserved(old[k],new[k])
            elif isinstance(old,list):
                assert len(old)==len(new)
                for a,b in zip(old,new,strict=True):preserved(a,b)
            elif isinstance(old,str) and urllib.parse.urlsplit(old).scheme in {'http','https'}:
                assert new=={'historical_reference_sha256':'sha256:'+hashlib.sha256(old.encode('utf8')).hexdigest(),
                             'role':'retrieval-history-only'}
            else:assert old==new
        origin=portable.pop('original_evidence')
        assert origin['sha256']==sha(old_proof) and Path(origin['path'])==old_proof
        preserved(original,portable);bind(old_proof);bind(local_proof)
        spec=result['outpainting']['outpainting']; x,y=spec['offset_x'],spec['offset_y']
        raw={}
        for name,shape in [('source',(8,128,192,4)),('expanded',(8,160,256,4))]:
            entry=next(c for c in v['calls'] if c['name']=='decode-'+name)
            raw[name]=np.frombuffer(gzip.decompress((folder/entry['stdout']).read_bytes()),np.uint8).reshape(shape)
        assert np.array_equal(raw['expanded'][:,y:y+128,x:x+192],raw['source'])
        selected=np.ones((160,256),bool);selected[y:y+128,x:x+192]=False
        assert np.all(raw['expanded'][:,selected,3]==255)
        public=(ROOT/next(k for k in v['files'] if k.endswith('/expanded.mov'))).parent
        for name,entry in v['files'].items():
            p=ROOT/name;assert sha(p)==entry['sha256'] and p.stat().st_size==entry['bytes'];bind(p)
        truth=np.load(public/'ground-truth.npz',allow_pickle=False)['frames']
        error=raw['expanded'][...,:3].astype(np.float64)-truth[...,:3].astype(np.float64)
        mse=float(np.square(error[:,selected]).mean()); psnr=100. if mse==0 else float(10*np.log10(255**2/mse))
        assert abs(psnr-v['quality']['psnr_db'])<1e-10 and v['quality']['passed']==(psnr>=30.)
        assert v['quality']['predeclared_gate_db']==30. and not v['quality']['natural_quality_accepted']
        with Image.open(public/'comparison.gif') as gif:
            durations=[]
            for frame in range(gif.n_frames):gif.seek(frame);durations.append(gif.info['duration'])
            assert gif.size==(768,184) and len(durations)==8 and sum(durations)==1000
        provenance=read(public/'provenance.json')
        assert provenance['source_license']=='CC0-1.0' and provenance['gif_durations_ms']==[120,130]*4
        source_info=read(public/'source-evidence.json')
        assert source_info['generator_sha256']==provenance['source_generator_sha256']==sha(BASE/'lama-direct-r1/executed-generator.py')
        for name,entry in provenance['files'].items():assert sha(public/name)==entry['sha256']
        assert not v['continuous_playback_reviewed'] and not v['audio_listening_reviewed']
        media.append(v)
    installed=read(BASE/'installed-r2/verification.json')
    assert same(installed) and installed['status']=='passed' and installed['packaged_files']==133
    assert installed['isolated_cli_calls']==media[3]['cli_calls']+2 and not installed['vace_installed_inference_tested']
    assert all(c['equal'] for c in installed['comparisons']);calls(BASE/'installed-r2',installed['calls'])
    bind(BASE/'installed-r2/verification.json');bind(BASE/'installed-r2/executed-install-check.py')
    assert sha(BASE/'installed-r2/executed-install-check.py')==sha(ROOT/'scripts/verify_video_outpainting_install.py')
    release=ROOT/'docs/assets/video-outpainting-20261019-v66-installed-r2/release'
    for name,digest in installed['release'].items():assert sha(release/name)==digest;bind(release/name)
    with zipfile.ZipFile(release/'agent-video-kit-cp313-win_amd64.zip') as archive:
        manifest=read(release/'manifest.json');assert archive.read('manifest.json')==(release/'manifest.json').read_bytes()
        assert len(manifest['wheels'])==7
        for entry in manifest['files']:
            payload=archive.read(entry['path'])
            assert len(payload)==entry['bytes'] and 'sha256:'+hashlib.sha256(payload).hexdigest()==entry['sha256']
        own=next(w for w in manifest['wheels'] if w['name']=='ai-ad-editor')
        with zipfile.ZipFile(io.BytesIO(archive.read(own['path']))) as wheel:
            names=[n for n in wheel.namelist() if n.startswith('ai_ad_editor/') and not n.endswith('/')]
            assert len(names)==133
            for name in names:assert wheel.read(name)==(ROOT/'product/src'/name).read_bytes()
    skills=read(BASE/'skills-r2.json'); mapping=read(ROOT/'video-cut-install-manifest.json')
    assert skills['skill_count']==mapping['skill_count']==17 and skills['local_links_checked']==238
    for row in skills['results']:
        p=ROOT/'skills'/row['skill']/'SKILL.md';entry=next(e for e in mapping['skills'] if e['name']==row['skill'])
        assert sha(p)==row['sha256']=='sha256:'+entry['skill_md_sha256'] and row['validator_exit_code']==0;bind(p)
    bind(BASE/'skills-r2.json');bind(ROOT/'video-cut-install-manifest.json')
    review=read(BASE/'static-review.json')
    assert review['reviewed_static_frames']==16 and not review['continuous_playback'] and not review['audio_listened'];bind(BASE/'static-review.json')
    assert {item['case'] for item in review['items']}=={'lama-direct-r3','lama-harmonic-r2','vace-harmonic-r4','installed-r2/media'}
    assert sum(len(item['source_frames']) for item in review['items'])==16
    for item in review['items']:
        assert item['source_frames']==[0,3,4,7] and sha(ROOT/item['path'])==item['sha256']
        bind(ROOT/item['path'])
    paths=['README.md','docs/README.md','docs/validation/'+REPORT,'docs/specs/'+CONTRACT,'docs/specs/'+NATIVE_CONTRACT,
        'docs/specs/本地模型管道诊断与有界留证契约_v0.1_2026-10-20.md',
        'docs/OpenFilm诊断模块复用与原生模型故障后续项_2026-10-20.md','docs/OpenFilm当前复用决策_2026-10-18.md',
        'docs/构建进度总表_2026-10-16.md','docs/产品需求与开发路线基线_2026-10-12.md',
        'docs/产品实现入口与P0使用说明_v0.1_2026-10-13.md','docs/specs/AgentCLI契约_v0.1_2026-10-13.md',
        'docs/validation/README功能核验与实测演示_2026-10-16.md','docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md',
        'docs/validation/VACE物理显卡准入与真实交付实测_2026-10-19.md',
        'docs/validation/VACE共享显存真实重试与准入拒绝_2026-10-19.md']
    links=0
    for relative in paths:
        p=ROOT/relative; text=p.read_text(encoding='utf8')
        for raw in re.findall(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^\"]*")?\)',text):
            target=raw.strip('<>').split('#',1)[0]
            if not target or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',target):continue
            q=(p.parent/urllib.parse.unquote(target)).resolve();assert q.exists() or q==output,(p,target);links+=1
        bind(p)
    for p in ROOT.glob('scripts/*video_outpainting*.py'):ast.parse(p.read_text(encoding='utf8'));bind(p)
    diagnostic=ROOT/'scripts/probe_safetensors_window_read.py';ast.parse(diagnostic.read_text(encoding='utf8'));bind(diagnostic)
    integration_script=ROOT/'scripts/integrate_vace_pread.py';ast.parse(integration_script.read_text(encoding='utf8'));bind(integration_script)
    for folder in (BASE,ROOT/'docs/validation/evidence/outpaint-geometry-20261019-v66-r1',
                   *sorted((ROOT/'docs/assets').glob('video-outpainting-20261019-v66-*'))):
        for p in folder.rglob('*'):
            if p.is_file() and p!=output:bind(p)
    crash=read(BASE/'vace-harmonic-r2/native-crash-analysis.json')
    assert crash['status']=='failed_native_dependency_before_generation' and crash['worker_pid_decimal']==24208
    assert crash['module']=='torch_cpu.dll' and crash['exception_code']=='0xc0000005' and crash['generated_frames']==0
    assert not crash['expanded_asset_registered'] and not crash['expanded_output_exists'] and crash['inpainting_cache_empty']
    assert not crash['native_exception_root_cause_resolved'] and not crash['classified_as_cuda_oom']
    assert sha(BASE/'vace-harmonic-r2/windows-native-crash-events.json')==crash['windows_events_sha256']
    retry=read(BASE/'vace-harmonic-r3/native-crash-analysis.json')
    assert retry['worker_pid_decimal']==34396 and retry['report_id']=='03b8b551-5e2b-4fc4-926d-a15540c97cdd'
    assert retry['module']==crash['module'] and retry['exception_code']==crash['exception_code'] and retry['fault_offset']==crash['fault_offset']
    assert retry['generated_frames']==0 and not retry['expanded_asset_registered'] and not retry['expanded_output_exists']
    assert retry['inpainting_cache_empty'] and not retry['native_exception_root_cause_resolved'] and not retry['classified_as_cuda_oom']
    assert sha(BASE/'vace-harmonic-r3/windows-native-crash-events.json')==retry['windows_events_sha256']
    historical=read(BASE/'pre-pread-source/source-snapshot.json');old_inputs=historical['files']
    assert historical['methods']==1454 and len(old_inputs)==200 and sha(BASE/'pre-pread-source/source-snapshot.zip')==historical['archive_sha256']
    with zipfile.ZipFile(BASE/'pre-pread-source/source-snapshot.zip') as snapshot:
        assert snapshot.testzip() is None and set(snapshot.namelist())==set(old_inputs)
        for name,digest in old_inputs.items():assert 'sha256:'+hashlib.sha256(snapshot.read(name)).hexdigest()==digest
    old_full=read(BASE/'full-r1.json');assert old_full['terminal_ok'] and old_full['methods']==1454 and old_full['skipped']==0
    assert old_full['exit_code']==0 and old_full['frozen_equal'] and old_full['frozen_before']==old_full['frozen_after']==old_inputs
    assert sha(BASE/'full-r1.log')==old_full['log_sha256']
    changed={name for name in current if current[name]!=old_inputs[name]}
    assert changed=={'product/src/ai_ad_editor/vace_model.py','product/src/ai_ad_editor/local_matting.py','product/tests/test_local_vace.py'}
    integration=read(BASE/'pre-pread-source/integration.json')
    assert integration['before']==old_inputs and integration['after']==current and integration['methods_from_ast']==1462
    for before_case,after_case in [('lama-direct-r2','lama-direct-r3'),('lama-harmonic-r1','lama-harmonic-r2'),('installed-r1/media','installed-r2/media')]:
        old=read(BASE/before_case/'verification.json');new=read(BASE/after_case/'verification.json')
        assert old['status']=='passed_execution_quality_separate' and old['frozen_equal']
        assert old['frozen_before']==old['frozen_after']==old_inputs
        for key in ('decoded_rgba_sha256','decoded_pcm_sha256','quality'):assert old[key]==new[key],(before_case,key)
    for failed in ('vace-harmonic-r2','vace-harmonic-r3'):
        failure=read(BASE/failed/'verification.json')
        assert failure['status']=='failed' and failure['frozen_equal'] and failure['frozen_before']==failure['frozen_after']==old_inputs
        calls(BASE/failed,failure['calls'],{'outpaint':6})
        failure_call=next(c for c in failure['calls'] if c['name']=='outpaint');assert failure_call['exit_code']==6
        succeeded_call=next(c for c in media[2]['calls'] if c['name']=='outpaint')
        for flag in ('--width','--height','--offset-x','--offset-y','--repair-blend','--model-max-edge','--prompt','--negative-prompt','--seed','--inference-steps','--window-frames','--window-overlap'):
            assert failure_call['command'][failure_call['command'].index(flag)+1]==succeeded_call['command'][succeeded_call['command'].index(flag)+1],flag
        old_adapter=read(BASE/failed/'model-register.stdout.log')['data']['adapter']
        new_adapter=read(BASE/'vace-harmonic-r4/model-register.stdout.log')['data']['adapter']
        assert old_adapter['model_sha256']==new_adapter['model_sha256'] and old_adapter['settings']==new_adapter['settings']
        assert old_adapter['executable_sha256']==new_adapter['executable_sha256']
        old_weights=[{k:a[k] for k in ('path','sha256','bytes')} for a in old_adapter['artifacts'] if a['role']=='model']
        new_weights=[{k:a[k] for k in ('path','sha256','bytes')} for a in new_adapter['artifacts'] if a['role']=='model']
        assert old_weights==new_weights and len(new_weights)==17 and sum(a['bytes'] for a in new_weights)==19037105642
        assert sha(ROOT/('docs/assets/video-outpainting-20261019-v66-'+failed+'/source.mov'))==sha(ROOT/'docs/assets/video-outpainting-20261019-v66-vace-harmonic-r4/source.mov')
        cleanup=read(BASE/failed/'project-cleanup-snapshot.json');project=read(BASE/failed/'failed-project.json')
        assert sha(BASE/failed/'failed-project.json')==cleanup['project_sha256'] and not cleanup['remaining_inpainting_cache_files']
        assert len(project['assets'])==1 and not any(a['id']=='expanded' for a in project['assets'])
    native=read(BASE/'vace-harmonic-r2/loading-candidate.json')
    for filename,entry in native['files'].items():assert sha(Path(filename))==entry['sha256']
    probe=read(BASE/'storage-prefix-r1/verification.json')
    assert probe['status']=='inconclusive_timeout_before_first_receipt' and not probe['candidate_fix_validated']
    assert not probe['pread_executed'] and probe['sampled_tensors_proven']==0 and probe['owned_child_absent_after_timeout']
    for name,entry in probe['files'].items():assert sha(BASE/'storage-prefix-r1'/name)==entry['sha256']
    assert sha(ROOT/'scripts/probe_safetensors_window_read.py')==sha(BASE/'storage-prefix-r1/executed-probe.py')
    legacy=ROOT/'docs/validation/evidence/vace-delivery-20261019-v66-r1'
    old=read(legacy/'delivery-audit-r1/verification.json');assert old['status']=='passed_delivery_quality_separate'
    assert old['archived_inputs']==198 and not old['controlled_quality_passed']
    for folder in (legacy,ROOT/'docs/assets/vace-delivery-20261019-v66-r1'):
        for p in folder.rglob('*'):
            if p.is_file():bind(p)
    counts.update(full_methods=1462,new_subset=24,loader_regression_methods=41,added_reader_methods=8,frozen_files=200,packaged_files=133,
        development_frames=sum(v['frames'] for v in media[:3]),development_cli=sum(v['cli_calls'] for v in media[:3]),
        installed_frames=8,installed_cli=installed['isolated_cli_calls'],skills=17,skill_links=238,
        document_links=links,bound_files=len(files))
    record={'status':'passed_scoped_release','checked_at_utc':datetime.now(timezone.utc).isoformat(),
        'counts':counts,'quality':[{k:v[k] for k in ('engine','blend','installed','quality')} for v in media],
        'limits':{'native_torch_text_load_access_violation_unresolved':True,'natural_quality_accepted':False,
                  'vace_installed_inference_tested':False,'different_machine_accepted':False,'full_capcut_parity':False},
        'files':files,'frozen_before':current,'frozen_after':frozen(),'frozen_equal':current==frozen()}
    assert record['frozen_equal']
    output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps(counts))


if __name__=='__main__':main()
