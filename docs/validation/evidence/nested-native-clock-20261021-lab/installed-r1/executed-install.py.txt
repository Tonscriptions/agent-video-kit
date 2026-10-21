"""Offline resource isolation and public native VFR nested-clock proof."""
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

def sha(path):
    with Path(path).open('rb') as stream:return 'sha256:'+hashlib.file_digest(stream,'sha256').hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('work','evidence','assets','wheelhouse','development'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();work=args.work.resolve();evidence=args.evidence.resolve()
    assert not work.exists() and not evidence.exists() and work.is_relative_to(ROOT/'product/.runtime')
    assert evidence.is_relative_to(ROOT/'docs') and args.assets.resolve().is_relative_to(ROOT/'docs/assets')
    development=json.loads(args.development.read_bytes());assert development['status']=='passed'
    work.mkdir(parents=True);evidence.mkdir(parents=True)
    (evidence/'executed-install.py.txt').write_bytes(Path(__file__).read_bytes())
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),'generator_sha256':sha(__file__),
        'native_windows':sys.platform=='win32','virtualization':False,'network':False,
        'frozen_before':frozen(),'calls':[],'checks':[]}
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
        assert result.returncode==0,label+': '+result.stdout[-1500:].decode('utf8','replace')+result.stderr[-1500:].decode('utf8','replace')
        return result.stdout
    try:
        bundle=work/'bundle';built=json.loads(run('build',[sys.executable,'-E','-B','-X','utf8',ROOT/'product/offline/build.py',
            '--output',bundle,'--wheelhouse',args.wheelhouse.resolve()]))
        record['bundle']=built;installed=work/'installed'
        record['installation']=json.loads(run('install',[sys.executable,'-I','-B','-X','utf8',bundle/'install.py',
            '--target',installed,'--manifest-sha256',built['manifest_sha256']]))
        source={p.name:p.read_bytes() for p in (ROOT/'product/src/ai_ad_editor').iterdir()
            if p.is_file() and p.suffix in {'.py','.mjs','.json','.txt','.c','.dll'}}
        manifest=json.loads((bundle/'manifest.json').read_bytes())
        wheel=next(bundle/item['path'] for item in manifest['wheels'] if item['name']=='ai-ad-editor')
        with zipfile.ZipFile(wheel) as archive:
            metadata=archive.read(next(n for n in archive.namelist() if n.endswith('.dist-info/WHEEL'))).decode('utf8')
            check('native-platform-wheel',wheel.name.endswith('-py3-none-win_amd64.whl') and 'Root-Is-Purelib: false' in metadata and 'Tag: py3-none-win_amd64' in metadata)
            shipped={}
            for name in archive.namelist():
                for prefix in ('ai_ad_editor/','ai_ad_editor-0.1.0.data/purelib/ai_ad_editor/'):
                    if name.startswith(prefix) and not name.endswith('/'):
                        key=name[len(prefix):];assert '/' not in key and key not in shipped
                        shipped[key]=archive.read(name)
        actual={p.name:p.read_bytes() for p in (installed/'site/ai_ad_editor').iterdir()
            if p.is_file() and p.suffix in {'.py','.mjs','.json','.txt','.c','.dll'}}
        check('all-161-source-wheel-installed-resources-byte-equal',source==shipped==actual and len(source)==161,
            source_resources=len(source),wheel_resources=len(shipped),installed_resources=len(actual))
        check('seven-existing-wheels-no-numpy',len(manifest['wheels'])==7 and not any(w['name'].lower()=='numpy' for w in manifest['wheels']))
        record['resource_hashes']={name:'sha256:'+hashlib.sha256(data).hexdigest() for name,data in sorted(source.items())}
        prefix=[sys.executable,'-I','-S','-B','-X','utf8',installed/'run.py']
        capabilities=json.loads(run('capabilities',[*prefix,'capabilities']))
        run('schema',[*prefix,'schema','show']);catalog=json.loads(run('effects',[*prefix,'effects','list']))
        feature=capabilities['data']['capabilities']['reverse_video_cache']
        check('isolated-reverse-cache-discovery',feature['protocol']=='native-lossless-reverse-chunks-v1' and feature['commands']==['cache.list','cache.prune'])
        index_feature=capabilities['data']['capabilities']['native_video_frame_index']
        check('isolated-native-index-discovery',index_feature['protocol']=='native-video-frame-index-v1' and index_feature['cache_kind']=='native-video-index')
        nested_feature=capabilities['data']['capabilities']['nested_native_video_clock']
        check('isolated-native-nested-clock-discovery',nested_feature['protocol']=='covering-native-source-half-open-v1' and nested_feature['status']=='implemented_with_limits')
        check('existing-effect-catalog',catalog['data']['catalog_version']=='0.9.0')
        modules=['ai_ad_editor.cli','ai_ad_editor.video_clock','ai_ad_editor.reverse_video_clock','ai_ad_editor.reverse_cache',
            'ai_ad_editor.render','ai_ad_editor.preview','ai_ad_editor.capabilities','ai_ad_editor.native_video_index','ai_ad_editor.derived_cache','ai_ad_editor.subtitle_clock','PIL.Image']
        origins=json.loads(run('origins',[sys.executable,'-I','-S','-B','-X','utf8','-c',
            'import sys,json,importlib;sys.path.insert(0,sys.argv[1]);names=json.loads(sys.argv[2]);'
            'print(json.dumps({name:importlib.import_module(name).__file__ for name in names}))',installed/'site',json.dumps(modules)]))
        check('all-module-origins-under-installed-site',all(Path(p).resolve().is_relative_to(installed/'site') for p in origins.values()),origins=origins)
        run('installed-native-VFR',[sys.executable,'-E','-B','-X','utf8',ROOT/'scripts/smoke_nested_native_clock.py',
            '--work',work/'media','--evidence',evidence/'media','--assets',args.assets.resolve(),'--installed',installed])
        media=json.loads((evidence/'media/verification.json').read_bytes())
        check('development-and-installed-exact-same-frozen-source',media['status']=='passed' and
            media['frozen_before']==media['frozen_after']==development['frozen_before']==development['frozen_after']==record['frozen_before'])
        comparable=('frames','fps','expected_source_frame_ids','encoded_source_frame_ids','preview_bytes','preview_max_RGBA_error','preview_sha256')
        check('both-installed-VFR-cases-match-independent-development-frame-evidence',
            set(media['cases'])==set(development['cases']) and all(
                {k:row[k] for k in comparable}=={k:development['cases'][name][k] for k in comparable}
                for name,row in media['cases'].items()))
        record.update(status='passed',isolated_cli_calls=media['cli_calls']+3,module_origin_probes=1,
            continuous_playback_reviewed=False,audio_reviewed=False,natural_quality_accepted=False,
            HDR_accepted=False,long_duration_latency_accepted=False,full_capcut_parity=False)
    except BaseException as error:record.update(status='failed',error=repr(error));raise
    finally:
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),frozen_after=frozen())
        record['frozen_equal']=record['frozen_before']==record['frozen_after'];save()
    assert record['frozen_equal']
    print(json.dumps({k:record[k] for k in ('status','isolated_cli_calls','module_origin_probes','frozen_equal')}))

if __name__=='__main__':main()
