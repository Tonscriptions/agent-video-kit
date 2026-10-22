"""Prepare a fresh isolated installer check from the frozen parent procedure."""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT.parent/'float-standard-render-lab-20261022'


def main():
    source = PARENT/'scripts/verify_float_standard_install.py'
    owner = json.loads((PARENT/'product/.runtime/float-standard-20261022/complete-r1/run.json').read_bytes())
    assert owner['verification_scripts']['scripts/verify_float_standard_install.py'] == 'sha256:'+hashlib.sha256(source.read_bytes()).hexdigest()
    text = source.read_text('utf8')
    for before, after in [('float-standard-20261022', 'float-preview-20261022'),
        ('smoke_float_standard_media.py', 'smoke_float_preview_media.py'),
        ('standard-r5/verification.json', 'native-r2/verification.json'),
        ('media-r4/verification.json', 'media-r1/verification.json'),
        ('passed-public-CLI-original-and-edited-native-float-media', 'passed-public-CLI-original-edited-and-native-float-previews'),
        ('179', '180'), ('298', '300'), ('220', '260'),
        ('real-CLI-media-and-260-methods', 'real-previews-and-260-methods'),
        ("standard['methods'] == 17", "standard['methods'] == 57"),
        ('actual native 17 methods', 'actual native 57 methods')]:
        assert before in text, before
        text = text.replace(before, after)
    anchor = "'test_float_native_source', 'test_float_standard_render']"
    assert text.count(anchor) == 1
    text = text.replace(anchor, "'test_float_native_source', 'test_float_standard_render', 'test_timeline_preview', 'test_float_preview']")
    text = text.replace("media['actual_public_render_CLI_processes'] == 2)",
        "media['actual_public_render_CLI_processes'] == 2 and media['actual_public_preview_CLI_processes'] == 3)")
    text = text.replace("m['actual_public_render_CLI_processes'] == 2)",
        "m['actual_public_render_CLI_processes'] == 2 and m['actual_public_preview_CLI_processes'] == 3)")
    text = text.replace('standard_render_integrated=True, default_backend_migrated=False',
        'standard_render_integrated=True, native_float_preview_integrated=True, default_backend_migrated=False')
    ast.parse(text)
    target = ROOT/'scripts/verify_float_preview_install.py'; assert not target.exists()
    target.write_text(text, encoding='utf8', newline='\n')
    print(json.dumps({'status': 'prepared-fresh-eight-wheel-180-resource-260-method-driver',
        'parent_driver_sha256': 'sha256:'+hashlib.sha256(source.read_bytes()).hexdigest(),
        'driver_sha256': 'sha256:'+hashlib.sha256(target.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
