"""Build seven local wheels, isolate installation and repeat native contact CLI."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_bytes())


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('work','evidence','assets','wheelhouse','source','preview','source-origin','development'):
        p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args();work=args.work.resolve();evidence=args.evidence.resolve()
    assert not work.exists() and not evidence.exists();work.mkdir(parents=True);evidence.mkdir(parents=True)
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),'script_sha256':sha(__file__),
        'native_windows':sys.platform=='win32','virtualization':False,'frozen_before':frozen(),
        'calls':[],'checks':[],'goal_complete':False,'full_capcut_parity':False}
    def save():(evidence/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    def check(name,ok,**details):
        record['checks'].append({'name':name,'ok':bool(ok),**details});save()
        if not ok:raise AssertionError(name)
    def run(label,command):
        command=list(map(str,command));env=dict(os.environ)
        env.update(TEMP=str(ROOT/'product/.runtime/temp'),TMP=str(ROOT/'product/.runtime/temp'),
            TMPDIR=str(ROOT/'product/.runtime/temp'),PYTHONDONTWRITEBYTECODE='1')
        r=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,timeout=1200)
        for stream in ('stdout','stderr'):(evidence/(label+'.'+stream+'.log')).write_bytes(getattr(r,stream))
        record['calls'].append({'label':label,'command':command,'exit_code':r.returncode,
            'stdout_sha256':hashlib.sha256(r.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(r.stderr).hexdigest()});save()
        if r.returncode:raise AssertionError(label+': '+r.stderr[-1500:].decode('utf8','replace'))
        return r.stdout
    try:
        bundle=work/'bundle'
        built=json.loads(run('build',[sys.executable,'-B','-X','utf8',ROOT/'product/offline/build.py',
            '--output',bundle,'--wheelhouse',args.wheelhouse.resolve()]))
        record['bundle']=built
        installed=work/'installed'
        record['installation']=json.loads(run('install',[sys.executable,'-I','-B','-X','utf8',bundle/'install.py',
            '--target',installed,'--manifest-sha256',built['manifest_sha256']]))
        source={p.name:p.read_bytes() for p in (ROOT/'product/src/ai_ad_editor').iterdir()
            if p.is_file() and p.suffix in {'.py','.mjs','.json','.txt'}}
        manifest=read(bundle/'manifest.json')
        wheel=next(bundle/r['path'] for r in manifest['wheels'] if r['name']=='ai-ad-editor')
        with zipfile.ZipFile(wheel) as z:
            shipped={n.split('/',1)[1]:z.read(n) for n in z.namelist() if n.startswith('ai_ad_editor/') and not n.endswith('/')}
        actual={p.name:p.read_bytes() for p in (installed/'site/ai_ad_editor').iterdir()
            if p.is_file() and p.suffix in {'.py','.mjs','.json','.txt'}}
        check('source-wheel-installed-exact',source==shipped==actual,resources=len(source),wheels=len(manifest['wheels']))
        record['resource_hashes']={k:hashlib.sha256(v).hexdigest() for k,v in sorted(source.items())}
        prefix=[sys.executable,'-I','-S','-B','-X','utf8',installed/'run.py']
        for label,argv in (('capabilities',['capabilities']),('schema',['schema','show']),('contact-help',['media','contact-sheet','--help'])):
            run(label,[*prefix,*argv])
        origins=json.loads(run('module-origins',[sys.executable,'-I','-S','-B','-X','utf8','-c',
            'import sys,json;sys.path.insert(0,sys.argv[1]);import ai_ad_editor.cli,ai_ad_editor.contact_sheet;'
            'print(json.dumps({m.__name__:m.__file__ for m in [ai_ad_editor.cli,ai_ad_editor.contact_sheet]}))',installed/'site']))
        check('isolated-imports-under-install',all(Path(v).resolve().is_relative_to(installed/'site') for v in origins.values()),origins=origins)
        run('actual-installed-media',[sys.executable,'-B','-X','utf8',ROOT/'scripts/smoke_contact_sheet.py',
            '--work',work/'media','--evidence',evidence/'media','--assets',args.assets.resolve(),
            '--source',args.source.resolve(),'--preview',args.preview.resolve(),'--source-origin',args.source_origin.resolve(),
            '--installed',installed])
        development=read(args.development.resolve());media=read(evidence/'media/verification.json')
        check('both-native-runs-passed',development['status']==media['status']=='passed' and development['frozen_equal'] and media['frozen_equal'])
        check('whole-source-decoded-frame-identities-match',development['source_frame_rgba_sha256']==media['source_frame_rgba_sha256'])
        left,right=development['contact_manifest'],media['contact_manifest']
        check('contact-png-byte-identical',left['contact']['sha256']==right['contact']['sha256'])
        check('embedded-annotation-font-identical',left['annotation_font']==right['annotation_font'])
        for i,(a,b) in enumerate(zip(left['frames'],right['frames'],strict=True)):
            for field in ('png_sha256','rgba_sha256','alpha_sha256','alpha_extrema','relative_seconds',
                          'source_pts_seconds_rational','source_time_base','panels'):
                check(f'frame-{i}-{field}-matches-development',a[field]==b[field])
        record.update(status='passed',isolated_cli_calls=media['cli_calls']+3,module_origin_probes=1,
            all_source_and_png_equal_development=True,no_external_dependencies_bundled=['Python','FFmpeg','system DLLs'])
    except BaseException as exc:
        record.update(status='failed',error={'type':type(exc).__name__,'message':str(exc)})
        raise
    finally:
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),frozen_after=frozen())
        record['frozen_equal']=record['frozen_before']==record['frozen_after'];save()
    if not record['frozen_equal']:raise AssertionError('product bytes changed')
    print(json.dumps({k:record[k] for k in ('status','isolated_cli_calls','module_origin_probes','frozen_equal')}))


if __name__=='__main__':main()
