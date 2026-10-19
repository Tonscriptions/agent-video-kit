"""Bind current source, native evidence, installed resources and documentation."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import gzip
import io
import json
from pathlib import Path
import re
import urllib.parse
import zipfile
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/pipeline-diagnostics-20261020-v67'

def sha(p): return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_bytes())

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    output=args.output.resolve();assert not output.exists()
    current=frozen();bound={};links=[]
    def bind(path):
        path=path.resolve();assert path.is_file();bound[path.relative_to(ROOT).as_posix()]={'sha256':sha(path),'bytes':path.stat().st_size}
    full=read(BASE/'full-r2.json');target=read(BASE/'target-r5.json')
    assert full['methods']==1496 and target['methods']==34
    for value in (full,target):
        assert value['terminal_ok'] and value['exit_code']==0 and value['skipped']==0
        assert value['frozen_equal'] and value['frozen_before']==value['frozen_after']==current
    assert len(current)==202
    for name in ('full-r2','target-r5'):
        assert sha(BASE/(name+'.log'))==read(BASE/(name+'.json'))['log_sha256']
    for folder in ('native-r3','installed-native-r1','lama-r3','installed-r1','installed-r1/media'):
        base=BASE/folder;v=read(base/'verification.json')
        assert v['frozen_equal'] and v['frozen_before']==v['frozen_after']==current
        assert v['status'] in ('passed','passed_execution_quality_separate')
        for call in v['calls']:
            for key in ('stdout','stderr'):
                p=base/call[key];assert sha(p)==call[key+'_sha256'];bind(p)
            if call.get('stdout_encoding')=='gzip-raw':
                raw=gzip.decompress((base/call['stdout']).read_bytes())
                assert len(raw)==call['decoded_stdout_bytes'] and 'sha256:'+hashlib.sha256(raw).hexdigest()==call['decoded_stdout_sha256']
            assert call['exit_code']==call.get('expected_exit',call.get('expected',0)),call['name']
        if folder in ('native-r3','installed-native-r1'):
            assert sha(base/'executed-smoke.py')==sha(ROOT/'scripts/smoke_pipeline_diagnostics.py')
            assert len(v['calls'])==10 and v['metadata_before']==v['metadata_after'] and v['cache_empty'] and not v['failed_assets_registered']
            assert not v['model_forward_accepted']
            manifest=read(base/'record/manifest.json'); ref=v['diagnostic']
            assert sha(base/'record/manifest.json')==ref['manifest_sha256']
            assert manifest['root_cause']=='unknown' and manifest['operation_id']==v['operation_id']
            assert manifest['error']['code']=='MATTING_PIPELINE_FAILED'
            rows={r['role']:r for r in manifest['processes']}
            assert set(rows)=={'decoder','worker','encoder'}
            assert rows['worker']['observed_exit']['raw']==1 and not rows['worker']['cleanup_requested']
            assert all(r['pid'] and r['final_exit'] is not None for r in rows.values())
            assert 'DecodeError' in read(base/'record/response.json')['worker_error']
            assert sum(p.stat().st_size for p in (base/'record').iterdir())<=512*1024
            with zipfile.ZipFile(base/'failure.zip') as z:
                assert set(z.namelist())=={'manifest.json',*manifest['files']}
                for name in z.namelist():assert z.read(name)==(base/'record'/name).read_bytes()
            assert (base/'failure.zip').stat().st_size<=768*1024 and sha(base/'failure.zip')==v['archive_sha256']
            for name,item in manifest['files'].items():
                p=base/'record'/name;assert sha(p)==item['sha256'] and p.stat().st_size==item['bytes'];bind(p)
            if folder.startswith('installed'):
                assert all('-I' in c['command'] and '-S' in c['command'] and '-B' in c['command'] for c in v['calls'])
        if folder in ('lama-r3','installed-r1/media'):
            assert sha(base/'executed-generator.py')==v['generator_sha256']==sha(ROOT/'scripts/smoke_video_outpainting.py')
            assert v['frames']==v['model_calls']==8 and v['cli_calls']==23 and all(c['passed'] for c in v['checks'])
            assert v['quality']['passed'] and v['quality']['predeclared_gate_db']==30 and not v['quality']['natural_quality_accepted']
            for name,item in v['files'].items():
                p=ROOT/name;assert sha(p)==item['sha256'] and p.stat().st_size==item['bytes'];bind(p)
    dev=read(BASE/'lama-r3/verification.json');ins=read(BASE/'installed-r1/media/verification.json')
    old=read(ROOT/'docs/validation/evidence/video-outpainting-20261019-v66/lama-harmonic-r2/verification.json')
    for key in ('decoded_rgba_sha256','decoded_pcm_sha256','quality'):assert dev[key]==ins[key]==old[key]
    release=ROOT/'docs/assets/pipeline-diagnostics-20261020-v67-installed/release'
    manifest=read(release/'manifest.json'); install=read(BASE/'installed-r1/verification.json')
    assert install['packaged_files']==134 and install['isolated_cli_calls']==25 and len(manifest['wheels'])==7
    assert sha(BASE/'installed-r1/executed-install-check.py')==sha(ROOT/'scripts/verify_video_outpainting_install.py')
    assert all(c['equal'] for c in install['comparisons'])
    with zipfile.ZipFile(release/'agent-video-kit-cp313-win_amd64.zip') as archive:
        assert archive.read('manifest.json')==(release/'manifest.json').read_bytes()
        own=next(v for v in manifest['wheels'] if v['name']=='ai-ad-editor')
        for item in manifest['files']:
            raw=archive.read(item['path']);assert len(raw)==item['bytes'] and 'sha256:'+hashlib.sha256(raw).hexdigest()==item['sha256']
        with zipfile.ZipFile(io.BytesIO(archive.read(own['path']))) as wheel:
            names=[n for n in wheel.namelist() if n.startswith('ai_ad_editor/') and not n.endswith('/')]
            assert len(names)==134
            for name in names:assert wheel.read(name)==(ROOT/'product/src'/name).read_bytes()
    skill=read(BASE/'skills-r1.json');skill_manifest=read(ROOT/'video-cut-install-manifest.json')
    assert skill['skill_count']==17 and skill['local_links_checked']==244
    for row in skill['results']:
        p=ROOT/'skills'/row['skill']/'SKILL.md';item=next(v for v in skill_manifest['skills'] if v['name']==row['skill'])
        assert sha(p)==row['sha256']=='sha256:'+item['skill_md_sha256'];bind(p)
        assert Path(item['registration_directory']).resolve()==p.parent.resolve()
    for name in ('pre-response-error-source','pre-policy-source'):
        value=read(BASE/(name+'.json'));archive=BASE/(name+'.zip');assert sha(archive)==value['archive_sha256']
        with zipfile.ZipFile(archive) as z:
            assert set(z.namelist())==set(value['frozen_inputs'])
            for n,h in value['frozen_inputs'].items():assert 'sha256:'+hashlib.sha256(z.read(n)).hexdigest()==h
    stopped=read(BASE/'full-r1.json');assert stopped['not_a_completed_regression'] and stopped['status']=='stopped_for_implementation_fix'
    historical=read(BASE/'historical-crash-mapping.json')
    for source in historical['sources']:
        assert sha(ROOT/source['source'])==source['source_sha256']
        assert source['application_error_events'][0]['fields']['ExceptionCode']=='c0000005'
    research=read(ROOT/'docs/validation/evidence/openfilm-reuse-20261020-r08-r3/verification.json')
    assert research['head']=='71922644da5d6b67db2cc796d4e057f98999944f' and research['source_files']==757
    assert research['groups']['skills']['files_after']==31 and research['groups']['providers']['files_after']==29
    assert research['fcpxml_original_tests']=={'tests':10,'pass':9,'fail':0,'skipped':1} and research['extracted_oom_cases']==8
    thumbnail=read(BASE/'current-thumbnail-static-r1.json')
    assert sha(ROOT/thumbnail['current_source'])==thumbnail['source_sha256']
    assert sha(ROOT/thumbnail['cli_source'])==thumbnail['cli_source_sha256']
    cleanup=read(BASE/'full-observed-cleanup-r1.json')
    assert cleanup['remaining_observed_owned']==0 and cleanup['stopped_processes']==0 and len(cleanup['observed_processes'])==6
    assert all(not r['owned_process_still_running'] for r in cleanup['observed_processes'])
    for folder in (BASE,ROOT/'docs/assets/pipeline-diagnostics-20261020-v67-lama-r3',ROOT/'docs/assets/pipeline-diagnostics-20261020-v67-installed',
        ROOT/'docs/validation/evidence/openfilm-refresh-20261020-r08', ROOT/'docs/validation/evidence/openfilm-reuse-20261020-r08',
        ROOT/'docs/validation/evidence/openfilm-reuse-20261020-r08-r2', ROOT/'docs/validation/evidence/openfilm-reuse-20261020-r08-r3'):
        for p in folder.rglob('*'):
            if p.is_file() and p.resolve()!=output:bind(p)
    paths=[ROOT/'.gitattributes',ROOT/'README.md',ROOT/'video-cut-install-manifest.json',ROOT/'docs/OpenFilm最新复用评估与成本取舍_2026-10-20.md',
        ROOT/'docs/OpenFilm当前复用决策_2026-10-18.md',ROOT/'docs/third-party/OpenFilm复用声明_2026-10-17.md',
        ROOT/'docs/specs/本地模型管道诊断与有界留证契约_v0.1_2026-10-20.md',
        ROOT/'docs/validation/本地模型管道诊断与回收前留证实测_2026-10-20.md',
        ROOT/'docs/README.md',ROOT/'docs/构建进度总表_2026-10-16.md',ROOT/'docs/产品需求与开发路线基线_2026-10-12.md',
        ROOT/'docs/specs/AgentCLI契约_v0.1_2026-10-13.md',ROOT/'docs/validation/README功能核验与实测演示_2026-10-16.md',
        ROOT/'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md']
    for p in paths:
        bind(p)
        if p.suffix!='.md':continue
        for raw in re.findall(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^\"]*")?\)',p.read_text(encoding='utf8')):
            value=raw.strip('<>').split('#',1)[0]
            if not value or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',value):continue
            target=(p.parent/urllib.parse.unquote(value)).resolve();assert target.exists(),(p,value)
            links.append({'from':p.relative_to(ROOT).as_posix(),'to':target.relative_to(ROOT).as_posix()})
    for p in ROOT.glob('scripts/*pipeline_diagnostics*.py'):bind(p)
    bind(ROOT/'scripts/review_openfilm_r08.py');bind(ROOT/'sources/upstream/openfilm-refresh-20261020-r08/repo.zip')
    for name in ('run_frozen_regression.py','smoke_video_outpainting.py','verify_video_outpainting_install.py'):bind(ROOT/'scripts'/name)
    output.write_text(json.dumps({'checked_at_utc':datetime.now(timezone.utc).isoformat(),'status':'passed','frozen_inputs':current,
        'full_methods':1496,'new_subset':34,'packaged_files':134,'development_cli_calls':33,'installed_cli_calls':35,
        'development_inference_frames':8,'installed_inference_frames':8,'natural_quality_accepted':False,'capcut_equivalence':False,
        'bound_files':bound,'local_document_links':links,'upstream_original_pass':9,'upstream_original_skipped':1,'upstream_extracted_cases':8},
        ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'status':'passed','files':len(bound),'document_links':len(links),'full_methods':1496},ensure_ascii=False))

if __name__=='__main__':main()
