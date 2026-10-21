"""Derive a fresh eight-wheel affine-clock verifier from the preserved V89 verifier."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PARENT=Path('E:/dev/sandbox/AI广告剪辑/product/.runtime/offline-media-profile-lab-20261021')
REL=ROOT/'docs/validation/evidence/multicam-affine-clock-20261021-lab'
TARGET=ROOT/'scripts/verify_multicam_affine_install.py'
assert not TARGET.exists()
original=(PARENT/'scripts/verify_media_profile_install.py').read_text('utf8')
text=original
changes=[]
def replace(old,new):
    global text
    count=text.count(old);assert count==1,(old,count)
    text=text.replace(old,new)
    changes.append({'before':old,'after':new,'occurrences':count})
replace('"""Eight-wheel offline runtime, native NumPy and fresh audio-origin media proof."""',
        '"""Eight-wheel isolated affine clock, float PCM and fresh camera-switch media proof."""')
replace("check('all-161-source-wheel-installed-resources-byte-equal',source==shipped==actual and len(source)==161,",
        "check('all-162-source-wheel-installed-resources-byte-equal',source==shipped==actual and len(source)==162,")
replace("'PIL.Image','ai_ad_editor.multicam','numpy'", "'PIL.Image','ai_ad_editor.multicam','ai_ad_editor.multicam_clock','numpy'")
replace("run('installed-audio-source-origin',[sys.executable,'-E','-B','-X','utf8',ROOT/'scripts/smoke_audio_source_origin.py',",
        "run('installed-multicam-affine',[sys.executable,'-E','-B','-X','utf8',ROOT/'scripts/smoke_multicam_affine_clock.py',")
replace("'--work',work/'media','--evidence',evidence/'media','--assets',args.assets.resolve(),'--installed',installed])",
        "'--work',work/'media','--evidence',evidence/'media','--assets',args.assets.resolve(),'--installed',installed,\n"
        "            '--reuse-sources',args.development.resolve().with_name('source-manifest.json')])")
replace("'both-installed-audio-origin-cases-match-independent-RGBA-and-PCM'", "'both-installed-affine-cases-match-independent-frame-and-PCM-oracles'")
replace("coverage['version']=='0.4.0'", "coverage['version']=='0.5.0'")
replace("set(media['cases'])=={'native','offset'}", "set(media['cases'])=={'positive','small-negative'}")
replace("record['fresh_media']={'source_coverage_version':'0.4.0','reused_parent_media':False,",
        "record['fresh_media']={'source_coverage_version':'0.5.0','reused_parent_media':False,'reused_original_source_inputs':True,")
replace("record.update(status='passed',isolated_cli_calls=media['cli_calls']+3,module_origin_probes=1,",
        """clock=capabilities['data']['capabilities']['multicam_clock']
        check('isolated-affine-clock-discovery',clock['protocol']=='multicam-affine-clock-v1')
        unit_bootstrap=('import sys,unittest;sys.path[:0]=[sys.argv.pop(1),sys.argv.pop(1)];'
            'from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();'
            'sys.argv=[sys.argv[0],"-v","test_multicam_affine_clock","test_audio_resample_precision"];'
            'unittest.main(module=None)')
        unit_output=run('isolated-41-affine-and-PCM-methods',[sys.executable,'-I','-S','-B','-X','utf8','-c',
            unit_bootstrap,installed/'site',ROOT/'product/tests'])
        unit_log=(evidence/'isolated-41-affine-and-PCM-methods.stderr.log').read_text('utf8')
        import re
        match=re.search(r'Ran (\\d+) tests in ([\\d.]+)s',unit_log)
        check('isolated-41-methods-terminal-OK',match is not None and int(match[1])==41
            and re.search(r'\\bOK\\s*$',unit_log) is not None and '... skipped ' not in unit_log)
        record['isolated_methods']={'methods':41,'suite_seconds':float(match[2]),'skipped':0,
            'log_sha256':sha(evidence/'isolated-41-affine-and-PCM-methods.stderr.log')}
        record.update(status='passed',isolated_cli_calls=media['cli_calls']+3,module_origin_probes=1,""")
TARGET.write_text(text,encoding='utf8',newline='\n')
sha=lambda data:'sha256:'+hashlib.sha256(data).hexdigest()
(REL/'install-preparation-r1.json').write_text(json.dumps({'status':'prepared','parent_script':str(PARENT/'scripts/verify_media_profile_install.py'),
    'parent_sha256':sha(original.encode('utf8')),'output':TARGET.relative_to(ROOT).as_posix(),
    'output_sha256':sha(TARGET.read_bytes()),'exact_changes':changes,'installed_executed':False},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print('prepared',TARGET.name,'changes',len(changes))
