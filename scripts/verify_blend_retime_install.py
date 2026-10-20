"""Native seven-wheel install and isolated blend-clock CLI verification."""
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


def sha(path):return 'sha256:'+hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('work','evidence','assets','wheelhouse','development'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();work=args.work.resolve();evidence=args.evidence.resolve()
    assert not work.exists() and not evidence.exists()
    assert work.is_relative_to(ROOT/'product/.runtime') and evidence.is_relative_to(ROOT/'docs')
    work.mkdir(parents=True);evidence.mkdir(parents=True)
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),'generator_sha256':sha(__file__),
        'native_windows':sys.platform=='win32','virtualization':False,'network':False,'frozen_before':frozen(),'calls':[],'checks':[]}
    def save():(evidence/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    def check(name,ok,**details):
        record['checks'].append({'name':name,'ok':bool(ok),**details});save();assert ok,name
    def run(label,command):
        command=list(map(str,command));env=dict(os.environ);temp=ROOT/'product/.runtime/temp';temp.mkdir(parents=True,exist_ok=True)
        env.update(TEMP=str(temp),TMP=str(temp),TMPDIR=str(temp),PYTHONDONTWRITEBYTECODE='1')
        result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,timeout=1200)
        for stream in ('stdout','stderr'):(evidence/(label+'.'+stream+'.log')).write_bytes(getattr(result,stream))
        record['calls'].append({'label':label,'command':command,'exit_code':result.returncode,
            'stdout_sha256':'sha256:'+hashlib.sha256(result.stdout).hexdigest(),
            'stderr_sha256':'sha256:'+hashlib.sha256(result.stderr).hexdigest()});save()
        assert result.returncode==0,label+': '+result.stdout[-2000:].decode('utf8','replace')+result.stderr[-2000:].decode('utf8','replace')
        return result.stdout
    try:
        bundle=work/'bundle';built=json.loads(run('build',[sys.executable,'-E','-B','-X','utf8',ROOT/'product/offline/build.py',
            '--output',bundle,'--wheelhouse',args.wheelhouse.resolve()]))
        record['bundle']=built;installed=work/'installed'
        record['installation']=json.loads(run('install',[sys.executable,'-I','-B','-X','utf8',bundle/'install.py',
            '--target',installed,'--manifest-sha256',built['manifest_sha256']]))
        source={p.name:p.read_bytes() for p in (ROOT/'product/src/ai_ad_editor').iterdir()
            if p.is_file() and p.suffix in {'.py','.mjs','.json','.txt'}}
        manifest=json.loads((bundle/'manifest.json').read_bytes());wheel=next(bundle/item['path'] for item in manifest['wheels'] if item['name']=='ai-ad-editor')
        with zipfile.ZipFile(wheel) as archive:
            shipped={n.split('/',1)[1]:archive.read(n) for n in archive.namelist() if n.startswith('ai_ad_editor/') and not n.endswith('/')}
        actual={p.name:p.read_bytes() for p in (installed/'site/ai_ad_editor').iterdir()
            if p.is_file() and p.suffix in {'.py','.mjs','.json','.txt'}}
        check('all-source-wheel-installed-resources-byte-equal',source==shipped==actual,resources=len(source),wheels=len(manifest['wheels']))
        check('exactly-seven-existing-wheels-no-numpy',len(manifest['wheels'])==7 and not any(w['name'].lower()=='numpy' for w in manifest['wheels']))
        check('new-model-module-shipped','blend_automation.py' in source)
        record['resource_hashes']={name:'sha256:'+hashlib.sha256(data).hexdigest() for name,data in sorted(source.items())}
        prefix=[sys.executable,'-I','-S','-B','-X','utf8',installed/'run.py']
        capabilities=json.loads(run('capabilities',[*prefix,'capabilities']));run('schema',[*prefix,'schema','show']);run('effects',[*prefix,'effects','list'])
        origins=json.loads(run('origins',[sys.executable,'-I','-S','-B','-X','utf8','-c',
            'import sys,json;sys.path.insert(0,sys.argv[1]);import ai_ad_editor.cli,ai_ad_editor.blend_automation,ai_ad_editor.effect_automation,ai_ad_editor.retime_edits,PIL.Image;'
            'print(json.dumps({m.__name__:m.__file__ for m in [ai_ad_editor.cli,ai_ad_editor.blend_automation,ai_ad_editor.effect_automation,ai_ad_editor.retime_edits,PIL.Image]}))',installed/'site']))
        check('isolated-imports-only-installed-site',all(Path(p).resolve().is_relative_to(installed/'site') for p in origins.values()),origins=origins)
        run('native-installed-demo',[sys.executable,'-E','-B','-X','utf8',ROOT/'scripts/smoke_blend_retime.py',
            '--work',work/'media','--evidence',evidence/'media','--assets',args.assets.resolve(),'--installed',installed])
        dev=json.loads(args.development.resolve().read_bytes());media=json.loads((evidence/'media/verification.json').read_bytes())
        check('development-and-installed-runs-passed',dev['status']==media['status']=='passed' and dev['frozen_equal'] and media['frozen_equal'])
        compare=('name','mode','transform','frames','fps','max_rgb_error','alpha_byte_equal','PCM_byte_equal',
                 'actual_decoded_sha256','independent_reference_sha256','author_model')
        check('all-decoded-cases-author-models-and-oracles-identical',
            [{k:x[k] for k in compare} for x in dev['cases']]==[{k:x[k] for k in compare} for x in media['cases']])
        check('every-output-frame-PTS-equal',dev['video_probes']==media['video_probes'])
        for name in ('foreground-original.nut','background-original.png','foreground-still-original.png','audio-original.wav'):
            check(name+'-exact-source-bytes',dev['public_files'][name]==media['public_files'][name])
        record.update(status='passed',isolated_cli_calls=media['cli_calls']+3,module_origin_probes=1,
            new_model_inference=0,full_capcut_parity=False)
    except BaseException as exc:
        record.update(status='failed',error={'type':type(exc).__name__,'message':str(exc)});raise
    finally:
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),frozen_after=frozen())
        record['frozen_equal']=record['frozen_before']==record['frozen_after'];save()
    assert record['frozen_equal']
    print(json.dumps({k:record[k] for k in ('status','isolated_cli_calls','module_origin_probes','frozen_equal')}))


if __name__=='__main__':main()
