"""Observe the published kernel before selective eight-band HSL is added."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import run_frozen_regression


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    output = args.output.resolve()
    assert not output.exists() and output.is_relative_to(Path(__file__).resolve().parents[1]/'docs')
    output.parent.mkdir(parents=True, exist_ok=True)
    run_frozen_regression.ROOT = source
    before = run_frozen_regression.frozen()
    sys.path.insert(0, str(source/'product/src'))
    from ai_ad_editor import render
    from ai_ad_editor.effects import get_effect
    from ai_ad_editor.media import ffmpeg_path
    warnings = []
    requested = {'type': 'selective_hsl', 'parameters': {'red_hue': 60}}
    chain = render._effect_filters([requested], warnings, 'baseline')
    frame = bytes([230, 50, 80, 127, 25, 180, 140, 0])*32
    command = [ffmpeg_path(), '-v', 'error', '-filter_threads', '1',
               '-f', 'rawvideo', '-pixel_format', 'rgba', '-video_size', '8x8',
               '-framerate', '6', '-i', 'pipe:0', '-vf', ','.join(chain) or 'null',
               '-f', 'rawvideo', '-pix_fmt', 'rgba', 'pipe:1']
    result = subprocess.run(command, input=frame*6, capture_output=True, timeout=30)
    assert result.returncode == 0 and result.stdout == frame*6
    assert get_effect('selective_hsl') is None and not chain
    assert any(row['code'] == 'RENDER_FEATURE_UNSUPPORTED' for row in warnings)
    after = run_frozen_regression.frozen()
    assert before == after and len(before) == 223
    record = {'status': 'observed-unsupported-and-unmodified-pixels',
              'checked_at_utc': datetime.now(timezone.utc).isoformat(),
              'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source).decode().strip(),
              'source_directory': str(source), 'module_origin': render.__file__,
              'frozen_before': before, 'frozen_after': after, 'frozen_equal': True,
              'requested': requested, 'compiled_filters': chain, 'warnings': warnings,
              'native_command': command, 'frames': 6, 'decoded_bytes_equal_original': True,
              'decoded_sha256': 'sha256:'+hashlib.sha256(result.stdout).hexdigest(),
              'generator_sha256': run_frozen_regression.sha(Path(__file__)),
              'network': False, 'virtualization': False, 'new_model_inference': 0}
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    print(json.dumps({'status': record['status'], 'frozen_inputs': len(before), 'frames': 6}))


if __name__ == '__main__':
    main()
