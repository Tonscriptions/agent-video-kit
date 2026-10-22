"""Adapt the reviewed native parent publisher; preserve its exact staging gates."""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT.parent/'float-standard-render-lab-20261022'


def main():
    source = PARENT/'scripts/publish_float_standard.py'
    preflight = json.loads((PARENT/'docs/validation/evidence/float-standard-20261022-lab/staging-preflight-r1.json').read_bytes())
    assert preflight['generator_sha256'] == 'sha256:'+hashlib.sha256(source.read_bytes()).hexdigest()
    text = source.read_text('utf8')
    for before, after in [('296', 'PARENT_FROZEN_COUNT_PLACEHOLDER'), ('298', '300'), ('PARENT_FROZEN_COUNT_PLACEHOLDER', '298'),
        ('2337', '2355'), ('220', '260'), ('179', '180'), ('V96', 'V97'), ('r96_', 'r97_'),
        ('float_standard_release_docs', 'float_preview_release_docs'), ('float-standard-20261022', 'float-preview-20261022'),
        ('float-render-lab-20261022', 'float-standard-render-lab-20261022'),
        ('standard-r5/verification.json', 'native-r2/verification.json'), ('media-r4/verification.json', 'media-r1/verification.json'),
        ("'native_methods': 17", "'native_methods': 57"), ('len(changed) == 10', 'len(changed) == 4'),
        ('real-CLI-media-and-260-methods', 'real-previews-and-260-methods'),
        ('passed-published-V95-plus-R16-parent-binding', 'passed-published-V96-parent-binding'),
        ('V97 候选：标准 CLI 原片浮点渲染（未发布）', 'V97 候选：原片 Float32 时间线预览与缓存（未发布）'),
        ('V97 标准 CLI 原片浮点渲染（当轮门禁已通过）', 'V97 原片 Float32 时间线预览与缓存（当轮门禁已通过）'),
        ('feat: connect native float frames to standard render queue and resume', 'feat: connect native Float32 timeline previews and content cache')]:
        assert before in text, before
        text = text.replace(before, after)
    before = """    assert review['status'] == 'reviewed-actual-CLI-stills-and-GIF-clock-not-playback'
    assert review['image_sha256'] == sha(ROOT/review['image'])"""
    after = """    assert review['status'] == 'reviewed-actual-CLI-preview-stills-and-GIF-clock-not-playback'
    assert review['GIF_frames'] == 14 and review['viewed_image_panels'] == 6
    for name, digest in review['files'].items():
        assert sha(ROOT/docs.ASSETS/name) == digest
    precision = read(ROOT/REL/'black-precision-review-r1.json')
    assert precision['status'] == 'reviewed-native-viewing-copy-format-loss-not-exact-reference-acceptance'
    assert precision['source_receipt_sha256'] == sha(ROOT/REL/'black-r3.json')
    assert not precision['exact_MP4_quantizer_accepted'] and precision['source_status'] == 'failed'"""
    assert text.count(before) == 1; text = text.replace(before, after)
    before = "        full = read(ROOT/REL/'full-r1.json')"
    after = """        assert media['actual_public_preview_CLI_processes'] == replay['actual_public_preview_CLI_processes'] == 3
        for key in ('Float32_sha256', 'PCM_sha256', 'PNG16_sha256'):
            assert media['preview_decoded'][key] == replay['preview_decoded'][key]
        full = read(ROOT/REL/'full-r1.json')"""
    assert text.count(before) == 1; text = text.replace(before, after)
    anchor = "        reviewed = publication_files(audit); state['source_files'] = reviewed; checkpoint()"
    assert text.count(anchor) == 1
    text = text.replace(anchor, """        docs.write(report, report.read_text('utf8').replace('本轮尚未合入或推送。',
            '当轮专项、安装与完整回归门禁已通过；推送结果以发布进程终态和远端提交为准。'))
"""+anchor)
    before = 'V97 explicit native float standard render/queue/resume; actual full2355/installed260, 180 resources; existing 17 skill bodies unchanged; default migration/all effects/preview/HDR/natural quality and full CapCut parity unfinished'
    after = 'V97 explicit native Float32 timeline previews and content cache; actual full2355/installed260, 180 resources; existing 17 skill bodies unchanged; default migration/all effects/HDR/natural quality and full CapCut parity unfinished'
    assert before in text; text = text.replace(before, after)
    text = text.replace("'standard_render_integrated': True,", "'standard_render_integrated': True, 'native_float_preview_integrated': True,")
    ast.parse(text)
    target = ROOT/'scripts/publish_float_preview.py'; assert not target.exists()
    target.write_text(text, encoding='utf8', newline='\n')
    print(json.dumps({'status': 'prepared-reviewed-private-staging-and-ordinary-publisher',
        'parent_publisher_sha256': preflight['generator_sha256'], 'publisher_sha256': 'sha256:'+hashlib.sha256(target.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
