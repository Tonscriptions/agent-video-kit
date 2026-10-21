"""Reuse the exact audio media workflow and verify NumPy delivered solely by wheel."""
import ast
import hashlib
import json
from pathlib import Path
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
DONOR=ROOT.parent/'audio-source-origin-lab-20261021'
REL=ROOT/'docs/validation/evidence/offline-media-profile-20261021-lab'


def sha(path):
    with Path(path).open('rb') as stream:return 'sha256:'+hashlib.file_digest(stream,'sha256').hexdigest()


REPLACEMENT=r'''        check('eight-pinned-media-wheels',manifest['runtime_profile']=='media-analysis-v1'
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
'''


def main():
    output=REL/'media-preparation-r1.json';assert not output.exists();current=frozen();assert len(current)==260
    smoke=ROOT/'scripts/smoke_audio_source_origin.py';assert not smoke.exists()
    original_smoke=DONOR/'scripts/smoke_audio_source_origin.py'
    smoke_source=original_smoke.read_text('utf8').replace('docs/validation/evidence/audio-source-origin-20261021-lab/development-audit-r1.json','docs/validation/evidence/offline-media-profile-20261021-lab/development-audit-r1.json').replace("len(record['frozen_before'])==259","len(record['frozen_before'])==260")
    smoke.write_text(smoke_source,encoding='utf8',newline='\n')
    donor=DONOR/'scripts/verify_audio_source_origin_install.py';source=donor.read_text('utf8')
    node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='copy_existing_numpy')
    lines=source.splitlines(keepends=True);source=''.join(lines[:node.lineno-1])+''.join(lines[node.end_lineno:])
    before="        check('seven-existing-wheels-no-numpy',len(manifest['wheels'])==7 and not any(w['name'].lower()=='numpy' for w in manifest['wheels']))\n"
    before+="        record['resource_hashes']={name:'sha256:'+hashlib.sha256(data).hexdigest() for name,data in sorted(source.items())}\n"
    before+="        record['optional_numpy_addon']=copy_existing_numpy(installed)\n"
    before+="        check('explicit-existing-numpy-addon-copied',bool(record['optional_numpy_addon']['files']))\n"
    assert source.count(before)==1;source=source.replace(before,REPLACEMENT)
    source=source.replace('Offline resource isolation and fresh native audio-origin media proof.','Eight-wheel offline runtime, native NumPy and fresh audio-origin media proof.')
    assert 'copy_existing_numpy' not in source and 'optional_numpy_addon' not in source
    target=ROOT/'scripts/verify_media_profile_install.py';assert not target.exists()
    compile(ast.parse(source),str(target),'exec');target.write_text(source,encoding='utf8',newline='\n')
    assert frozen()==current
    record={'status':'prepared-not-executed','frozen_inputs':current,'smoke_script_sha256':sha(smoke),
        'smoke_donor':str(original_smoke),'smoke_byte_unchanged':False,'only_binding_path_and_input_count_changed':True,'install_donor':str(donor),
        'install_donor_sha256':sha(donor),'installer_verifier_sha256':sha(target),
        'host_numpy_copy_function_removed':True,'base_bundle_expected_wheels':8,'network':False,
        'main_changed':False,'generator_sha256':sha(__file__)}
    output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({k:record[k] for k in ('status','smoke_byte_unchanged','host_numpy_copy_function_removed','base_bundle_expected_wheels')}))


if __name__=='__main__':main()
