"""Keep the existing full offline-install checks and add native window coverage."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT.parent / 'float-stream-lab-20261022'


def main():
    target = ROOT / 'scripts/verify_float_native_install.py'
    assert not target.exists()
    value = (PARENT / 'scripts/verify_float_stream_install.py').read_text('utf8')
    replacements = [
        ('float-stream-20261022', 'float-render-20261022'),
        ('176', '178'), ('182', '203'), ('292', '296'),
        ('smoke_float_stream_media.py', 'smoke_float_native_media.py'),
        ("reference=REL/'media-r4/verification.json'", "reference=REL/'media-r1/verification.json'"),
        ('passed-real-bounded-FFV1-and-independent-authored-PCM',
         'passed-real-native-window-FFV1-and-independent-authored-PCM'),
        ("'test_float_audio_graph','test_float_stream']",
         "'test_float_audio_graph','test_float_stream','test_float_native_pipe','test_float_native_source']"),
    ]
    for old, new in replacements:
        assert old in value, old
        value = value.replace(old, new)
    compile(value, str(target), 'exec')
    target.write_text(value, encoding='utf8', newline='\n')
    print(target)


if __name__ == '__main__':
    main()
