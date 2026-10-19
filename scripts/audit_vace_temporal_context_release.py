"""Bind V68 runtime, terminal tests, media, native package and Agent guidance."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import urllib.parse
import zipfile

from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/vace-temporal-context-20261020-v68'


def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_bytes())
def runtime_closure(value):return {k:v for k,v in value.items() if not k.startswith('product/tests/')}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--target',default='target-r3')
    parser.add_argument('--full',default='full-r1')
    args=parser.parse_args();output=args.output.resolve();assert not output.exists()
    current=frozen();bound={};links=[]

    def bind(path):
        path=path.resolve();assert path.is_file()
        bound[path.relative_to(ROOT).as_posix()]={'bytes':path.stat().st_size,'sha256':sha(path)}

    for name,methods in ((args.target,65),(args.full,1520)):
        value=read(BASE/(name+'.json'))
        assert value['terminal_ok'] and value['exit_code']==0 and value['skipped']==0
        assert value['methods']==methods and value['frozen_equal']
        assert value['frozen_before']==value['frozen_after']==current
        assert value['log_sha256']==sha(BASE/(name+'.log'))

    def calls(base, value, *, expected=True):
        for call in value['calls']:
            for key in ('stdout','stderr'):
                path=base/call[key];assert sha(path)==call[key+'_sha256'];bind(path)
            if call.get('stdout_encoding')=='gzip-raw':
                raw=gzip.decompress((base/call['stdout']).read_bytes())
                assert len(raw)==call['decoded_stdout_bytes']
                assert 'sha256:'+hashlib.sha256(raw).hexdigest()==call['decoded_stdout_sha256']
            if expected:assert call['exit_code']==call.get('expected_exit',0),call['name']

    actual=read(BASE/'previous-r1/verification.json')
    assert actual['status']!='running' and actual['frozen_equal'] is False
    revision=read(BASE/'test-only-revision.json')
    assert revision['changed_inputs']==['product/tests/test_vace_context.py'] and revision['runtime_closure_equal']
    assert actual['frozen_before']==revision['frozen_before']
    assert actual['frozen_after']==revision['frozen_after']==current
    assert runtime_closure(actual['frozen_before'])==runtime_closure(actual['frozen_after'])==runtime_closure(current)
    assert actual['temporal_context']=='previous' and actual['text_weight_budgets_mib']=={'gpu':7168,'cpu':8192}
    assert actual['controlled_psnr_gate_db']==30 and not actual['natural_quality_accepted']
    assert sha(BASE/'previous-r1/executed-generator.py')==actual['generator_sha256']
    calls(BASE/'previous-r1',actual,expected=False)
    if actual['status']=='failed':
        assert any(c['name']=='outpaint' and c['exit_code']!=0 for c in actual['calls'])
        failure=read(BASE/'previous-r1/failure-r1/verification.json')
        assert failure['status']=='passed' and failure['accepted_vace_forwards']==0
        assert failure['cache_empty'] and not failure['expanded_asset_registered'] and not failure['generated_output_exists']
        assert failure['metadata_before_diagnostic_queries']==failure['metadata_after_diagnostic_queries']
        assert not failure['metadata_before_outpaint_captured']
        calls(BASE/'previous-r1/failure-r1',failure)
        cleanup=read(BASE/'previous-r1/owned-process-cleanup-r1.json')
        assert cleanup['remaining_observed_owned']==0 and cleanup['stopped_by_this_check']==0 and len(cleanup['processes'])==5
        assert not any(row['same_process_still_running'] for row in cleanup['processes'])
    else:
        assert actual['frames']==8 and actual['model_calls']==2
        assert all(c['passed'] for c in actual['checks'])

    dev=read(BASE/'lama-r1/verification.json')
    install=read(BASE/'installed-r1/verification.json')
    inner=read(BASE/'installed-r1/base/verification.json')
    media=read(BASE/'installed-r1/base/media/verification.json')
    for base,value in ((BASE/'lama-r1',dev),(BASE/'installed-r1',install),
                       (BASE/'installed-r1/base',inner),(BASE/'installed-r1/base/media',media)):
        assert value['status'] in ('passed','passed_execution_quality_separate')
        assert value['frozen_equal'] and value['frozen_before']==value['frozen_after']==current
        calls(base,value)
    assert sha(BASE/'installed-r1/executed-install-check.py')==sha(ROOT/'scripts/verify_vace_temporal_context_install.py')
    assert install['base_receipt_sha256']==sha(BASE/'installed-r1/base/verification.json')
    assert install['packaged_files']==inner['packaged_files']==135
    assert install['isolated_cli_calls']==28 and install['isolated_module_contract_calls']==1
    assert install['actual_vace_forwards']==0 and install['actual_lama_forwards']==8
    assert inner['isolated_cli_calls']==25 and all(c['equal'] for c in inner['comparisons'])
    for value in (dev,media):
        assert value['frames']==value['model_calls']==8 and value['cli_calls']==23
        assert all(c['passed'] for c in value['checks'])
        assert value['quality']['predeclared_gate_db']==30 and value['quality']['passed']
        assert not value['quality']['natural_quality_accepted']
        assert value['generator_sha256']==sha(ROOT/'scripts/smoke_video_outpainting.py')
        for name,item in value['files'].items():
            p=ROOT/name;assert sha(p)==item['sha256'] and p.stat().st_size==item['bytes'];bind(p)
    for key in ('decoded_rgba_sha256','decoded_pcm_sha256','quality'):assert dev[key]==media[key]
    release=ROOT/'docs/assets/vace-temporal-context-20261020-v68-installed/release'
    manifest=read(release/'manifest.json');assert len(manifest['wheels'])==7
    with zipfile.ZipFile(release/'agent-video-kit-cp313-win_amd64.zip') as archive:
        assert archive.read('manifest.json')==(release/'manifest.json').read_bytes()
        for item in manifest['files']:
            raw=archive.read(item['path'])
            assert len(raw)==item['bytes'] and 'sha256:'+hashlib.sha256(raw).hexdigest()==item['sha256']
        own=next(w for w in manifest['wheels'] if w['name']=='ai-ad-editor')
        with zipfile.ZipFile(io.BytesIO(archive.read(own['path']))) as wheel:
            names=[n for n in wheel.namelist() if n.startswith('ai_ad_editor/') and not n.endswith('/')]
            assert len(names)==135
            for name in names:assert wheel.read(name)==(ROOT/'product/src'/name).read_bytes()
    skills=read(BASE/'skills-r1.json');mapping=read(ROOT/'video-cut-install-manifest.json')
    assert skills['skill_count']==mapping['skill_count']==17 and skills['local_links_checked']==250
    for row in skills['results']:
        p=ROOT/'skills'/row['skill']/'SKILL.md'
        item=next(v for v in mapping['skills'] if v['name']==row['skill'])
        assert sha(p)==row['sha256']=='sha256:'+item['skill_md_sha256'];bind(p)
        assert Path(item['registration_directory']).resolve()==p.parent.resolve()
    for name in ('baseline-v67-source','pre-assertion-fix-source'):
        value=read(BASE/(name+'.json'));archive=BASE/(name+'.zip')
        assert sha(archive)==value['archive_sha256']
        with zipfile.ZipFile(archive) as z:
            assert set(z.namelist())==set(value['frozen_inputs'])
            for n,h in value['frozen_inputs'].items():assert 'sha256:'+hashlib.sha256(z.read(n)).hexdigest()==h
    for path in BASE.rglob('*'):
        if path.is_file() and path.resolve()!=output:bind(path)
    for folder in ROOT.glob('docs/assets/vace-temporal-context-20261020-v68*'):
        for path in folder.rglob('*'):
            if path.is_file():bind(path)
    documents=[ROOT/'README.md',ROOT/'docs/README.md',ROOT/'docs/构建进度总表_2026-10-16.md',
        ROOT/'docs/产品需求与开发路线基线_2026-10-12.md',ROOT/'docs/specs/AgentCLI契约_v0.1_2026-10-13.md',
        ROOT/'docs/validation/README功能核验与实测演示_2026-10-16.md',
        ROOT/'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md',
        ROOT/'docs/validation/VACE前窗生成上下文实测_2026-10-20.md',
        ROOT/'docs/specs/VACE前窗生成上下文与连续输出契约_v0.1_2026-10-20.md']
    for path in documents:
        bind(path)
        for raw in re.findall(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^\"]*")?\)',path.read_text(encoding='utf8')):
            value=raw.strip('<>').split('#',1)[0]
            if not value or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',value):continue
            target=(path.parent/urllib.parse.unquote(value)).resolve();assert target.exists(),(path,value)
            links.append({'from':path.relative_to(ROOT).as_posix(),'to':target.relative_to(ROOT).as_posix()})
    for path in ROOT.glob('scripts/*vace_temporal_context*.py'):bind(path)
    for path in (ROOT/'.gitattributes',ROOT/'video-cut-install-manifest.json',ROOT/'scripts/smoke_video_outpainting.py',
                 ROOT/'scripts/verify_video_outpainting_install.py',ROOT/'scripts/run_frozen_regression.py'):bind(path)
    record={'status':'passed','checked_at_utc':datetime.now(timezone.utc).isoformat(),'frozen_inputs':current,
        'full_methods':1520,'target_methods':65,'new_methods':24,'packaged_files':135,
        'isolated_cli_calls':28,'isolated_module_contract_calls':1,'skills':17,'skill_links':250,
        'native_previous_status':actual['status'],'natural_quality_accepted':False,'full_capcut_parity':False,
        'bound_files':bound,'local_document_links':links}
    output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'status':'passed','files':len(bound),'document_links':len(links)}))


if __name__=='__main__':main()
