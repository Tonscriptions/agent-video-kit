"""Eight-wheel isolated affine clock, float PCM and fresh camera-switch media proof."""
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
        check('all-162-source-wheel-installed-resources-byte-equal',source==shipped==actual and len(source)==162,
            source_resources=len(source),wheel_resources=len(shipped),installed_resources=len(actual))
        check('eight-pinned-media-wheels',manifest['runtime_profile']=='media-analysis-v1'
            and len(manifest['wheels'])==8 and {w['name'] for w in manifest['wheels']}==
            {'ai-ad-editor','jsonschema','attrs','jsonschema-specifications','referencing','rpds-py','pillow','numpy'})
        record['resource_hashes']={name:'sha256:'+hashlib.sha256(data).hexdigest() for name,data in sorted(source.items())}
        numpy_row=next(row for row in manifest['wheels'] if row['name']=='numpy')
        numpy_wheel=bundle/numpy_row['path'];lock=json.loads((args.wheelhouse/'lock.json').read_bytes())
        locked=next(row for row in lock['artifacts'] if row['name']=='numpy')
        check('official-pinned-numpy-wheel-byte-equal',numpy_row['version']=='2.4.2'
            and sha(numpy_wheel)==locked['sha256']=='sha256:7df2de1e4fba69a51c06c28f5a3de36731eb9639feb8e1cf7e4a7b0daf4cf622')
        from email.parser import BytesParser
        with zipfile.ZipFile(wheel) as archive:
            info=BytesParser().parsebytes(archive.read(next(n for n in archive.namelist() if n.endswith('.dist-info/METADATA'))))
        check('product-declares-numpy-runtime-dependency',any(r.lower().startswith('numpy') for r in info.get_all('Requires-Dist',[])))
        native=record['installation']['audit']['numpy_native']
        check('installer-executed-native-dot-solve-and-FFT',native['dot']==285.0
            and max(abs(a-b) for a,b in zip(native['solve'],[2.,3.]))<=1e-12
            and native['fft_impulse_real']==[1.,1.,1.] and native['fft_impulse_imag']==[0.,0.,0.]
            and len(native['extensions'])==2)
        check('installer-audited-all-eight-local-module-origins',len(record['installation']['audit']['modules'])==8
            and record['installation']['audit']['modules']['numpy']['version']=='2.4.2')
        equal={};notices={}
        with zipfile.ZipFile(numpy_wheel) as archive:
            for name in archive.namelist():
                if name.endswith('/') or name.endswith('.dist-info/RECORD'):continue
                path=installed/'site'/name;data=archive.read(name)
                assert path.resolve().is_relative_to(installed/'site') and path.read_bytes()==data,name
                equal[name]={'sha256':sha(path),'bytes':len(data)}
                if any(token in Path(name).name.upper() for token in ('LICENSE','COPYING','NOTICE')):
                    notice=bundle/'licenses/numpy'/name
                    assert notice.read_bytes()==data,name
                    notices[name]={'bundle_path':notice.relative_to(bundle).as_posix(),'installed_path':name,'sha256':sha(notice)}
        check('all-931-original-numpy-wheel-files-installed-byte-equal',len(equal)==931,compared_files=len(equal))
        check('all-original-numpy-notices-in-bundle-and-install',bool(notices),notices=notices)
        record['numpy_distribution']={'base_bundle_includes_numpy':True,'host_site_copied':False,
            'source':'official-pinned-wheel','version':'2.4.2','wheel_sha256':sha(numpy_wheel),
            'original_wheel_files_except_rewritten_RECORD':equal,'notices':notices,'native_audit':native}
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
            'ai_ad_editor.render','ai_ad_editor.preview','ai_ad_editor.capabilities','ai_ad_editor.native_video_index','ai_ad_editor.derived_cache','ai_ad_editor.subtitle_clock','PIL.Image','ai_ad_editor.multicam','ai_ad_editor.multicam_clock','numpy','numpy._core._multiarray_umath']
        origins=json.loads(run('origins',[sys.executable,'-I','-S','-B','-X','utf8','-c',
            'import sys,json,importlib;sys.path.insert(0,sys.argv[1]);names=json.loads(sys.argv[2]);'
            'print(json.dumps({name:importlib.import_module(name).__file__ for name in names}))',installed/'site',json.dumps(modules)]))
        check('all-module-origins-under-installed-site',all(Path(p).resolve().is_relative_to(installed/'site') for p in origins.values()),origins=origins)
        run('installed-multicam-affine',[sys.executable,'-E','-B','-X','utf8',ROOT/'scripts/smoke_multicam_affine_clock.py',
            '--work',work/'media','--evidence',evidence/'media','--assets',args.assets.resolve(),'--installed',installed,
            '--reuse-sources',args.development.resolve().with_name('source-manifest.json')])
        media=json.loads((evidence/'media/verification.json').read_bytes())
        check('development-and-installed-exact-same-frozen-source',media['status']=='passed' and
            media['frozen_before']==media['frozen_after']==development['frozen_before']==development['frozen_after']==record['frozen_before'])
        check('both-installed-affine-cases-match-independent-frame-and-PCM-oracles',media['cases']==development['cases'])
        coverage=capabilities['data']['capabilities']['media']['multicam_source_coverage']
        check('isolated-coverage-policy-discovery',coverage['source_shortfall_default']=='reject' and coverage['source_shortfall_choices']==['reject','trim','stretch'])
        check('isolated-native-stream-coverage-discovery',coverage['version']=='0.5.0'
            and coverage['coverage_clock']=='native-video-first-last-intervals-v1'
            and coverage['unknown_video_coverage_contract']=='return_audio_only_sync_with_diagnostics_but_refuse_camera_switch_authoring')
        check('all-fresh-installed-media-controls-passed',media['status']=='passed'
            and set(media['cases'])=={'positive','small-negative'} and all(row['ok'] for row in media['checks']))
        audio_clock=capabilities['data']['capabilities']['media']['source_audio_clock']
        check('isolated-native-audio-source-clock-discovery',audio_clock['protocol']=='demux-relative-first-audio-pts-v1'
            and audio_clock['async_clock_drift_correction'] is False
            and coverage['audio_source_clock']==audio_clock['protocol'])
        record['fresh_media']={'source_coverage_version':'0.5.0','reused_parent_media':False,'reused_original_source_inputs':True,
            'verification_sha256':sha(evidence/'media/verification.json'),'cases':media['cases']}
        clock=capabilities['data']['capabilities']['media']['multicam_clock']
        check('isolated-affine-clock-discovery',clock['protocol']=='multicam-affine-clock-v1')
        unit_bootstrap=('import sys,unittest;sys.path[:0]=[sys.argv.pop(1),sys.argv.pop(1)];'
            'from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();'
            'sys.argv=[sys.argv[0],"-v","test_multicam_affine_clock","test_audio_resample_precision"];'
            'unittest.main(module=None)')
        unit_output=run('isolated-41-affine-and-PCM-methods',[sys.executable,'-I','-S','-B','-X','utf8','-c',
            unit_bootstrap,installed/'site',ROOT/'product/tests'])
        unit_log=(evidence/'isolated-41-affine-and-PCM-methods.stderr.log').read_text('utf8')
        import re
        match=re.search(r'Ran (\d+) tests in ([\d.]+)s',unit_log)
        check('isolated-41-methods-terminal-OK',match is not None and int(match[1])==41
            and re.search(r'\bOK\s*$',unit_log) is not None and '... skipped ' not in unit_log)
        record['isolated_methods']={'methods':41,'suite_seconds':float(match[2]),'skipped':0,
            'log_sha256':sha(evidence/'isolated-41-affine-and-PCM-methods.stderr.log')}
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
