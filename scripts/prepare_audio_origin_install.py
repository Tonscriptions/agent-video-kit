"""Prepare an isolated audio-origin verifier using the existing offline bundle and explicit NumPy addon."""
import ast
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REL=ROOT/'docs/validation/evidence/audio-source-origin-20261021-lab'
DONOR=ROOT.parent/'multicam-stream-coverage-lab-20261021/scripts/verify_multicam_stream_coverage_install.py'
TARGET=ROOT/'scripts/verify_audio_source_origin_install.py'


def sha(path):
    with Path(path).open('rb') as stream:return 'sha256:'+hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    assert not TARGET.exists()
    native=json.loads((REL/'native-r1/verification.json').read_bytes());assert native['status']=='passed'
    original=DONOR.read_text('utf8');source=original
    for before,after in (
        ('Offline resource isolation and fresh native-stream coverage media proof.','Offline resource isolation and fresh native audio-origin media proof.'),
        ('installed-multicam-stream-coverage','installed-audio-source-origin'),
        ('scripts/smoke_multicam_stream_coverage.py','scripts/smoke_audio_source_origin.py'),
        ('both-installed-native-stream-cases-match-independent-RGBA-and-PCM','both-installed-audio-origin-cases-match-independent-RGBA-and-PCM'),
        ("coverage['version']=='0.3.0'","coverage['version']=='0.4.0'"),
        ("{'tail','leading'}","{'native','offset'}"),
        ("'source_coverage_version':'0.3.0'","'source_coverage_version':'0.4.0'"),
        ("'reused_v86_media':False","'reused_parent_media':False")):
        assert before in source,before;source=source.replace(before,after)
    anchor="        record['fresh_media']="
    assert source.count(anchor)==1
    addition="""        audio_clock=capabilities['data']['capabilities']['media']['source_audio_clock']
        check('isolated-native-audio-source-clock-discovery',audio_clock['protocol']=='demux-relative-first-audio-pts-v1'
            and audio_clock['async_clock_drift_correction'] is False
            and coverage['audio_source_clock']==audio_clock['protocol'])
"""
    source=source.replace(anchor,addition+anchor)
    a={n.name:ast.dump(n,include_attributes=False) for n in ast.parse(original).body if isinstance(n,ast.FunctionDef)}
    b={n.name:ast.dump(n,include_attributes=False) for n in ast.parse(source).body if isinstance(n,ast.FunctionDef)}
    unchanged={name:a[name]==b[name] for name in ('sha','copy_existing_numpy')};assert all(unchanged.values())
    TARGET.write_text(source,encoding='utf8',newline='\n')
    record={'status':'prepared-not-executed','donor_sha256':sha(DONOR),'producer_sha256':sha(__file__),
        'verifier_sha256':sha(TARGET),'unchanged_helper_AST':unchanged,'native_smoke_sha256':sha(REL/'native-r1/verification.json'),
        'shipping_limit':'Seven base wheels do not contain NumPy; explicit readonly copy of existing local NumPy with RECORD/license verification, not a product installer feature.',
        'parent_media_or_installation_results_reused':False,'full_capcut_parity':False}
    (REL/'install-preparation-r1.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'status':record['status'],'verifier_sha256':record['verifier_sha256']}))


if __name__=='__main__':main()
