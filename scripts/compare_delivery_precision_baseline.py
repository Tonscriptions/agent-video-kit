"""Execute the final delivery checks on the unchanged V51 product."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASE = '409c207009b7e6bb484d01d550b64291d5b4d4df'


def sha(path):
    return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def run(output, work):
    output.mkdir(parents=True, exist_ok=False)
    work.mkdir(parents=True, exist_ok=False)
    raw = subprocess.check_output(['git', 'archive', '--format=zip', BASE,
                                   'product/src', 'docs/specs/agent-project.schema.json'], cwd=ROOT)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for item in archive.infolist():
            path = (work/item.filename).resolve()
            assert path.is_relative_to(work)
            if item.is_dir():
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.read(item))
    test = ROOT/'product/tests/test_delivery_precision.py'
    before = sha(test)
    env = dict(os.environ)
    env.update(TEMP=str(ROOT/'product/.runtime/temp'), TMP=str(ROOT/'product/.runtime/temp'),
               TMPDIR=str(ROOT/'product/.runtime/temp'), PYTHONDONTWRITEBYTECODE='1')
    bootstrap = ('import sys,unittest;sys.path[:0]=[sys.argv.pop(1),sys.argv.pop(1)];'
                 'from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();'
                 'unittest.main(module=None)')
    command = [sys.executable, '-E', '-B', '-X', 'utf8', '-c', bootstrap,
               str(work/'product/src'), str(ROOT/'product/tests'), 'discover',
               '-s', str(ROOT/'product/tests'), '-p', 'test_delivery_precision.py', '-v']
    with (output/'baseline.log').open('wb') as stream:
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=stream,
                                stderr=subprocess.STDOUT, timeout=360)
    text = (output/'baseline.log').read_text(encoding='utf-8')
    match = re.search(r'Ran (\d+) tests in ([\d.]+)s', text)
    failures = sorted(set(re.findall(r'^FAIL: (\w+)', text, re.M)))
    errors = sorted(set(re.findall(r'^ERROR: (\w+)', text, re.M)))
    assert match and result.returncode == 1 and sha(test) == before
    required = {'test_lossless_vp9_keeps_all_256_static_alpha_levels',
                'test_lossless_vp9_keeps_spatial_and_temporal_alpha_changes',
                'test_fractional_mp4_keeps_41_frames_without_lengthening_audio',
                'test_equal_length_but_delayed_audio_still_fails',
                'test_common_timestamp_offset_is_not_hidden_by_equal_start_times'}
    assert required.issubset(failures), failures
    record = {'status': 'verified_counterfactual_failures', 'base_commit': BASE, 'command': command,
              'exit_code': result.returncode, 'methods': int(match[1]), 'suite_seconds': float(match[2]),
              'failed_methods': failures, 'error_methods': errors,
              'control_passed_methods': int(match[1])-len(set(failures+errors)),
              'same_current_test_sha256': before, 'log_sha256': sha(output/'baseline.log'),
              'source_files': {p.relative_to(work).as_posix(): sha(p)
                               for p in sorted((work/'product/src').rglob('*')) if p.is_file()},
              'generator_sha256': sha(Path(__file__))}
    (output/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    (output/'executed-test.py').write_bytes(test.read_bytes())
    (output/'verification.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n',
                                          encoding='utf-8', newline='\n')
    print(json.dumps({key: record[key] for key in ('status', 'methods', 'control_passed_methods',
                                                  'failed_methods', 'error_methods')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    run(args.output.resolve(), args.work.resolve())
