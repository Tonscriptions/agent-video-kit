"""Check release evidence, original adoption bytes and current documentation links."""
import argparse,hashlib,io,json,re,urllib.parse,zipfile
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def read(path):return json.loads((ROOT/path).read_bytes())


def run(output):
    assert not output.exists()
    full=read('docs/validation/evidence/stroke-tests-20261018/full.json')
    assert full['exit_code']==0 and full['terminal_ok'] and full['skipped']==0 and full['frozen_equal']
    assert full['methods']==1107 and len(full['frozen_after'])==165
    assert full['frozen_before']==full['frozen_after']
    assert all(sha(ROOT/k)==v for k,v in full['frozen_after'].items())
    assert full['log_sha256']==sha(ROOT/'docs/validation/evidence/stroke-tests-20261018/full.log')
    adoption=read('docs/validation/evidence/openfilm-stroke-adoption-20261018/verification.json')
    original=(ROOT/'docs/validation/evidence/openfilm-examples-review-final-20261018/px/stroke.js').read_bytes()
    piece=original[adoption['extracted_offset']:]
    assert len(piece)==1417 and hashlib.sha256(piece).hexdigest()==adoption['extracted_sha256']
    current=(ROOT/'product/src/ai_ad_editor/openfilm_stroke.mjs').read_bytes()
    assert current.endswith(piece) and hashlib.sha256(current).hexdigest()==adoption['target_sha256']
    for name,source in [('OPENFILM_EXAMPLES_LICENSE.txt','docs/validation/evidence/openfilm-examples-review-final-20261018/LICENSE.raw.txt'),
                        ('PDOOM_VIDEO_LICENSE.txt','docs/validation/evidence/openfilm-examples-review-final-20261018/px/LICENSE-pdoom-video.txt')]:
        assert (ROOT/'product/src/ai_ad_editor'/name).read_bytes()==(ROOT/source).read_bytes()
    real=read('docs/validation/evidence/stroke-real-verified-20261018/verification.json')
    assert real['status']=='passed' and real['frozen_before']==real['frozen_after']==full['frozen_after']
    assert real['calls']==17 and real['primary_html_frames']==108 and real['geometry_min_coverage']==1
    assert real['generator_sha256']==sha(ROOT/'docs/validation/evidence/stroke-real-verified-20261018/executed-generator.py')
    wheel=read('docs/validation/evidence/stroke-wheel-final-20261018/verification.json')
    assert wheel['package_file_count']==112 and wheel['fresh_process_cli_calls']==12 and len(wheel['runtime_dependencies'])==5
    assert all(sha(ROOT/'product/src'/row['path'])==row['sha256'] for row in wheel['package_files'])
    native=read('docs/validation/evidence/stroke-native-install-final-20261018/verification.json')
    assert native['status']=='passed' and native['cli_calls']==6 and native['frames']==36
    for data in (real,wheel):
        for item in data['browser_reports']:
            assert item['cleanup']['all_children_reaped'] and not item['cleanup']['active_after_cleanup']
            assert item['worker']['pages_opened']==item['worker']['pages_closed'] and item['worker']['browser_closed']
    public=ROOT/'docs/assets/stroke-motion-verified-20261018'
    release=read('docs/assets/stroke-motion-verified-20261018/release-manifest.json')
    assert sha(public/'agent-video-kit-cp313-win_amd64.zip')==native['release_zip_sha256']
    with zipfile.ZipFile(public/'agent-video-kit-cp313-win_amd64.zip') as archive:
        assert archive.read('manifest.json')==(public/'release-manifest.json').read_bytes()
        for row in release['files']:
            raw=archive.read(row['path']);assert len(raw)==row['bytes'] and 'sha256:'+hashlib.sha256(raw).hexdigest()==row['sha256']
        own=next(row for row in release['wheels'] if row['name']=='ai-ad-editor')
        with zipfile.ZipFile(io.BytesIO(archive.read(own['path']))) as product:
            names=[n for n in product.namelist() if n.startswith('ai_ad_editor/')]
            assert len(names)==112
            for name in names:assert product.read(name)==(ROOT/'product/src'/name).read_bytes()
    media=read('docs/validation/evidence/stroke-media-final-20261018.json')
    assert media['gif']['frames']==16 and media['gif']['total_duration_ms']==2970
    for path,row in media['files'].items():assert sha(ROOT/path)==row['sha256']
    skills=read('docs/validation/evidence/stroke-skills-20261018.json');manifest=read('video-cut-install-manifest.json')
    assert skills['skill_count']==14 and skills['local_links_checked']==164
    assert manifest['current_audit']['record_sha256']==sha(ROOT/'docs/validation/evidence/stroke-skills-20261018.json')
    for row in manifest['skills']:assert sha(ROOT/'skills'/row['name']/'SKILL.md')=='sha256:'+row['skill_md_sha256']
    documents=[ROOT/'README.md',ROOT/'AGENTS.md',*sorted((ROOT/'docs').rglob('*.md'))]
    local=0;broken=[]
    for path in documents:
        text=path.read_text(encoding='utf-8-sig');assert text.strip(),path
        text=re.sub(r'^\s*```.*?^\s*```[^\n]*','',text,flags=re.M|re.S)
        for raw in re.findall(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^\"]*")?\)',text):
            target=raw.strip('<>')
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',target) and not re.match(r'^[A-Za-z]:[/\\]',target):continue
            target=target.split('#',1)[0]
            if not target:continue
            local+=1
            if not (path.parent/urllib.parse.unquote(target)).resolve().exists():broken.append({'document':str(path),'target':target})
    assert not broken,broken
    readme=(ROOT/'README.md').read_text(encoding='utf-8')
    assert list(map(int,re.findall(r'^\| V(\d{2}) \|',readme,re.M)))==list(range(1,49))
    assert readme.index('V48（产品）')<readme.index('V47（产品）')
    assert '完整 **1107/1107**' in readme and '2,970 ms' in readme and 'V48' in readme.split('## 当前状态')[1]
    out={'status':'passed','checked_at_utc':datetime.now(timezone.utc).isoformat(),'documents':len(documents),'local_links':local,
        'full_methods':1107,'frozen_files':165,'source_adoptions_original_bytes':True,'package_files':112,
        'real_cli_calls':17,'wheel_cli_calls':12,'installed_cli_calls':6,'skills':14,'skill_links':164,
        'real_frames':108,'actual_gif_frames':16,'continuous_playback_review':False,'generator_sha256':sha(Path(__file__))}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:out[k] for k in ('status','documents','local_links','full_methods','frozen_files')}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output.resolve())
