"""Establish actual native Float32/NUT and 16-bit-alpha PNG round trips."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'product/src'))
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.media import ffmpeg_path


def main():
    configure_local_runtime()
    work = ROOT/'product/.runtime/float-preview-20261022/formats-r1'
    work.mkdir(parents=True, exist_ok=False)
    receipt = ROOT/'docs/validation/evidence/float-preview-20261022-lab/formats-r1.json'
    calls = []
    def call(args, payload=None):
        command = [ffmpeg_path(), '-nostdin', '-hide_banner', '-v', 'error', *map(str, args)]
        value = subprocess.run(command, input=payload, capture_output=True, timeout=60, cwd=ROOT,
                               creationflags=subprocess.CREATE_NO_WINDOW)
        calls.append({'command': command, 'exit_code': value.returncode,
                      'stdout_bytes': len(value.stdout), 'stdout_sha256': hashlib.sha256(value.stdout).hexdigest(),
                      'stderr': value.stderr.decode('utf8', 'replace')})
        return value
    values = np.linspace(0, 1, 3*4*8*8, dtype=np.float32).reshape(3, 4, 8, 8)
    values[0, 0, 0, :4] = [.12345678, .12345679, -.01, 1.01]
    source = values.astype('<f4').tobytes()
    movie = work/'master.nut'
    encoded = call(['-f', 'rawvideo', '-pixel_format', 'gbrapf32le', '-video_size', '8x8', '-framerate', '30000/1001',
                    '-i', 'pipe:0', '-c:v', 'rawvideo', '-pix_fmt', 'gbrapf32le', '-f', 'nut', movie], source)
    decoded = call(['-i', movie, '-f', 'rawvideo', '-pix_fmt', 'gbrapf32le', 'pipe:1']) if not encoded.returncode else None
    rgba16 = np.arange(8*8*4, dtype='<u2').reshape(8, 8, 4)*257
    rgba16[1, :, 3] = np.arange(8)*8191+1
    png = work/'frame.png'
    png_encode = call(['-f', 'rawvideo', '-pixel_format', 'rgba64le', '-video_size', '8x8', '-framerate', '1',
                       '-i', 'pipe:0', '-frames:v', '1', '-c:v', 'png', '-pix_fmt', 'rgba64be', png], rgba16.tobytes())
    png_decode = call(['-i', png, '-f', 'rawvideo', '-pix_fmt', 'rgba64le', 'pipe:1']) if not png_encode.returncode else None
    checks = {'float32_nut_bit_exact_including_negative_and_over_one': decoded is not None and decoded.returncode == 0 and decoded.stdout == source,
              'png16_independent_alpha_bit_exact': png_decode is not None and png_decode.returncode == 0 and png_decode.stdout == rgba16.tobytes()}
    result = {'status': 'passed' if all(checks.values()) else 'failed', 'checks': checks, 'commands': calls,
              'native_windows': True, 'virtualization': False, 'network': False,
              'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    receipt.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    print(json.dumps({'status': result['status'], 'checks': checks}))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
