"""Fresh eight-wheel installation: 171 resources, float CLI media and 117 methods."""
from datetime import datetime,timezone
import hashlib,json,os
from pathlib import Path
import re,subprocess,sys,zipfile
from run_frozen_regression import frozen,sha

ROOT=Path(__file__).resolve().parents[1]
REL=ROOT/'docs/validation/evidence/color-precision-20261021-lab'

def main():
    work=ROOT/'product/.runtime/color-precision-20261021/installed-r1'
    evidence=REL/'installed-r1'
    assert not work.exists() and not evidence.exists()
    work.mkdir(parents=True);evidence.mkdir()
    before=frozen();assert len(before)==282
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),
        'pid':os.getpid(),'generator_sha256':sha(Path(__file__)),'frozen_before':before,
        'calls':[],'checks':[],'network':False,'virtualization':False,'native_windows':True,
        'host_numpy_copied':False,'global_site_packages_changed':False,'published':False}
    def save():
        (evidence/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    def check(name,ok,**details):
        record['checks'].append({'name':name,'ok':bool(ok),**details});save();assert ok,name
    env=dict(os.environ,TEMP=str(ROOT/'product/.runtime/temp'),TMP=str(ROOT/'product/.runtime/temp'),TMPDIR=str(ROOT/'product/.runtime/temp'))
    env.pop('AI_AD_EDITOR_AUDIO_CLOCK_FIXTURES',None)
    def run(name,command):
        command=list(map(str,command));p=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,timeout=1200,creationflags=subprocess.CREATE_NO_WINDOW)
        for stream in ('stdout','stderr'):(evidence/(name+'.'+stream+'.log')).write_bytes(getattr(p,stream))
        record['calls'].append({'name':name,'command':command,'exit_code':p.returncode,
            'stdout_sha256':'sha256:'+hashlib.sha256(p.stdout).hexdigest(),
            'stderr_sha256':'sha256:'+hashlib.sha256(p.stderr).hexdigest()});save()
        assert p.returncode==0,(name,p.stdout[-1000:].decode('utf8','replace'),p.stderr[-2000:].decode('utf8','replace'))
        return p.stdout
    try:
        wheelhouse=ROOT/'sources/python-runtime/cp313-win_amd64-media'
        deps=json.loads((REL/'foundation-r1.json').read_bytes())['dependency_artifact_inputs']
        check('all-nine-pinned-wheelhouse-inputs-before',all(sha(ROOT/k)==v for k,v in deps.items()))
        record['dependency_artifact_inputs']=deps
        bundle=work/'bundle';installed=work/'installed'
        built=json.loads(run('build',[sys.executable,'-E','-B','-X','utf8',ROOT/'product/offline/build.py','--output',bundle,'--wheelhouse',wheelhouse]))
        record['bundle']=built
        record['installation']=json.loads(run('install',[sys.executable,'-I','-B','-X','utf8',bundle/'install.py','--target',installed,'--manifest-sha256',built['manifest_sha256']]))
        manifest=json.loads((bundle/'manifest.json').read_bytes())
        check('complete-eight-wheel-media-analysis-profile',manifest['runtime_profile']=='media-analysis-v1' and len(manifest['wheels'])==8
            and {w['name'] for w in manifest['wheels']}=={'ai-ad-editor','jsonschema','attrs','jsonschema-specifications','referencing','rpds-py','pillow','numpy'})
        extensions={'.py','.mjs','.json','.txt','.c','.dll'}
        source={p.name:p.read_bytes() for p in (ROOT/'product/src/ai_ad_editor').iterdir() if p.is_file() and p.suffix in extensions}
        actual={p.name:p.read_bytes() for p in (installed/'site/ai_ad_editor').iterdir() if p.is_file() and p.suffix in extensions}
        wheel=next(bundle/w['path'] for w in manifest['wheels'] if w['name']=='ai-ad-editor')
        with zipfile.ZipFile(wheel) as archive:
            metadata=archive.read(next(n for n in archive.namelist() if n.endswith('.dist-info/WHEEL'))).decode('utf8')
            check('native-platform-wheel-tag',wheel.name.endswith('-py3-none-win_amd64.whl') and 'Root-Is-Purelib: false' in metadata and 'Tag: py3-none-win_amd64' in metadata)
            shipped={}
            for name in archive.namelist():
                for prefix in ('ai_ad_editor/','ai_ad_editor-0.1.0.data/purelib/ai_ad_editor/'):
                    if name.startswith(prefix) and not name.endswith('/'):
                        key=name[len(prefix):];assert '/' not in key and key not in shipped
                        shipped[key]=archive.read(name)
        check('all-171-source-wheel-site-resources-byte-identical',len(source)==171 and source==shipped==actual,
            source_resources=len(source),wheel_resources=len(shipped),installed_resources=len(actual))
        record['resource_hashes']={k:'sha256:'+hashlib.sha256(v).hexdigest() for k,v in sorted(source.items())}
        numpy_row=next(w for w in manifest['wheels'] if w['name']=='numpy');numpy_wheel=bundle/numpy_row['path']
        check('official-pinned-numpy-2.4.2-wheel',numpy_row['version']=='2.4.2' and sha(numpy_wheel)=='sha256:7df2de1e4fba69a51c06c28f5a3de36731eb9639feb8e1cf7e4a7b0daf4cf622')
        files={};notices={}
        with zipfile.ZipFile(numpy_wheel) as archive:
            for name in archive.namelist():
                if name.endswith('/') or name.endswith('.dist-info/RECORD'):continue
                path=installed/'site'/name;data=archive.read(name)
                assert path.resolve().is_relative_to(installed/'site') and path.read_bytes()==data,name
                files[name]={'sha256':sha(path),'bytes':len(data)}
                if any(t in Path(name).name.upper() for t in ('LICENSE','COPYING','NOTICE')):
                    notice=bundle/'licenses/numpy'/name;assert notice.read_bytes()==data
                    notices[name]={'bundle_path':notice.relative_to(bundle).as_posix(),'sha256':sha(notice)}
        check('all-931-original-numpy-files-and-notices-byte-identical',len(files)==931 and bool(notices),compared_files=len(files),notices=notices)
        record['numpy_distribution']={'original_files_except_rewritten_RECORD':files,'notices':notices,'host_distribution_copied':False}
        audit=record['installation']['audit'];native=audit['numpy_native']
        check('installer-native-dot-solve-FFT-and-eight-module-origins',native['dot']==285.0
            and max(abs(a-b) for a,b in zip(native['solve'],[2.,3.]))<=1e-12
            and native['fft_impulse_real']==[1.,1.,1.] and native['fft_impulse_imag']==[0.,0.,0.]
            and len(native['extensions'])==2 and len(audit['modules'])==8)
        prefix=[sys.executable,'-I','-S','-B','-X','utf8',installed/'run.py']
        caps=json.loads(run('capabilities',[*prefix,'capabilities']))['data']['capabilities']
        run('schema',[*prefix,'schema','show']);run('effects',[*prefix,'effects','list'])
        check('installed-public-float-protocol-discovery',caps['native_float_surface_bundle']['protocol']=='agent-native-clock-float32-bundle-v1')
        reference=REL/'surface-cli-media-r1/verification.json'
        assert json.loads(reference.read_bytes())['status'].startswith('passed-subprocess-surface-CLI')
        run('installed-public-surface-media',[sys.executable,'-E','-B','-X','utf8',ROOT/'scripts/smoke_float_bundle_cli.py',
            '--revision','installed-r1','--installed',installed,'--reference',reference])
        media=REL/'surface-cli-media-installed-r1/verification.json';media_record=json.loads(media.read_bytes())
        check('fresh-installed-public-CLI-actual-media-pass',media_record['status'].startswith('passed-subprocess-surface-CLI')
            and media_record['frozen_before']==media_record['frozen_after']==before and media_record['CLI_calls']==15)
        test_names=['test_float_raster','test_float_geometry','test_float_pixels','test_float_video_source',
                    'test_float_yuv','test_float_color_signal','test_float_bundle','test_queue_reuse']
        bootstrap=('import sys,unittest,json,pathlib;sys.path[:0]=[sys.argv[1],sys.argv[2]];'
            'from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();'
            'names=json.loads(sys.argv[3]);suite=unittest.defaultTestLoader.loadTestsFromNames(names);'
            'result=unittest.TextTestRunner(verbosity=2).run(suite);'
            'origins={n:str(pathlib.Path(m.__file__).resolve()) for n,m in sys.modules.items() if getattr(m,"__file__",None) and (n=="ai_ad_editor" or n.startswith("ai_ad_editor.") or n=="numpy" or n.startswith("numpy.") or n=="PIL" or n.startswith("PIL."))};'
            'calls={n:getattr(sys.modules[n],"NATIVE_CALLS",[]) for n in names};'
            'print(json.dumps({"methods":result.testsRun,"skipped":len(result.skipped),"origins":origins,"native_test_records":calls}));'
            'raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)')
        result=json.loads(run('isolated-117-float-and-queue-methods',[sys.executable,'-I','-S','-B','-X','utf8','-c',bootstrap,
            installed/'site',ROOT/'product/tests',json.dumps(test_names)]))
        log=evidence/'isolated-117-float-and-queue-methods.stderr.log';text=log.read_text('utf8')
        match=re.search(r'Ran (\d+) tests in ([\d.]+)s',text)
        check('isolated-117-methods-terminal-OK-no-skips',match is not None and int(match[1])==result['methods']==117
            and result['skipped']==0 and re.search(r'\bOK\s*$',text) is not None and '... skipped ' not in text)
        check('every-runtime-test-module-under-fresh-installed-site',bool(result['origins']) and all(Path(p).is_relative_to(installed/'site') for p in result['origins'].values()),runtime_module_count=len(result['origins']))
        record['isolated_methods']={**result,'suite_seconds':float(match[2]),'log_sha256':sha(log)}
        check('all-171-installed-resources-still-identical-after-actual-tests',all((installed/'site/ai_ad_editor'/name).read_bytes()==data for name,data in source.items()))
        check('all-nine-wheelhouse-and-282-product-inputs-unchanged',all(sha(ROOT/k)==v for k,v in deps.items()) and frozen()==before)
        record.update(status='passed-fresh-eight-wheel-float-CLI-media-and-117-methods',
            isolated_subprocess_CLI_calls=media_record['CLI_calls']+3,fresh_media_receipt_sha256=sha(media),
            HDR_accepted=False,natural_quality_accepted=False,continuous_playback_reviewed=False,
            ordinary_timeline_render_integrated=False,full_capcut_parity=False)
    except BaseException as error:
        record.update(status='failed-preserved',error=repr(error));raise
    finally:
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),frozen_after=frozen())
        record['frozen_equal']=record['frozen_before']==record['frozen_after'];save()
        (evidence/'executed.script.py.txt').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({k:record.get(k) for k in ('status','isolated_subprocess_CLI_calls','frozen_equal')}))

if __name__=='__main__':main()
