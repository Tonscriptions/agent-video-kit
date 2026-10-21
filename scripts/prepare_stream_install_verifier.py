"""Prepare a fresh native-stream coverage isolated-install verifier, without running it."""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REL = ROOT / 'docs/validation/evidence/multicam-stream-coverage-20261021-lab'
DONOR = ROOT.parent / 'multicam-source-range-lab-20261021/scripts/verify_multicam_source_range_install.py'
TARGET = ROOT / 'scripts/verify_multicam_stream_coverage_install.py'


def sha(path):
    return 'sha256:' + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    assert not TARGET.exists()
    original = DONOR.read_text('utf-8')
    text = original.replace('Offline resource isolation and public native empty-window proof.',
        'Offline resource isolation and fresh native-stream coverage media proof.')
    text = text.replace("run('installed-multicam-source-range'", "run('installed-multicam-stream-coverage'")
    text = text.replace('scripts/smoke_multicam_source_range.py', 'scripts/smoke_multicam_stream_coverage.py')
    text = text.replace("'both-installed-coverage-cases-match-independent-RGBA-and-PCM'",
        "'both-installed-native-stream-cases-match-independent-RGBA-and-PCM'")
    anchor = "        record.update(status='passed',isolated_cli_calls=media['cli_calls']+3,module_origin_probes=1,"
    assert text.count(anchor) == 1
    addition = """        check('isolated-native-stream-coverage-discovery',coverage['version']=='0.3.0'
            and coverage['coverage_clock']=='native-video-first-last-intervals-v1'
            and coverage['unknown_video_coverage_contract']=='return_audio_only_sync_with_diagnostics_but_refuse_camera_switch_authoring')
        check('installed-readonly-native-index-and-corruption-controls',
            all(any(row['name']==name and row['ok'] for row in media['checks']) for name in
                ('tail-existing-native-indices-readonly-hit','leading-existing-native-indices-readonly-hit',
                 'tail-corrupt-native-index-refused-without-write','leading-corrupt-native-index-refused-without-write')))
        record['fresh_media']={'source_coverage_version':'0.3.0','reused_v86_media':False,
            'verification_sha256':sha(evidence/'media/verification.json'),'cases':media['cases']}
"""
    # Resolve control names from the actual smoke producer, avoiding fabricated checks.
    smoke = (ROOT/'scripts/smoke_multicam_stream_coverage.py').read_text('utf-8')
    tree = ast.parse(smoke)
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id=='check' and node.args:
            arg = node.args[0]
            if isinstance(arg, ast.JoinedStr):
                parts = [part.value for part in arg.values if isinstance(part, ast.Constant) and isinstance(part.value,str)]
                suffix = ''.join(parts)
                if 'native-index' in suffix or 'native-ind' in suffix:
                    names.append(suffix)
    # The installer performs exactly the same smoke, including all checks. Require every check to pass
    # and both cases to exist; keep the individual names in the executed media receipt.
    start = addition.index("        check('installed-readonly-native-index-and-corruption-controls',")
    end = addition.index("        record['fresh_media']", start)
    addition = addition[:start] + """        check('all-fresh-installed-media-controls-passed',media['status']=='passed'
            and set(media['cases'])=={'tail','leading'} and all(row['ok'] for row in media['checks']))
""" + addition[end:]
    text = text.replace(anchor, addition + anchor)
    before = {n.name: ast.dump(n,include_attributes=False) for n in ast.parse(original).body if isinstance(n,ast.FunctionDef)}
    after = {n.name: ast.dump(n,include_attributes=False) for n in ast.parse(text).body if isinstance(n,ast.FunctionDef)}
    unchanged = {name:before[name]==after[name] for name in ('sha','copy_existing_numpy')}
    assert all(unchanged.values())
    TARGET.write_text(text,encoding='utf-8',newline='\n')
    receipt = {'status':'prepared-not-executed','donor_sha256':sha(DONOR),
        'producer_sha256':sha(__file__),'verifier_sha256':sha(TARGET),'unchanged_helper_AST':unchanged,
        'native_index_smoke_control_suffixes':names,'frozen_core_changed':False,
        'numpy_shipping':'explicit readonly existing local NumPy addon copy; seven-wheel product installer does not ship NumPy',
        'requires':'fresh successful development smoke receipt from this exact 258-input runtime'}
    (REL/'install-preparation-r1.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'status':receipt['status'],'verifier_sha256':receipt['verifier_sha256'],'unchanged_helper_AST':unchanged}))


if __name__=='__main__':
    main()
