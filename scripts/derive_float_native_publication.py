"""Prepare the existing serialized ordinary-push machinery for native windows."""
from datetime import datetime, timezone
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT.parent / 'float-stream-lab-20261022'


def upgrade(value):
    # Current identifiers first, then the older parent identifiers; each pass
    # is intentional and does not rewrite a newly produced parent count again.
    for old, new in (('float_stream_release_docs', 'float_native_release_docs'),
        ('publish_float_stream', 'publish_float_native'),
        ('float-stream-20261022', 'float-render-20261022'),
        ('2299', '2320'), ('2280', '2299'), ('182', '203'), ('163', '182'),
        ('292', '296'), ('288', '292'), ('176', '178'),
        ('V94', 'V95'), ('V93', 'V94')):
        value = value.replace(old, new)
    return value


SOURCE_GATE = '''def source_gate(complete):
    from float_native_release_docs import current_evidence
    current=frozen();focus,media,installed=current_evidence();installed=installed_gate()
    base=ROOT/REL;foundation=read(base/'foundation-r1.json');parent=foundation['parent_frozen_inputs']
    assert len(current)==296 and len(parent)==292 and {k:current[k] for k in parent}==parent and len(set(current)-set(parent))==4
    assert len(installed['numpy_distribution']['files'])==931 and installed['actual_discovery_CLI_processes']==3
    for name in ('media-r1','media-installed-r1'):
        value=read(base/name/'verification.json')
        assert value['status']=='passed-real-native-window-FFV1-and-independent-authored-PCM' and value['frozen_before']==value['frozen_after']==current
        assert value['actual_native_launches']==86 and value['actual_encoder_processes']==2 and value['actual_new_CLI_processes']==0 and value['actual_author_frames_each']==20
        assert value['all_reference_pixel_maximum_code_error']==0 and all(row['passed'] for row in value['checks'])
        assert len(value['native_window_source_receipts'])==4 and all(row['closed'] and row['maximum_cached_float_bytes']==491520 and not row['whole_movie_pixel_cache'] for row in value['native_window_source_receipts'])
        for path,row in value['assets'].items():assert sha(ROOT/path)==row['sha256'] and (ROOT/path).stat().st_size==row['bytes']
        if name.startswith('media-installed'):
            assert value['isolated_python'] and value['regression_payload_hashes']==media['regression_payload_hashes']
    review=read(base/'static-review-r1.json');assert review['status']=='reviewed-actual-still-frames-and-PCM-only' and review['image_sha256']==sha(ROOT/ASSETS/'media-r1/actual-frames-and-PCM.png')
    repair=read(base/'native-r1-repair-audit.json');assert repair['status']=='passed-preserved-failed-native-r1-and-scoped-r2-repair' and repair['passed_receipt_sha256']==sha(base/'native-r2.json') and repair['failed_receipt_sha256']==sha(base/'native-r1.json') and repair['all_292_parent_inputs_unchanged'] and not repair['pixel_oracle_or_tolerance_relaxed']
    assert sha(base/'review-generator-r1.executed.py.txt')==review['generator_sha256']==repair['generator_sha256']
    verify(ROOT,foundation['dependency_artifact_inputs'])
    audit={'status':'passed-native-window-source-preflight','frozen_inputs':current,'parent_frozen_inputs':parent,
        'complete_terminal_required':True,'complete_terminal_checked':False,'git_helper_sha256':sha(MAIN/'scripts/native_index_release_tools.py'),
        'native_receipt_sha256':sha(base/'native-r2.json'),'installed_receipt_sha256':sha(base/'installed-r1/verification.json')}
    full=None
    if complete:
        lineage=read(base/'parent-binding-r1.json');owner=read(ROOT/'product/.runtime/float-render-20261022/complete-r1/run.json');full=read(base/'full-r1.json')
        assert lineage['status']=='passed-published-V94-parent-binding' and lineage['published_parent_frozen']==parent and lineage['frozen_after']==current
        assert owner['status']=='passed-complete-native-suite-not-published' and owner['methods']==2320 and owner['full_receipt_sha256']==sha(base/'full-r1.json')
        assert full['status']=='passed' and full['terminal_ok'] and full['methods']==2320 and full['skipped']==0 and full['frozen_before']==full['frozen_after']==current
        assert full['external_fixture_count']==8 and full['external_fixtures_equal'] and full['external_fixture_manifest_unchanged'] and full['verification_scripts_equal']
        for key in ('verification_scripts','dependency_artifact_inputs','bound_evidence'):verify(ROOT,owner[key])
        for name,row in full['external_fixtures_expected'].items():assert sha(ROOT/name)==row['sha256']
        audit.update(status='passed-native-window-complete-and-installed-gates',complete_terminal_checked=True,published_parent=lineage['published_parent_commit'],
            full_receipt_sha256=sha(base/'full-r1.json'),owner_sha256=sha(ROOT/'product/.runtime/float-render-20261022/complete-r1/run.json'))
    return audit,full


'''


def main():
    outputs = {}
    publisher = upgrade((PARENT / 'scripts/publish_float_stream.py').read_text('utf8'))
    a, b = publisher.index('def source_gate('), publisher.index('def finalize_full(')
    publisher = publisher[:a] + SOURCE_GATE + publisher[b:]
    publisher = publisher.replace('feat: stream float author frames with verified native audio',
        'feat: decode original native windows into float author timeline')
    publisher = publisher.replace('V95 library-only bounded Float32-to-FFV1 video and authored native audio transport; actual full2320/installed203;',
        'V95 library-only locked native-clock original-source windows to Float32 timeline; actual full2320/installed203;')
    outputs['publish_float_native.py'] = publisher
    complete = (PARENT / 'scripts/run_float_stream_complete.py').read_text('utf8')
    complete = complete.replace("PARENT=ROOT.parent/'float-timeline-lab-20261022'", "PARENT=ROOT.parent/'__PARENT_LAB__'")
    complete = complete.replace('float-timeline-20261022', '__PARENT_RUNTIME__')
    complete = upgrade(complete).replace('__PARENT_LAB__', 'float-stream-lab-20261022').replace('__PARENT_RUNTIME__', 'float-stream-20261022')
    for old, new in (('release-chain-r2', 'release-chain-r1'), ('publication-r2', 'publication-r1'),
        ('full-r2.json', 'full-r1.json'), ('waiting-for-actual-full2299-r2', 'waiting-for-actual-full2299-r1'),
        ("'foundation-r1.json','audio-r3.json','stream-r2.json','installed-r1/verification.json',\n            'media-r4/verification.json'",
         "'foundation-r1.json','native-r2.json','native-r1.json','native-r1-repair-audit.json','static-review-r1.json','installed-r1/verification.json',\n            'media-r1/verification.json'")):
        assert old in complete, old
        complete = complete.replace(old, new)
    outputs['run_float_native_complete.py'] = complete
    release = upgrade((PARENT / 'scripts/release_float_stream_after_complete.py').read_text('utf8'))
    release = release.replace('float_stream_lab', 'float_native_source_lab')
    release = release.replace("data['float_native_source_lab'].update", "data.setdefault('float_native_source_lab',{}).update")
    release = release.replace('published-V95-library-stream-default-render-not-integrated', 'published-V95-native-windows-default-render-not-integrated')
    release = release.replace('浮点视频流与作者音轨合成独立实测_2026-10-22.md', '原生素材窗口解码与浮点音画合成实测_2026-10-22.md')
    release = release.replace('浮点视频有界编码与作者音频接入_实验_v0.1_2026-10-22.md', '原生素材窗口浮点源_实验_v0.1_2026-10-22.md')
    release = release.replace('V95 bounded Float32-to-FFV1 and native authored audio library;', 'V95 original native-clock pixel windows and Float32 author timeline library;')
    outputs['release_float_native_after_complete.py'] = release
    for name, value in outputs.items():
        target = ROOT / 'scripts' / name
        assert not target.exists()
        compile(value, str(target), 'exec')
        target.write_text(value, encoding='utf8', newline='\n')
    receipt = ROOT / 'docs/validation/evidence/float-render-20261022-lab/publisher-preparation-r1.json'
    receipt.write_text(json.dumps({'status': 'prepared-serialized-owner-and-ordinary-publication-not-dispatched',
        'at_utc': datetime.now(timezone.utc).isoformat(), 'parent': str(PARENT),
        'parent_published': False, 'new_expected_full_methods': 2320,
        'required_installed_methods': 203, 'full_passed': False,
        'files': list(outputs), 'force_push': False}, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'prepared': list(outputs)}))


if __name__ == '__main__':
    main()
