"""Bind V56 source, executed media, native install, skills, failures and docs."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import urllib.parse
import zipfile

from run_frozen_regression import frozen
from sync_magnetic_mode_documents import DOCS, CONTRACT, REPORT

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'docs/validation/evidence/magnetic-mode-20261018-v56'
PUBLIC=ROOT/'docs/assets/magnetic-mode-final-20261018-v56'
NATIVE=ROOT/'docs/validation/evidence/magnetic-mode-native-final-20261018-v56'
FINAL=EVIDENCE/'release.json'


def digest(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()
def sha(path):return digest(path.read_bytes())
def read(path):return json.loads(path.read_bytes())


def run(output,preflight=False):
    assert not output.exists()
    current=frozen();full=read(EVIDENCE/'full-final.json');integration=read(EVIDENCE/'magnetic-integration-final.json')
    assert len(current)==181 and full['frozen_before']==current
    if not preflight:
        assert full['terminal_ok'] and full['exit_code']==0 and full['skipped']==0 and full['methods']==1289
        assert full['frozen_equal'] and full['frozen_after']==current
        assert sha(EVIDENCE/'full-final.log')==full['log_sha256']
    assert integration['terminal_ok'] and integration['exit_code']==0 and integration['methods']==66 and integration['skipped']==0
    assert integration['frozen_before']==integration['frozen_after']==current
    assert sha(EVIDENCE/'magnetic-integration-final.log')==integration['log_sha256']
    smoke=read(PUBLIC/'verification.json');native=read(NATIVE/'verification.json');media=read(EVIDENCE/'media-final.json')
    assert smoke['status']=='passed_scoped_magnetic_mode' and smoke['frozen_before']==smoke['frozen_after']==current
    assert smoke['main_frames']==236 and smoke['stereo_sample_frames']==1132800
    assert len(smoke['cases'])==6 and len(smoke['cli_calls'])==44
    assert max(c['max_rgb_error'] for c in smoke['cases'])==1 and max(c['max_pcm_error'] for c in smoke['cases'])==0
    assert smoke['rgb_threshold']==2 and smoke['pcm_threshold']==2e-6
    assert sha(ROOT/'scripts/smoke_magnetic_mode.py')==sha(PUBLIC/'executed-generator.py')
    for call in smoke['cli_calls']:
        assert call['exit_code']==call['expected_exit_code'] and sha(PUBLIC/call['result'])==call['result_sha256']
        assert read(PUBLIC/call['result'])['ok']==(call['expected_exit_code']==0)
    assert sum(c['expected_exit_code']==2 for c in smoke['cli_calls'])==1
    for row in smoke['files']:
        path=PUBLIC/row['path'];assert path.stat().st_size==row['bytes'] and sha(path)==row['sha256'],path
    assert media['status']=='passed_scoped_media_audit' and media['source_receipt_sha256']==sha(PUBLIC/'verification.json')
    assert media['generator_sha256']==sha(ROOT/'scripts/audit_magnetic_mode_media.py')
    assert media['master_frames']==236 and media['master_stereo_sample_frames']==1132800
    assert media['gif']=={'width':480,'height':192,'frames':40,'duration_ms':4000}
    assert len(media['previews'])==6
    for row in media['previews']:assert sha(PUBLIC/row['path'])==row['sha256']
    assert sha(PUBLIC/media['static_review']['path'])==media['static_review']['sha256']
    static=read(EVIDENCE/'static-review.json')
    assert len(static['images'])==2 and not static['continuous_playback'] and not static['human_listening']
    for row in static['images']:assert sha(Path(row['path']))==row['sha256']
    assert native['status']=='passed' and native['installer_exit_code']==0 and native['isolated_cli_calls']==39
    assert native['installed_package_files']==121 and native['package_bytes_equal_to_wheel_and_source']
    assert native['actual_new_frames']==316 and native['actual_new_stereo_sample_frames']==1516800
    assert native['frozen_before']==native['frozen_after']==current
    assert native['generator_sha256']==sha(ROOT/'scripts/verify_magnetic_mode_native_install.py')==sha(NATIVE/'executed-generator.py')
    assert len(native['outputs'])==8 and all(r['max_rgb_error']==r['max_pcm_error']==0 for r in native['outputs'])
    for call in native['calls']:
        i=call['index'];assert '-I' in call['command'] and '-S' in call['command']
        assert call['exit_code']==call['expected_exit_code']
        assert sha(NATIVE/f'{i:02}.stdout.json')==call['stdout_sha256']
        assert sha(NATIVE/f'{i:02}.stderr.log')==call['stderr_sha256']
    assert sum(c['expected_exit_code']==2 for c in native['calls'])==1
    selection=read(NATIVE/'32.stdout.json')['data']['fragment']['selection']
    assert selection['requested']==['a'] and len(selection['included'])==12 and len(selection['expanded'])==11
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
            assert len(names)==121 and names==set(native['installed_files'])
            for name in names:
                raw=wheel.read(name);assert raw==(ROOT/'product/src'/name).read_bytes() and digest(raw)==native['installed_files'][name]
            assert b'magnetic_enabled(sequence)' in wheel.read('ai_ad_editor/fragments.py')
    schema=ROOT/'docs/specs/agent-project.schema.json'
    assert schema.read_bytes()==(ROOT/'product/src/ai_ad_editor/agent-project.schema.json').read_bytes()
    assert sha(schema)==manifest['schema_sha256']
    # Actual product failure and intentionally interrupted work stay distinct.
    probe=read(EVIDENCE/'fragment-probe-first.json');assert [r['exit_code'] for r in probe]==[0,0,2]
    assert 'FRAGMENT_PROJECT_INVALID' in json.dumps(probe[-1]['result'])
    assert 'EDIT_MAGNETIC_MAIN_GAP_OR_OVERLAP' in json.dumps(probe[-1]['result'])
    interruption=read(EVIDENCE/'full-first-interruption.json')
    assert interruption['status']=='intentionally_interrupted_incomplete_not_passed' and len(interruption['owned_processes'])==2
    assert not read(EVIDENCE/'full-first.json').get('terminal_ok')
    with zipfile.ZipFile(EVIDENCE/'failed-fragment-product.whl') as old:
        assert b'magnetic_enabled(sequence)' not in old.read('ai_ad_editor/fragments.py')
        assert old.read('ai_ad_editor/fragments.py')!=(ROOT/'product/src/ai_ad_editor/fragments.py').read_bytes()
    skills=read(EVIDENCE/'skills.json');mapping=read(ROOT/'video-cut-install-manifest.json')
    assert skills['skill_count']==14 and skills['local_links_checked']==198
    assert mapping['current_audit']['record_sha256']==sha(EVIDENCE/'skills.json')
    for row in skills['results']:
        name=row['skill'];assert name.startswith('video-cut-') and sha(ROOT/'skills'/name/'SKILL.md')==row['sha256']
        assert (Path('C:/Users/carzy/.codex/skills')/name).resolve()==(ROOT/'skills'/name).resolve()
        assert next(s for s in mapping['skills'] if s['name']==name)['skill_md_sha256']==row['sha256'][7:]
    docs=[ROOT/name for name in DOCS]+[ROOT/'docs/specs'/CONTRACT,ROOT/'docs/validation'/REPORT,
        ROOT/'docs/OpenFilm最新源码复核与降本清单_2026-10-18.md']
    links=[]
    for doc in docs:
        text=doc.read_text(encoding='utf-8-sig')
        for raw in re.findall(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^\"]*")?\)',text):
            target=raw.strip('<>').split('#',1)[0]
            if not target or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',target):continue
            path=(doc.parent/urllib.parse.unquote(target)).resolve()
            assert path.exists() or path==FINAL,(doc,raw)
            links.append({'document':doc.relative_to(ROOT).as_posix(),'target':raw})
    process=subprocess.run(['powershell','-NoProfile','-Command',
        "@(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.Name -in @('chrome-headless-shell.exe','chrome.exe','node.exe') -and ($_.CommandLine -like '*AI广告剪辑*html-toolchain*' -or $_.CommandLine -like '*AI广告剪辑*html_motion_worker.mjs*') } | Select-Object ProcessId,ParentProcessId,Name,CommandLine) | ConvertTo-Json -Depth 3 -Compress"],capture_output=True,check=True)
    residual=json.loads(process.stdout.decode('utf-8-sig').strip() or '[]')
    if isinstance(residual,dict):residual=[residual]
    if not preflight:assert not residual,residual
    extra={'verification.json','encoded-static-review.png','agent-video-kit-cp313-win_amd64.zip','release-manifest.json','install-receipt.json'}
    assert {p.relative_to(PUBLIC).as_posix() for p in PUBLIC.rglob('*') if p.is_file()}=={r['path'] for r in smoke['files']}|extra
    record={'status':'passed_preflight_full_pending' if preflight else 'passed','checked_at_utc':datetime.now(timezone.utc).isoformat(),
        'generator_sha256':sha(Path(__file__)),'frozen_files':len(current),'source_freeze':current,
        'full_methods':full.get('methods'),'integration_methods':66,'new_methods':26,'main_frames':236,'stereo_sample_frames':1132800,
        'native_cli_calls':39,'native_package_files':121,'native_frames':316,'native_stereo_sample_frames':1516800,
        'skill_count':14,'skill_local_links':198,'documents':{p.relative_to(ROOT).as_posix():sha(p) for p in docs},
        'document_local_links':len(links),'fixed_toolchain_residual_processes':residual,
        'public_files':{p.relative_to(PUBLIC).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(PUBLIC.rglob('*')) if p.is_file()},
        'suite_receipt_sha256':sha(EVIDENCE/'full-final.json'),'native_receipt_sha256':sha(NATIVE/'verification.json'),
        'media_receipt_sha256':sha(EVIDENCE/'media-final.json'),'static_review_sha256':sha(EVIDENCE/'static-review.json'),
        'other_machine_accepted':False,'natural_audio_accepted':False,'full_capcut_parity_accepted':False}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:record[k] for k in ('status','frozen_files','full_methods','document_local_links','native_package_files','skill_count')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--preflight',action='store_true')
    a=p.parse_args();run(a.output.resolve(),a.preflight)
