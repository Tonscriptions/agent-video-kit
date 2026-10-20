"""Build seven offline wheels and repeat shutter CLI in a fresh isolated install."""
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

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return 'sha256:' + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('work','evidence','assets','runtime','wheelhouse','development'):
        parser.add_argument('--'+name,required=True,type=Path)
    args=parser.parse_args();work=args.work.resolve();evidence=args.evidence.resolve()
    assert not work.exists() and not evidence.exists()
    work.mkdir(parents=True);evidence.mkdir(parents=True)
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),
            'script_sha256':digest(__file__),'native_windows':sys.platform=='win32','virtualization':False,
            'frozen_before':frozen(),'calls':[],'checks':[],'full_capcut_parity':False,'new_model_inference':0}

    def save():
        (evidence/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')

    def check(name,ok,**details):
        record['checks'].append({'name':name,'ok':bool(ok),**details});save()
        if not ok:raise AssertionError(name)

    def run(label,argv):
        command=list(map(str,argv));env=dict(os.environ)
        env.update(TEMP=str(ROOT/'product/.runtime/temp'),TMP=str(ROOT/'product/.runtime/temp'),
                   TMPDIR=str(ROOT/'product/.runtime/temp'),PYTHONDONTWRITEBYTECODE='1')
        result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,timeout=1200)
        for stream in ('stdout','stderr'):(evidence/(label+'.'+stream+'.log')).write_bytes(getattr(result,stream))
        record['calls'].append({'label':label,'command':command,'exit_code':result.returncode,
                                'stdout_sha256':'sha256:'+hashlib.sha256(result.stdout).hexdigest(),
                                'stderr_sha256':'sha256:'+hashlib.sha256(result.stderr).hexdigest()});save()
        if result.returncode:raise AssertionError(label+': '+result.stdout[-1200:].decode('utf8','replace')+result.stderr[-1200:].decode('utf8','replace'))
        return result.stdout

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
        wheel=next(bundle/item['path'] for item in manifest['wheels'] if item['name']=='ai-ad-editor')
        with zipfile.ZipFile(wheel) as archive:
            shipped={n.split('/',1)[1]:archive.read(n) for n in archive.namelist() if n.startswith('ai_ad_editor/') and not n.endswith('/')}
        actual={p.name:p.read_bytes() for p in (installed/'site/ai_ad_editor').iterdir()
                if p.is_file() and p.suffix in {'.py','.mjs','.json','.txt'}}
        check('source-wheel-installed-all-bytes-equal',source==shipped==actual,resources=len(source),wheels=len(manifest['wheels']))
        check('no-new-numpy-or-cloud-wheel',len(manifest['wheels'])==7 and not any(item['name'].lower()=='numpy' for item in manifest['wheels']))
        record['resource_hashes']={name:'sha256:'+hashlib.sha256(data).hexdigest() for name,data in sorted(source.items())}
        prefix=[sys.executable,'-I','-S','-B','-X','utf8',installed/'run.py']
        for label,argv in [('capabilities',['capabilities']),('schema',['schema','show']),('render-help',['motion','html-render','--help'])]:
            run(label,[*prefix,*argv])
        origins=json.loads(run('module-origins',[sys.executable,'-I','-S','-B','-X','utf8','-c',
            'import sys,json;sys.path.insert(0,sys.argv[1]);import ai_ad_editor.cli,ai_ad_editor.html_motion,ai_ad_editor.html_shutter,PIL.ImageMath;'
            'print(json.dumps({m.__name__:m.__file__ for m in [ai_ad_editor.cli,ai_ad_editor.html_motion,ai_ad_editor.html_shutter,PIL.ImageMath]}))',installed/'site']))
        check('fresh-interpreter-imports-only-installed-modules',all(Path(p).resolve().is_relative_to(installed/'site') for p in origins.values()),origins=origins)
        run('installed-native-shutter',[sys.executable,'-E','-B','-X','utf8',ROOT/'scripts/smoke_html_shutter.py',
            '--work',work/'media','--evidence',evidence/'media','--assets',args.assets.resolve(),
            '--runtime',args.runtime.resolve(),'--installed',installed])
        development=read(args.development.resolve());media=read(evidence/'media/verification.json')
        check('both-real-native-runs-passed',development['status']==media['status']=='passed' and development['frozen_equal'] and media['frozen_equal'])
        check('independent-reference-frames-equal',development['independent_reference_rgba_sha256']==media['independent_reference_rgba_sha256'])
        for name,left in development['renders'].items():
            right=media['renders'][name]
            for field in ('frame_rgba_sha256','source_capture_count','encoded_clock'):
                check(name+'-'+field+'-matches-development',left[field]==right[field])
            check(name+'-saved-shutter-config-identical',left['asset']['html_motion']['shutter']==right['asset']['html_motion']['shutter'])
        check('all-public-input-output-bytes-identical',development['public_files']==media['public_files'])
        record.update(status='passed',isolated_cli_calls=media['cli_calls']+3,module_origin_probes=1,
                      external_runtime_not_bundled=['Python','FFmpeg','Node','playwright-core','Chromium','Windows system DLLs'])
    except BaseException as exc:
        record.update(status='failed',error={'type':type(exc).__name__,'message':str(exc)})
        raise
    finally:
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),frozen_after=frozen())
        record['frozen_equal']=record['frozen_before']==record['frozen_after'];save()
    assert record['frozen_equal']
    print(json.dumps({k:record[k] for k in ('status','isolated_cli_calls','module_origin_probes','frozen_equal')}))


if __name__=='__main__':main()
