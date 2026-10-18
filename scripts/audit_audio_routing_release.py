"""Bind current source, real audio/media, native install, skills and release."""
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

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'docs/validation/evidence/audio-routing-20261018-v55'
PUBLIC=ROOT/'docs/assets/audio-routing-verified-20261018-v55'
NATIVE=ROOT/'docs/validation/evidence/audio-routing-native-install-verified-20261018-v55'
FINAL=EVIDENCE/'release.json'


def digest(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()
def sha(path):return digest(path.read_bytes())
def read(path):return json.loads(path.read_bytes())


def run(output,preflight=False):
    assert not output.exists()
    current=frozen();full=read(EVIDENCE/'full-verified.json');targeted=read(EVIDENCE/'targeted-verified.json')
    assert full['frozen_before']==current
    if not preflight:
        assert full['terminal_ok'] and full['exit_code']==0 and full['skipped']==0 and full['frozen_equal']
        assert full['frozen_after']==current and full['methods']==1263
    assert targeted['terminal_ok'] and targeted['exit_code']==0 and targeted['methods']==37 and targeted['skipped']==0
    assert targeted['frozen_before']==targeted['frozen_after']==current and len(current)==178
    smoke=read(PUBLIC/'verification.json');native=read(NATIVE/'verification.json');media=read(EVIDENCE/'media-verified-audit.json')
    assert smoke['status']=='passed_scoped_audio_routing' and smoke['frozen_before']==smoke['frozen_after']==current
    assert len(smoke['cases'])==6 and len(smoke['cli_calls'])==60
    assert sum(row['output_samples'] for row in smoke['cases'])==624000
    assert max(row['max_absolute_error'] for row in smoke['cases'])<=2e-6
    assert len([c for c in smoke['cli_calls'] if c['arguments'][:2]==['policy','audit']])==6
    for call in smoke['cli_calls']:
        result=PUBLIC/call['result'];assert call['exit_code']==0 and sha(result)==call['result_sha256']
        assert read(result)['ok']
    for row in smoke['files']:
        path=PUBLIC/row['path'];assert path.stat().st_size==row['bytes'] and sha(path)==row['sha256'],path
    assert media['status']=='passed_scoped_media_audit' and media['source_receipt_sha256']==sha(PUBLIC/'verification.json')
    assert media['generator_sha256']==sha(ROOT/'scripts/finalize_audio_routing_media.py')
    assert media['main_frames']==156 and media['master_stereo_sample_frames']==624000
    assert media['gif']=={'width':480,'height':270,'frames':78,'duration_ms':13000}
    combined=media['combined_exact_preview'];assert sha(PUBLIC/combined['path'])==combined['sha256']
    assert float(combined['probe']['format']['duration'])==13
    assert sha(PUBLIC/media['static_review']['path'])==media['static_review']['sha256']
    assert media['static_review']['moments_seconds']==[.5,6.5,11.5]
    assert not media['static_review']['continuous_playback'] and not media['static_review']['human_listening']
    static=read(EVIDENCE/'static-review.json')
    assert len(static['images'])==2 and not static['continuous_playback'] and not static['human_listening']
    for row in static['images']:assert sha(Path(row['path']))==row['sha256']
    assert native['status']=='passed' and native['installer_exit_code']==0 and native['isolated_cli_calls']==30
    assert native['installed_package_files']==119 and native['actual_new_frames']==204 and native['actual_new_stereo_sample_frames']==816000
    assert native['frozen_before']==native['frozen_after']==current and native['package_bytes_equal_to_wheel_and_source']
    assert native['generator_sha256']==sha(ROOT/'scripts/verify_audio_routing_native_install.py')==sha(NATIVE/'executed-generator.py')
    for call in native['calls']:
        i=call['index'];assert '-I' in call['command'] and '-S' in call['command']
        assert call['exit_code']==call['expected_exit_code'] and sha(NATIVE/f'{i:02}.stdout.json')==call['stdout_sha256']
        assert sha(NATIVE/f'{i:02}.stderr.log')==call['stderr_sha256']
    assert len([c for c in native['calls'] if c['expected_exit_code']==2])==1
    assert not native['other_machine_accepted'] and not native['listening_review'] and not native['virtual_environment']
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
            assert len(names)==119 and names==set(native['installed_files'])
            for name in names:
                raw=wheel.read(name);assert raw==(ROOT/'product/src'/name).read_bytes() and digest(raw)==native['installed_files'][name]
            assert b"'track/'" in wheel.read('ai_ad_editor/audio_routing.py')
    schema=ROOT/'docs/specs/agent-project.schema.json'
    assert schema.read_bytes()==(ROOT/'product/src/ai_ad_editor/agent-project.schema.json').read_bytes()
    assert sha(schema)==manifest['schema_sha256']
    # Keep actual failures and interrupted work distinct from successful tests.
    for name in ('targeted-first','targeted-second'):
        record=read(EVIDENCE/(name+'.json'));assert record['exit_code']==1 and not record['terminal_ok'] and record['frozen_equal']
    assert read(EVIDENCE/'targeted-first.json')['methods']==25 and read(EVIDENCE/'targeted-second.json')['methods']==34
    for name in ('full-interruption','full-final-interruption'):
        interrupted=read(EVIDENCE/(name+'.json'));assert interrupted['status']=='intentionally_interrupted_incomplete_not_passed'
        assert interrupted['owned_processes'] and 'comfy' not in json.dumps(interrupted).lower()
    with zipfile.ZipFile(EVIDENCE/'failed-policy-product.whl') as old:
        assert b"'track:'" in old.read('ai_ad_editor/audio_routing.py')
    failed_install=read(ROOT/'docs/validation/evidence/audio-routing-native-install-final-20261018-v55/27.stdout.json')
    assert not failed_install['ok'] and failed_install['errors'][0]['code']=='POLICY_REMOTE_REFERENCE'
    skills=read(EVIDENCE/'skills.json');mapping=read(ROOT/'video-cut-install-manifest.json')
    assert skills['skill_count']==14 and skills['local_links_checked']==194
    assert mapping['current_audit']['record_sha256']==sha(EVIDENCE/'skills.json')
    for row in skills['results']:
        name=row['skill'];assert name.startswith('video-cut-') and sha(ROOT/'skills'/name/'SKILL.md')==row['sha256']
        assert (Path('C:/Users/carzy/.codex/skills')/name).resolve()==(ROOT/'skills'/name).resolve()
        assert next(s for s in mapping['skills'] if s['name']==name)['skill_md_sha256']==row['sha256'][7:]
    docs=[ROOT/'README.md',ROOT/'docs/README.md',ROOT/'docs/构建进度总表_2026-10-16.md',
        ROOT/'docs/specs/AgentCLI契约_v0.1_2026-10-13.md',ROOT/'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md',
        ROOT/'docs/specs/命名音频总线发送返回与侧链契约_v0.1_2026-10-18.md',ROOT/'docs/validation/命名音频总线发送返回与侧链实测_2026-10-18.md']
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
        "@(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.Name -in @('chrome-headless-shell.exe','chrome.exe','node.exe') -and ($_.CommandLine -like '*AI广告剪辑*html-toolchain*' -or $_.CommandLine -like '*AI广告剪辑*html_motion_worker.mjs*') } | Select-Object ProcessId,ParentProcessId,Name,CommandLine) | ConvertTo-Json -Depth 3 -Compress"],
        capture_output=True,check=True)
    residual=json.loads(process.stdout.decode('utf-8-sig').strip() or '[]')
    if isinstance(residual,dict):residual=[residual]
    if not preflight:assert not residual,residual
    extra={'verification.json','audio-routing-showcase-final.mp4','encoded-static-review.png',
           'agent-video-kit-cp313-win_amd64.zip','release-manifest.json','install-receipt.json'}
    assert {p.relative_to(PUBLIC).as_posix() for p in PUBLIC.rglob('*') if p.is_file()}=={r['path'] for r in smoke['files']}|extra
    record={'status':'passed_preflight_full_pending' if preflight else 'passed','checked_at_utc':datetime.now(timezone.utc).isoformat(),
        'generator_sha256':sha(Path(__file__)),'frozen_files':len(current),'source_freeze':current,'full_methods':full.get('methods'),
        'targeted_methods':37,'main_frames':156,'stereo_sample_frames':624000,'native_cli_calls':30,'native_package_files':119,
        'skill_count':14,'skill_local_links':194,'documents':{p.relative_to(ROOT).as_posix():sha(p) for p in docs},
        'document_local_links':len(links),'fixed_toolchain_residual_processes':residual,
        'public_files':{p.relative_to(PUBLIC).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(PUBLIC.rglob('*')) if p.is_file()},
        'suite_receipt_sha256':sha(EVIDENCE/'full-verified.json'),'native_receipt_sha256':sha(NATIVE/'verification.json'),
        'media_receipt_sha256':sha(EVIDENCE/'media-verified-audit.json'),'other_machine_accepted':False,'natural_audio_accepted':False,'full_capcut_parity_accepted':False}
    record['static_review_sha256']=sha(EVIDENCE/'static-review.json')
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:record[k] for k in ('status','frozen_files','full_methods','document_local_links','native_package_files','skill_count')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--preflight',action='store_true')
    args=p.parse_args();run(args.output.resolve(),args.preflight)
