"""Bind V65 terminal regression, real media, offline package and document bytes."""
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
import urllib.parse
import zipfile
from run_frozen_regression import frozen
from sync_hardware_acceleration_documents import ROOT, BASE, REPORT, CONTRACT


def sha(p):
    with p.open('rb') as stream: return 'sha256:'+hashlib.file_digest(stream,'sha256').hexdigest()
def read(p):return json.loads(p.read_bytes())
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    output=parser.parse_args().output.resolve();assert not output.exists()
    current=frozen();files={};counts={}
    def bind(path):
        assert path.is_file(),str(path)
        files[path.relative_to(ROOT).as_posix()]={'sha256':sha(path),'bytes':path.stat().st_size}
    def same(v):return v['frozen_equal'] and v['frozen_before']==v['frozen_after']==current
    def calls(folder,rows):
        for row in rows:
            for key in ('stdout','stderr'):
                p=folder/row[key];assert sha(p)==row[key+'_sha256'];bind(p)
            expected=row.get('expected_exit',0)
            assert (row['exit_code']!=0 if expected=='nonzero' else row['exit_code']==expected),row['id']
    full=read(BASE/'full-r1.json');unit=read(BASE/'subset-r6.json')
    for name,v,count in [('full-r1',full,1430),('subset-r6',unit,20)]:
        assert same(v) and v['terminal_ok'] and v['exit_code']==0 and v['skipped']==0 and v['methods']==count
        assert sha(BASE/(name+'.log'))==v['log_sha256'];bind(BASE/(name+'.json'));bind(BASE/(name+'.log'))
    assert len(current)==198
    media=[]
    for folder in (BASE/'development-r6',BASE/'installed-r1/media'):
        v=read(folder/'verification.json');assert same(v) and v['status']=='completed'
        assert v['cli_calls']==20 and len(v['artifacts'])==8 and len(v['checks'])==49 and all(x['passed'] for x in v['checks'])
        assert sum(a['frames'] for a in v['artifacts'])==384 and sum(a['audio_sample_frames'] for a in v['artifacts'])==768000
        calls(folder,v['calls']);bind(folder/'verification.json');bind(folder/'executed-generator.py')
        for artifact in v['artifacts']:
            path=ROOT/artifact['path'];assert sha(path)==artifact['sha256'];bind(path)
            manifest_path=folder/(artifact['id']+'.manifest.json');manifest=read(manifest_path)
            command=manifest['command'];transport=manifest['filter_graph_transport']
            # These bounded real cases use inline transport. Its hash covers the
            # actual hwdownload wrapper; filter_complex retains the logical graph.
            assert '-filter_complex' in command
            executed_graph=command[command.index('-filter_complex')+1]
            assert 'sha256:'+hashlib.sha256(executed_graph.encode('utf8')).hexdigest()==transport['sha256']
            if manifest['acceleration'].get('selected_decoders'):
                assert 'hwdownload' in executed_graph and executed_graph!=manifest['filter_complex']
            bind(manifest_path)
        asset_folder=(ROOT/v['artifacts'][0]['path']).parent
        provenance=read(asset_folder/'provenance.json');assert provenance['license']=='CC0-1.0'
        for name,entry in provenance['files'].items():
            p=asset_folder/name;assert sha(p)==entry['sha256'] and p.stat().st_size==entry['bytes'];bind(p)
        bind(asset_folder/'provenance.json')
        for path in folder.rglob('report.json'):
            report=read(path)
            for command in report['probes']+report['attempts']:
                if command['status']=='completed':
                    for key in ('stdout','stderr'):
                        log=path.parent/Path(command[key]['path']).name
                        assert sha(log).split(':',1)[1]==command[key]['sha256'].removeprefix('sha256:');bind(log)
                else: assert command['stderr_scope']=='partial executor tail'
            if report['request']['encode']=='require':
                assert all(a.get('encoder')!='libx264' for a in report['attempts'])
            if report['request']['decode']=='require':
                assert all(bool(a.get('decoders')) for a in report['attempts'])
            bind(path)
        media.append(v)
    installed=read(BASE/'installed-r1/verification.json');assert same(installed) and installed['status']=='passed'
    assert installed['packaged_files']==132 and installed['isolated_cli_calls']==22 and len(installed['comparisons'])==8
    assert all(x['decoded_video_equal'] and x['decoded_pcm_equal'] for x in installed['comparisons'])
    calls(BASE/'installed-r1',installed['calls']);bind(BASE/'installed-r1/verification.json');bind(BASE/'installed-r1/executed-install-check.py')
    assets=(ROOT/media[1]['artifacts'][0]['path']).parent
    for name,digest in installed['release'].items(): assert sha(assets/'release'/name)==digest;bind(assets/'release'/name)
    with zipfile.ZipFile(assets/'release/agent-video-kit-cp313-win_amd64.zip') as archive:
        manifest=read(assets/'release/manifest.json');assert archive.read('manifest.json')==(assets/'release/manifest.json').read_bytes()
        for entry in manifest['files']:
            payload=archive.read(entry['path']);assert len(payload)==entry['bytes'] and 'sha256:'+hashlib.sha256(payload).hexdigest()==entry['sha256']
        own=next(w for w in manifest['wheels'] if w['name']=='ai-ad-editor')
        with zipfile.ZipFile(io.BytesIO(archive.read(own['path']))) as wheel:
            names=[n for n in wheel.namelist() if n.startswith('ai_ad_editor/') and not n.endswith('/')]
            assert len(names)==132
            for name in names: assert wheel.read(name)==(ROOT/'product/src'/name).read_bytes()
            assert wheel.read('ai_ad_editor/OPENFILM_LICENSE.txt')==(ROOT/'sources/upstream/openfilm-refresh-20261019-r07/LICENSE').read_bytes()
    audit=read(BASE/'media-audit-r3/verification.json');assert audit['status']=='passed_scoped_media_audit'
    assert audit['gif_frames']==16 and audit['gif_duration_ms']==2010 and audit['preview_frames_separate']==96
    assert audit['lossless_h264_d3d11_negative'] and audit['lossless_h264_cuda_cpu_four_frames_equal']
    calls(BASE/'media-audit-r3',audit['calls']);bind(BASE/'media-audit-r3/verification.json');bind(BASE/'media-audit-r3/static-review.json')
    review=read(BASE/'media-audit-r3/static-review.json');assert review['reviewed_static_frames']==6 and not review['continuous_playback'] and not review['audio_listened']
    preview=ROOT/'docs/assets/hardware-acceleration-20261019-v65-r6/preview-r3'
    for name,entry in read(preview/'provenance.json')['files'].items():assert sha(preview/name)==entry['sha256'];bind(preview/name)
    bind(preview/'provenance.json')
    skills=read(BASE/'skills-r1.json');mapping=read(ROOT/'video-cut-install-manifest.json')
    assert skills['skill_count']==mapping['skill_count']==17 and skills['local_links_checked']==235
    for row in skills['results']:
        p=ROOT/'skills'/row['skill']/'SKILL.md';entry=next(x for x in mapping['skills'] if x['name']==row['skill'])
        assert sha(p)==row['sha256']=='sha256:'+entry['skill_md_sha256'] and row['validator_exit_code']==0
        assert (Path('C:/Users/carzy/.codex/skills')/row['skill']).resolve()==p.parent.resolve();bind(p)
    bind(BASE/'skills-r1.json');bind(ROOT/'video-cut-install-manifest.json')
    docs=[ROOT/'README.md',ROOT/'docs/README.md',ROOT/'docs/validation'/REPORT,ROOT/'docs/specs'/CONTRACT,
        ROOT/'docs/构建进度总表_2026-10-16.md',ROOT/'docs/产品需求与开发路线基线_2026-10-12.md',
        ROOT/'docs/产品实现入口与P0使用说明_v0.1_2026-10-13.md',ROOT/'docs/specs/AgentCLI契约_v0.1_2026-10-13.md',
        ROOT/'docs/validation/README功能核验与实测演示_2026-10-16.md',ROOT/'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md',
        ROOT/'docs/third-party/OpenFilm复用声明_2026-10-17.md',ROOT/'docs/OpenFilm当前复用决策_2026-10-18.md',
        ROOT/'docs/OpenFilm_0.2.1复用清单与成本复核_2026-10-19.md']
    links=0
    for path in docs:
        text=path.read_text(encoding='utf8')
        assert not re.search(r'\b(?:TODO|TBD|待填写)\b',text[:1000])
        for raw in re.findall(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^\"]*")?\)',text):
            target=raw.strip('<>').split('#',1)[0]
            if not target or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',target):continue
            resolved=(path.parent/urllib.parse.unquote(target)).resolve();assert resolved.exists() or resolved==output,(path,target)
            links+=1
        bind(path)
    for p in ROOT.glob('scripts/*hardware_acceleration*.py'):ast.parse(p.read_text(encoding='utf8'));bind(p)
    # Historical failures and experiments retain their exact raw bytes without being counted as current green tests.
    for folder in [BASE,*[p for p in (ROOT/'docs/assets').glob('hardware-acceleration-20261019-v65-*') if p.is_dir()]]:
        for p in folder.rglob('*'):
            if p.is_file() and p!=output:bind(p)
    counts.update(full_methods=1430,new_subset=20,frozen_files=198,development_cli=20,development_frames=384,
        installed_cli=22,packaged_files=132,skills=17,skill_links=235,document_links=links,bound_files=len(files))
    save(output,{'status':'passed','checked_at_utc':datetime.now(timezone.utc).isoformat(),'counts':counts,
        'frozen_before':current,'frozen_after':frozen(),'frozen_equal':current==frozen(),'files':files})
    print(json.dumps(counts))


if __name__=='__main__':main()
