"""Install seven offline wheels, verify native platform tag and all 153 resources, repeat HSL."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
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
        assert result.returncode==0,label+': '+result.stdout[-1600:].decode('utf8','replace')+result.stderr[-1600:].decode('utf8','replace')
        return result.stdout
    try:
        bundle=work/'bundle';built=json.loads(run('build',[sys.executable,'-E','-B','-X','utf8',ROOT/'product/offline/build.py',
            '--output',bundle,'--wheelhouse',args.wheelhouse.resolve()]))
        record['bundle']=built;installed=work/'installed'
        record['installation']=json.loads(run('install',[sys.executable,'-I','-B','-X','utf8',bundle/'install.py',
            '--target',installed,'--manifest-sha256',built['manifest_sha256']]))
        source={p.name:p.read_bytes() for p in (ROOT/'product/src/ai_ad_editor').iterdir()
            if p.is_file() and p.suffix in {'.py','.mjs','.json','.txt','.c','.dll'}}
        manifest=json.loads((bundle/'manifest.json').read_bytes());wheel=next(bundle/item['path'] for item in manifest['wheels'] if item['name']=='ai-ad-editor')
        with zipfile.ZipFile(wheel) as archive:
            metadata=archive.read(next(n for n in archive.namelist() if n.endswith('.dist-info/WHEEL'))).decode('utf8')
            check('platform-wheel-py3-none-win_amd64',wheel.name.endswith('-py3-none-win_amd64.whl') and 'Root-Is-Purelib: false' in metadata and 'Tag: py3-none-win_amd64' in metadata,wheel=wheel.name,metadata=metadata)
            prefixes=('ai_ad_editor/','ai_ad_editor-0.1.0.data/purelib/ai_ad_editor/')
            shipped={}
            for n in archive.namelist():
                for prefix in prefixes:
                    if n.startswith(prefix) and not n.endswith('/'):
                        name=n[len(prefix):];assert '/' not in name and name not in shipped
                        shipped[name]=archive.read(n)
        actual={p.name:p.read_bytes() for p in (installed/'site/ai_ad_editor').iterdir()
            if p.is_file() and p.suffix in {'.py','.mjs','.json','.txt','.c','.dll'}}
        check('all-source-wheel-installed-resources-byte-equal',source==shipped==actual,resources=len(source),wheel_resources=len(shipped),installed_resources=len(actual),
            missing_from_wheel=sorted(source.keys()-shipped.keys()),missing_from_installed=sorted(source.keys()-actual.keys()),wheels=len(manifest['wheels']))
        assert len(source)==153
        check('seven-existing-wheels-no-numpy',len(manifest['wheels'])==7 and not any(w['name'].lower()=='numpy' for w in manifest['wheels']))
        record['resource_hashes']={name:'sha256:'+hashlib.sha256(data).hexdigest() for name,data in sorted(source.items())}
        prefix=[sys.executable,'-I','-S','-B','-X','utf8',installed/'run.py']
        capabilities=json.loads(run('capabilities',[*prefix,'capabilities']))
        run('schema',[*prefix,'schema','show']);catalog=json.loads(run('effects',[*prefix,'effects','list']))
        check('installed-catalog-version',catalog['data']['catalog_version']=='0.8.1')
        automation=capabilities['data']['capabilities']['effects']['numeric_effect_automation']
        check('installed-ten-command-families-and-selective-HSL',automation['numeric_channels']==34 and len(automation['effects'])==10 and capabilities['data']['capabilities']['effects']['selective_hsl']['numeric_channels']==25)
        origins=json.loads(run('origins',[sys.executable,'-I','-S','-B','-X','utf8','-c',
            'import sys,json;sys.path.insert(0,sys.argv[1]);import ai_ad_editor.cli,ai_ad_editor.effect_automation,ai_ad_editor.effects,ai_ad_editor.render,ai_ad_editor.selective_hsl,ai_ad_editor.hsl_native,ai_ad_editor.hsl_program,PIL.Image;'
            'print(json.dumps({m.__name__:m.__file__ for m in [ai_ad_editor.cli,ai_ad_editor.effect_automation,ai_ad_editor.effects,ai_ad_editor.render,ai_ad_editor.selective_hsl,ai_ad_editor.hsl_native,ai_ad_editor.hsl_program,PIL.Image]}))',installed/'site']))
        check('isolated-imports-only-installed-site',all(Path(p).resolve().is_relative_to(installed/'site') for p in origins.values()),origins=origins)
        run('native-installed-demo',[sys.executable,'-E','-B','-X','utf8',ROOT/'scripts/smoke_native_hsl.py',
            '--work',work/'media','--evidence',evidence/'media','--assets',args.assets.resolve(),'--installed',installed])
        dev=json.loads(args.development.resolve().read_bytes());media=json.loads((evidence/'media/verification.json').read_bytes())
        check('development-and-installed-passed',dev['status']==media['status']=='passed' and dev['frozen_equal'] and media['frozen_equal'])
        keys=('name','effect','frames','fps','max_rgb_error','alpha_byte_equal','PCM_byte_equal','actual_decoded_sha256','independent_reference_sha256','kernel_metadata')
        check('all-decoded-cases-and-independent-oracles-identical',
            [{k:x[k] for k in keys} for x in dev['cases']]==[{k:x[k] for k in keys} for x in media['cases']])
        check('every-output-frame-PTS-equal',dev['video_probes']==media['video_probes'])
        for name in ('foreground-original.png','background-original.png','audio-original.wav','source-preview.png'):
            check(name+'-exact-input-bytes',dev['public_files'][name]==media['public_files'][name])
        record.update(status='passed',isolated_cli_calls=media['cli_calls']+3,module_origin_probes=1,
            new_model_inference=0,continuous_playback_reviewed=False,audio_reviewed=False,
            natural_quality_accepted=False,full_capcut_parity=False)
    except BaseException as exc:
        record.update(status='failed',error={'type':type(exc).__name__,'message':str(exc)});raise
    finally:
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),frozen_after=frozen())
        record['frozen_equal']=record['frozen_before']==record['frozen_after'];save()
    assert record['frozen_equal']
    print(json.dumps({k:record[k] for k in ('status','isolated_cli_calls','module_origin_probes','frozen_equal')}))


if __name__=='__main__':main()
