"""Public upstream refresh and read-only verification of already adopted code."""
from __future__ import annotations
import argparse,hashlib,json,re,subprocess,urllib.error,urllib.request,zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REF='eefd6a8d379289102141359a4718dbab12170526'


def digest(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()


def run(output):
    output.mkdir(parents=True,exist_ok=False)
    def fetch(item):
        name,url=item;started=datetime.now(timezone.utc).isoformat();request=urllib.request.Request(url,headers={'User-Agent':'Agent-Video-Kit-source-review','Accept':'application/vnd.github+json','Cache-Control':'no-cache'})
        try:
            with urllib.request.urlopen(request,timeout=30) as response:raw=response.read(4*1024**2);status=response.status
        except urllib.error.HTTPError as exc:raw=exc.read(1024**2);status=exc.code
        except OSError as exc:raw=json.dumps({'network_error':str(exc)}).encode();status=None
        (output/(name+'.raw.json')).write_bytes(raw)
        return name,{'url':url,'started_at_utc':started,'finished_at_utc':datetime.now(timezone.utc).isoformat(),'status':status,'sha256':digest(raw),'bytes':len(raw),'body':json.loads(raw)}
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses=dict(pool.map(fetch,[('repository','https://api.github.com/repos/openfilm/openfilm'),('main','https://api.github.com/repos/openfilm/openfilm/commits/main')]))
    head=responses['main']['body'].get('sha') if responses['main']['status']==200 else None
    fallback=None
    if head is None:
        result=subprocess.run(['git','ls-remote','https://github.com/openfilm/openfilm.git','refs/heads/main'],capture_output=True,timeout=45)
        fallback={'exit_code':result.returncode,'stdout':result.stdout.decode(),'stderr':result.stderr.decode()}
        (output/'git-head.json').write_text(json.dumps(fallback,indent=2)+'\n',encoding='utf-8')
        if result.returncode==0:head=result.stdout.decode().split()[0]
    if head!=REF:
        (output/'verification.json').write_text(json.dumps({'status':'revision_requires_review','actual_head':head,'fixed_head':REF,'requests':responses},indent=2)+'\n',encoding='utf-8')
        raise RuntimeError('New or unavailable upstream head; do not claim current-source equivalence')
    archive=ROOT/'sources/upstream/openfilm-0.2.0/repo.zip'
    expected=json.loads((ROOT/'docs/validation/evidence/openfilm-refresh-20261018/verification.json').read_bytes())
    assert digest(archive.read_bytes())==expected['source_archive_sha256']
    with zipfile.ZipFile(archive) as source:
        entries=[n for n in source.namelist() if not n.endswith('/')];prefix=entries[0].split('/')[0]+'/'
        files={name[len(prefix):]:source.read(name) for name in entries}
    assert {name:digest(data) for name,data in files.items()}==expected['head_hashes'] and len(files)==702
    local=ROOT/'product/.runtime/openfilm-refresh-20261018/source'
    assert {p.relative_to(local).as_posix():digest(p.read_bytes()) for p in local.rglob('*') if p.is_file()}==expected['head_hashes']
    product=ROOT/'product/src/ai_ad_editor';checks={}
    for name,tail in [('subtitle','studio/server/subtitle-segments.mjs'),('overrides','src/overrides.mjs')]:
        path=product/('openfilm_subtitle_segments.mjs' if name=='subtitle' else 'openfilm_overrides.mjs')
        assert path.read_bytes()==files['packages/openfilm/'+tail];checks[name]={'method':'original exact bytes','sha256':digest(path.read_bytes())}
    clock=(product/'openfilm_frame_clock.mjs').read_bytes();line=re.search(rb'^export const FILM_CLOCK = .*;$',files['packages/openfilm/src/host.mjs'],re.M).group(0).rstrip(b'\r')
    assert line==re.search(rb'^export const FILM_CLOCK = .*;$',clock,re.M).group(0).rstrip(b'\r');checks['frame_clock']={'method':'original exact export','sha256':digest(clock)}
    bounds=(product/'openfilm_text_bounds.mjs').read_bytes();body=bounds[bounds.index(b'export function cutText()'):]
    assert body in files['packages/openfilm/src/shared.mjs'];checks['text_bounds']={'method':'original exact cutText function plus source header','sha256':digest(bounds),'function_bytes':len(body)}
    fields=(product/'openfilm_template_fields.mjs').read_bytes();text=files['packages/openfilm/studio/ui/src/lib/template-controls.ts'].decode()
    fragment=text[text.index('const COLOR = '):text.index('/** The clip\'s own value of a custom property')]
    for before,after in {'value: string, isColor: (v: string) => boolean = () => false): VarField':'value, isColor = () => false)','name: string, value: string): boolean':'name, value)','field: VarField): string':'field)','name: string): string':'name)','num[2]!':'num[2]','quoted[2]!':'quoted[2]','words[0]!':'words[0]'}.items():fragment=fragment.replace(before,after)
    assert fields[fields.index(b'const COLOR = '):]==fragment.encode();checks['template_fields']={'method':'four original rules; only TypeScript types/assertions removed','sha256':digest(fields)}
    assert (product/'OPENFILM_LICENSE.txt').read_bytes()==files['LICENSE']
    skills=sorted(n for n in files if n.startswith('packages/openfilm/skills/') and n.endswith('/SKILL.md'))
    record={'status':'verified','checked_at_utc':datetime.now(timezone.utc).isoformat(),'fixed_head':REF,'actual_head':head,'no_new_upstream_code':True,'requests':{name:{k:v for k,v in row.items() if k!='body'} for name,row in responses.items()},'git_head_fallback':fallback,'stars_at_api_snapshot':responses['repository']['body'].get('stargazers_count') if responses['repository']['status']==200 else None,'forks_at_api_snapshot':responses['repository']['body'].get('forks_count') if responses['repository']['status']==200 else None,'archive_sha256':digest(archive.read_bytes()),'upstream_files_checked':len(files),'mit_license_original_bytes':True,'adoptions':checks,'official_skill_paths':skills,'existing_upstream_tests':'Historical 20/20 and R01 tests were not rerun or added to product totals','new_product_feature_from_this_research':False,'product_regression':'V47 evidence reported separately after terminal completion','runtime_upstream_code_executed':False,'browser_tabs_opened':0,'virtualization':False,'script_sha256':digest(Path(__file__).read_bytes())}
    (output/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:record[k] for k in ('status','actual_head','stars_at_api_snapshot','forks_at_api_snapshot','upstream_files_checked')},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args();run(args.output.resolve())
