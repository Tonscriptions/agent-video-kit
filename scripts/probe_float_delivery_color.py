"""Independent all-code gray oracle at the integer delivery conversion edge."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'product/src'))
from ai_ad_editor.media import ffmpeg_path


def main():
    out = ROOT/'docs/validation/evidence/float-standard-20261022-lab/color-boundary-r1'
    out.mkdir(parents=True, exist_ok=False)
    codes = np.arange(65536, dtype='<u2').reshape(256, 256)
    payload = np.tile(codes[None], (3, 1, 1)).tobytes()
    expected = 64 + codes.astype(np.float64)/65535*876
    base = 'scale=in_range=pc:out_range=tv:out_color_matrix=bt709:flags=accurate_rnd+full_chroma_int+full_chroma_inp'
    graphs = {'swscale-current': base, 'swscale-no-dither': base+':sws_dither=none',
              'zscale-explicit': 'zscale=primariesin=709:transferin=linear:matrixin=gbr:rangein=full:primaries=709:transfer=linear:matrix=709:range=limited:dither=none'}
    rows = []
    for name, graph in graphs.items():
        command = [ffmpeg_path(), '-nostdin', '-v', 'error', '-threads', '1', '-filter_threads', '1',
            '-f', 'rawvideo', '-pixel_format', 'gbrp16le', '-video_size', '256x256', '-i', 'pipe:0',
            '-vf', graph+',format=yuv444p10le', '-frames:v', '1', '-f', 'rawvideo', 'pipe:1']
        p = subprocess.run(command, input=payload, capture_output=True, timeout=60, creationflags=subprocess.CREATE_NO_WINDOW)
        (out/(name+'.yuv')).write_bytes(p.stdout)
        (out/(name+'.stderr.txt')).write_bytes(p.stderr)
        row = {'id': name, 'command': command, 'exit_code': p.returncode,
               'output_sha256': 'sha256:'+hashlib.sha256(p.stdout).hexdigest()}
        if p.returncode == 0:
            actual = np.frombuffer(p.stdout, '<u2').reshape(3, 256, 256)
            delta = actual[0].astype(np.float64)-expected
            row.update(maximum_error=float(np.max(np.abs(delta))), minimum_delta=float(delta.min()),
                maximum_delta=float(delta.max()), unique_luma_codes=len(np.unique(actual[0])),
                endpoints=[int(actual[0, 0, 0]), int(actual[0, -1, -1])],
                neutral_chroma_max_error=int(np.max(np.abs(actual[1:].astype(int)-512))))
        rows.append(row)
    record = {'status': 'measured-three-real-native-delivery-conversions', 'cases': rows,
              'input_sha256': 'sha256:'+hashlib.sha256(payload).hexdigest(),
              'oracle': 'BT709 neutral RGB full 0..65535 -> limited 10bit Y=64+876*x, Cb=Cr=512',
              'source': 'all65536 independent gray values; no product geometry or encoder',
              'network': False, 'virtualization': False,
              'script_sha256': 'sha256:'+hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (out/'verification.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf8')
    print(json.dumps(record))


if __name__ == '__main__':
    main()
