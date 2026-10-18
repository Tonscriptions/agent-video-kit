"""Bind V57 source, complete receipts, installed bytes, media, failures, skills and current docs."""
from __future__ import annotations
import argparse,hashlib,io,json,re,subprocess,urllib.parse,zipfile
from datetime import datetime,timezone
from pathlib import Path
from run_frozen_regression import frozen
from sync_complete_output_retime_documents import DOCS,CONTRACT,REPORT

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'docs/validation/evidence/retime-edits-20261019-v57'
PUBLIC=ROOT/'docs/assets/retime-release-20261019-v57'
NATIVE=ROOT/'docs/validation/evidence/retime-native-release-20261019-v57'
FINAL=EVIDENCE/'release.json'
def read(p):return json.loads(p.read_bytes())
def digest(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()
def sha(p):return digest(p.read_bytes())

def run(output,preflight):
    assert not output.exists();current=frozen();assert len(current)==184
    full=read(EVIDENCE/'full-final.json');assert full['frozen_before']==current
    if not preflight:
        assert full['terminal_ok'] and full['exit_code']==0 and full['skipped']==0 and full['methods']==1329
        assert full['frozen_equal'] and full['frozen_after']==current
        assert sha(EVIDENCE/'full-final.log')==full['log_sha256']
    for name,methods in [('targeted-final',40),('magnetic-final',66)]:
        r=read(EVIDENCE/(name+'.json'))
        assert r['terminal_ok'] and r['methods']==methods and r['exit_code']==r['skipped']==0
        assert r['frozen_before']==r['frozen_after']==current
        assert sha(EVIDENCE/(name+'.log'))==r['log_sha256']
    smoke=read(PUBLIC/'verification.json');native=read(NATIVE/'verification.json');media=read(EVIDENCE/'media-release.json')
    assert smoke['status']=='passed_scoped_complete_output_retime'
    assert smoke['frozen_before']==smoke['frozen_after']==current
    assert len(smoke['cases'])==9 and len(smoke['cli_calls'])==62
    assert smoke['main_frames']==344 and smoke['stereo_sample_frames']==1651200
    assert max(r['max_rgb_error'] for r in smoke['cases'])==1 and max(r['max_pcm_error'] for r in smoke['cases'])==0
    assert sha(ROOT/'scripts/smoke_complete_output_retime.py')==sha(PUBLIC/'executed-generator.py')
    for row in smoke['files']:
        p=PUBLIC/row['path'];assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],p
    for call in smoke['cli_calls']:
        assert call['exit_code']==call['expected_exit_code'] and sha(PUBLIC/call['result'])==call['result_sha256']
        assert read(PUBLIC/call['result'])['ok']==(call['expected_exit_code']==0)
    assert sum(c['expected_exit_code']==2 for c in smoke['cli_calls'])==2
    assert media['status']=='passed_scoped_media_audit' and media['source_receipt_sha256']==sha(PUBLIC/'verification.json')
    assert media['generator_sha256']==sha(ROOT/'scripts/audit_complete_output_retime_media.py')
    assert media['master_frames']==344 and media['master_stereo_sample_frames']==1651200
    assert media['gif']=={'width':480,'height':192,'frames':43,'duration_ms':4300}
    assert len(media['previews'])==9
    for row in media['previews']:assert sha(PUBLIC/row['path'])==row['sha256']
    assert sha(PUBLIC/media['static_review']['path'])==media['static_review']['sha256']
    static=read(EVIDENCE/'static-review.json');assert len(static['images'])==2
    assert not static['continuous_playback'] and not static['human_listening']
    for row in static['images']:assert sha(Path(row['path']))==row['sha256']
    assert native['status']=='passed' and native['installer_exit_code']==0 and native['isolated_cli_calls']==51
    assert native['installed_package_files']==123 and native['package_bytes_equal_to_wheel_and_source']
    assert native['actual_new_frames']==454 and native['actual_new_stereo_sample_frames']==2179200
    assert native['frozen_before']==native['frozen_after']==current
    assert native['generator_sha256']==sha(ROOT/'scripts/verify_complete_output_retime_native.py')==sha(NATIVE/'executed-generator.py')
    assert len(native['outputs'])==12 and all(r['max_rgb_error']<=2 and r['max_pcm_error']<=2e-6 for r in native['outputs'])
    for call in native['calls']:
        i=call['index'];assert '-I' in call['command'] and '-S' in call['command']
        assert call['exit_code']==call['expected_exit_code']
        assert sha(NATIVE/f'{i:02}.stdout.json')==call['stdout_sha256'] and sha(NATIVE/f'{i:02}.stderr.log')==call['stderr_sha256']
    assert sum(c['expected_exit_code']==2 for c in native['calls'])==1
    assert not native['other_machine_accepted'] and not native['human_listening'] and not native['virtual_environment']
    release=PUBLIC/'agent-video-kit-cp313-win_amd64.zip'
    assert sha(release)==native['release_zip_sha256'] and sha(PUBLIC/'release-manifest.json')==native['manifest_sha256']
    with zipfile.ZipFile(release) as z:
        manifest=json.loads(z.read('manifest.json'));assert z.read('manifest.json')==(PUBLIC/'release-manifest.json').read_bytes()
        assert len(manifest['wheels'])==7 and not manifest['python_included'] and not manifest['ffmpeg_included']
        for row in manifest['files']:
            raw=z.read(row['path']);assert len(raw)==row['bytes'] and digest(raw)==row['sha256']
        product=next(r for r in manifest['wheels'] if r['name']=='ai-ad-editor')
        with zipfile.ZipFile(io.BytesIO(z.read(product['path']))) as wheel:
            names={n for n in wheel.namelist() if n.startswith('ai_ad_editor/') and not n.endswith('/')}
            assert len(names)==123 and names==set(native['installed_files'])
            for name in names:
                raw=wheel.read(name);assert raw==(ROOT/'product/src'/name).read_bytes() and digest(raw)==native['installed_files'][name]
            assert 'ai_ad_editor/retime_edits.py' in names and 'ai_ad_editor/retime_transform.py' in names
    schema=ROOT/'docs/specs/agent-project.schema.json'
    assert schema.read_bytes()==(ROOT/'product/src/ai_ad_editor/agent-project.schema.json').read_bytes() and sha(schema)==manifest['schema_sha256']
    development=EVIDENCE/'development';index=read(development/'index.json');assert index['status']=='preserved_and_verified'
    assert index['generator_sha256']==sha(ROOT/'scripts/archive_complete_output_retime_development.py')
    assert len(index['runs'])==6 and len(index['files'])==628 and index['author_probe']['max_pcm_difference']==0
    archive=development/index['archive'];assert sha(archive)==index['archive_sha256']
    with zipfile.ZipFile(archive) as z:
        assert len(z.namelist())==len(index['files'])
        for row in index['files']:
            raw=z.read(row['member']);assert len(raw)==row['bytes'] and digest(raw)==row['sha256']
        failure=json.loads(z.read('docs/assets/retime-second-20261019-v57/failure.json'))
        assert '0.139936149' in failure['error']
        for name in ('render.py','time_mapping.py'):
            assert digest(z.read('source-before-native-tempo-fix/'+name))==failure['source_freeze']['product/src/ai_ad_editor/'+name]
        assert z.read('docs/assets/retime-second-20261019-v57/source.wav')==(PUBLIC/'source.wav').read_bytes()
        assert z.read('docs/assets/retime-second-20261019-v57/RT05-edit.json')==(PUBLIC/'RT05-edit.json').read_bytes()
    failed_native=read(ROOT/'docs/validation/evidence/retime-native-final-20261019-v57/failure.json')
    assert failed_native['calls'][-1]['exit_code']==2 and failed_native['error']=='AssertionError()'
    first=read(ROOT/'docs/validation/evidence/retime-edits-20261018-v57/targeted-first.json')
    assert first['exit_code']==1 and first['methods']==36 and not first['terminal_ok']
    head=read(PUBLIC/'RT06-legacy-head-comparison.json');assert not head['accepted_reference'] and head['max_pcm_difference']>.08
    tempo=read(PUBLIC/'RT06-native-tempo.json');assert tempo['raw_output_samples']==24475 and tempo['selection']==[475,24475]
    skills=read(EVIDENCE/'skills.json');mapping=read(ROOT/'video-cut-install-manifest.json')
    assert skills['skill_count']==14 and skills['local_links_checked']==202
    assert mapping['current_audit']['record_sha256']==sha(EVIDENCE/'skills.json')
    for row in skills['results']:
        name=row['skill'];assert name.startswith('video-cut-') and sha(ROOT/'skills'/name/'SKILL.md')==row['sha256']
        assert (Path('C:/Users/carzy/.codex/skills')/name).resolve()==(ROOT/'skills'/name).resolve()
        assert next(s for s in mapping['skills'] if s['name']==name)['skill_md_sha256']==row['sha256'][7:]
    docs=[ROOT/n for n in DOCS]+[ROOT/'docs/specs'/CONTRACT,ROOT/'docs/validation'/REPORT,
        ROOT/'docs/OpenFilm最新源码复核与降本清单_2026-10-18.md'];links=[]
    for doc in docs:
        source=doc.read_text(encoding='utf-8-sig')
        for raw in re.findall(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^\"]*")?\)',source):
            target=raw.strip('<>').split('#',1)[0]
            if not target or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',target):continue
            path=(doc.parent/urllib.parse.unquote(target)).resolve();assert path.exists() or path==FINAL,(doc,raw)
            links.append({'document':doc.relative_to(ROOT).as_posix(),'target':raw})
        if not preflight and doc.name!=CONTRACT and doc.name!='OpenFilm最新源码复核与降本清单_2026-10-18.md':
            assert '完整回归运行中' not in source.split('<!-- /V57-CURRENT -->')[0]
    process=subprocess.run(['powershell','-NoProfile','-Command',
        "@(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.Name -in @('chrome-headless-shell.exe','chrome.exe','node.exe') -and ($_.CommandLine -like '*AI广告剪辑*html-toolchain*' -or $_.CommandLine -like '*AI广告剪辑*html_motion_worker.mjs*') } | Select-Object ProcessId,ParentProcessId,Name,CommandLine) | ConvertTo-Json -Depth 3 -Compress"],capture_output=True,check=True)
    residual=json.loads(process.stdout.decode('utf-8-sig').strip() or '[]')
    if isinstance(residual,dict):residual=[residual]
    if not preflight:assert not residual,residual
    extras={'verification.json','encoded-static-review.png','agent-video-kit-cp313-win_amd64.zip','release-manifest.json','install-receipt.json'}
    assert {p.relative_to(PUBLIC).as_posix() for p in PUBLIC.rglob('*') if p.is_file()}=={r['path'] for r in smoke['files']}|extras
    record={'status':'passed_preflight_full_pending' if preflight else 'passed','checked_at_utc':datetime.now(timezone.utc).isoformat(),
        'generator_sha256':sha(Path(__file__)),'frozen_files':len(current),'source_freeze':current,
        'full_methods':full.get('methods'),'new_methods':40,'magnetic_integration_methods':66,
        'main_cli_calls':62,'main_frames':344,'stereo_sample_frames':1651200,
        'native_cli_calls':51,'native_package_files':123,'native_frames':454,'native_stereo_sample_frames':2179200,
        'skill_count':14,'skill_local_links':202,'documents':{p.relative_to(ROOT).as_posix():sha(p) for p in docs},
        'document_local_links':len(links),'fixed_toolchain_residual_processes':residual,
        'public_files':{p.relative_to(PUBLIC).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(PUBLIC.rglob('*')) if p.is_file()},
        'suite_receipt_sha256':sha(EVIDENCE/'full-final.json'),'native_receipt_sha256':sha(NATIVE/'verification.json'),
        'media_receipt_sha256':sha(EVIDENCE/'media-release.json'),'static_review_sha256':sha(EVIDENCE/'static-review.json'),
        'preserved_development_index_sha256':sha(development/'index.json'),'full_capcut_parity_accepted':False,
        'other_machine_accepted':False,'natural_audio_accepted':False}
    output.parent.mkdir(exist_ok=True,parents=True);output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:record[k] for k in ('status','frozen_files','full_methods','document_local_links','native_package_files','skill_count')}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--preflight',action='store_true')
    a=p.parse_args();run(a.output.resolve(),a.preflight)
