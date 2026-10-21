"""Reuse the tested offline verifier with an explicit existing NumPy addon."""
import ast
from pathlib import Path
from smoke_multicam_source_range import sha, write

ROOT = Path(__file__).resolve().parents[1]
REL = ROOT / 'docs/validation/evidence/multicam-source-range-20261021-lab'


def replace_once(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new)


ADDON = '''
def copy_existing_numpy(installed):
    import base64
    import importlib.metadata
    import shutil
    distribution=importlib.metadata.distribution('numpy')
    source=Path(distribution.locate_file('')).resolve(strict=True)
    info=next(p.parts[0] for p in distribution.files if p.name=='METADATA' and p.parts[0].endswith('.dist-info'))
    allowed={'numpy','numpy.libs',info};files={};omitted=[]
    for name in distribution.files:
        if name.parts[0] not in allowed or '__pycache__' in name.parts or name.suffix=='.pyc':
            omitted.append(str(name));continue
        path=Path(distribution.locate_file(name))
        assert not path.is_symlink() and path.resolve(strict=True).is_relative_to(source)
        destination=installed/'site'/str(name)
        assert destination.resolve().is_relative_to(installed/'site') and not destination.exists()
        data=path.read_bytes()
        if name.hash:
            assert name.hash.mode=='sha256'
            assert base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode()==name.hash.value,str(name)
        destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,destination)
        assert destination.read_bytes()==data
        files[str(name)]={'sha256':sha(path),'bytes':len(data)}
    assert any(name.startswith('numpy.libs/') and name.endswith('.dll') for name in files)
    assert any('LICENSE' in Path(name).name.upper() for name in files)
    return {'kind':'explicit-existing-local-optional-addon','name':'numpy','version':distribution.version,
        'source':str(source),'files':files,'omitted':omitted,'network':False,
        'base_seven_wheel_bundle_contains_numpy':False,'source_modified':False}

'''


def main():
    source = ROOT.parent / 'native-empty-window-lab-20261021/scripts/verify_native_empty_install.py'
    target = ROOT / 'scripts/verify_multicam_source_range_install.py'
    assert not target.exists()
    text = source.read_text('utf8')
    text = replace_once(text, 'def main():', ADDON + 'def main():')
    text = replace_once(text, "prefix=[sys.executable,'-I','-S','-B','-X','utf8',installed/'run.py']",
        "record['optional_numpy_addon']=copy_existing_numpy(installed)\n        check('explicit-existing-numpy-addon-copied',bool(record['optional_numpy_addon']['files']))\n        prefix=[sys.executable,'-I','-S','-B','-X','utf8',installed/'run.py']")
    text = replace_once(text, "'PIL.Image']", "'PIL.Image','ai_ad_editor.multicam','numpy','numpy._core._multiarray_umath']")
    text = text.replace('smoke_native_empty_window.py', 'smoke_multicam_source_range.py').replace('installed-native-empty-window', 'installed-multicam-source-range')
    start = text.index("        comparable=('frames'")
    end = text.index("        record.update(status='passed'", start)
    text = text[:start] + """        check('both-installed-coverage-cases-match-independent-RGBA-and-PCM',media['cases']==development['cases'])
        coverage=capabilities['data']['capabilities']['media']['multicam_source_coverage']
        check('isolated-coverage-policy-discovery',coverage['source_shortfall_default']=='reject' and coverage['source_shortfall_choices']==['reject','trim','stretch'])
""" + text[end:]
    compile(text, target.name, 'exec')
    original = ast.parse(source.read_text('utf8'))
    adapted = ast.parse(text)
    sha_before = next(n for n in original.body if isinstance(n, ast.FunctionDef) and n.name == 'sha')
    sha_after = next(n for n in adapted.body if isinstance(n, ast.FunctionDef) and n.name == 'sha')
    assert ast.dump(sha_before, include_attributes=False) == ast.dump(sha_after, include_attributes=False)
    target.write_text(text, encoding='utf8', newline='\n')
    write(REL / 'isolated-verifier-reuse-r1.json', {'status': 'prepared-with-explicit-optional-dependency',
        'source': str(source), 'source_sha256': sha(source), 'prepared_sha256': sha(target),
        'unchanged_helper_AST': ['sha'], 'native_windows_only': True, 'base_bundle_unchanged': True,
        'optional_numpy_from_existing_distribution_record_only': True, 'generator_sha256': sha(__file__)})
    print('prepared isolated verifier; core bundle unchanged, NumPy addon explicit')


if __name__ == '__main__':
    main()
