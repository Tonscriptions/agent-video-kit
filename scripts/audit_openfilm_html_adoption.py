"""Public upstream snapshot and byte-exact clock extraction; no upstream code runs."""
from __future__ import annotations
import argparse,hashlib,json,re,urllib.request,zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
from smoke_fragments import save,sha

ROOT=Path(__file__).resolve().parents[1]
COMMIT='eefd6a8d379289102141359a4718dbab12170526'


def run(output):
    output.mkdir(parents=True,exist_ok=False)
    started=datetime.now(timezone.utc).isoformat()
    def fetch(item):
        name,url=item
        request=urllib.request.Request(url,headers={'User-Agent':'agent-video-kit-source-review','Accept':'application/vnd.github+json'})
        with urllib.request.urlopen(request,timeout=30) as response:
            data=response.read()
            (output/(name+'.raw.json')).write_bytes(data)
            return name,json.loads(data)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses=dict(pool.map(fetch,[('repository','https://api.github.com/repos/openfilm/openfilm'),
                                      ('main','https://api.github.com/repos/openfilm/openfilm/commits/main')]))
    archive=ROOT/'sources/upstream/openfilm-0.2.0/repo.zip'
    local=ROOT/'product/.runtime/openfilm-refresh-20261018/source'
    host_name='packages/openfilm/src/host.mjs';matched=0
    with zipfile.ZipFile(archive) as source:
        assert source.testzip() is None
        host_member=next(i.filename for i in source.infolist() if i.filename.endswith('/'+host_name))
        prefix=host_member[:-len(host_name)]
        for info in source.infolist():
            if info.is_dir():continue
            assert info.filename.startswith(prefix)
            path=local/info.filename[len(prefix):]
            assert path.is_file() and path.read_bytes()==source.read(info)
            matched+=1
        host=source.read(host_member)
        license_bytes=source.read(prefix+'LICENSE')
    assert matched==702,matched
    line=re.search(rb'^export const FILM_CLOCK = .*;$',host,re.M).group(0).rstrip(b'\r')
    extracted=(ROOT/'product/src/ai_ad_editor/openfilm_frame_clock.mjs').read_bytes()
    actual=re.search(rb'^export const FILM_CLOCK = .*;$',extracted,re.M).group(0).rstrip(b'\r')
    assert actual==line
    assert (ROOT/'product/src/ai_ad_editor/OPENFILM_LICENSE.txt').read_bytes()==license_bytes
    record={'status':'passed','checked_at_utc':started,'fixed_commit':COMMIT,'upstream_main':responses['main']['sha'],
        'main_unchanged':responses['main']['sha']==COMMIT,'stars_at_api_snapshot':responses['repository']['stargazers_count'],
        'forks_at_api_snapshot':responses['repository']['forks_count'],'api_raw':{n:{'sha256':sha(output/(n+'.raw.json'))} for n in responses},
        'fixed_source_archive_sha256':sha(archive),'upstream_files_equal':matched,'original_host_sha256':'sha256:'+hashlib.sha256(host).hexdigest(),
        'export_line_sha256':'sha256:'+hashlib.sha256(line).hexdigest(),'export_line_bytes':len(line),'clock_export_exact':True,
        'adopted_module_sha256':sha(ROOT/'product/src/ai_ad_editor/openfilm_frame_clock.mjs'),'mit_license_exact':True,
        'adoption':'only original clock export; native orchestration/resource closure/CLI/process lifetime are new or workflow adaptations',
        'upstream_studio_or_render_executed':False,'browser_tabs_opened':0,'generator_sha256':sha(Path(__file__))}
    save(output/'verification.json',record)
    print(json.dumps({k:record[k] for k in ('upstream_main','main_unchanged','stars_at_api_snapshot','forks_at_api_snapshot','upstream_files_equal','export_line_bytes')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();run(args.output.resolve())
