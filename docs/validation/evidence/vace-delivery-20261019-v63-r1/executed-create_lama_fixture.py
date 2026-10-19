"""Create a deterministic moving-object fixture with known unoccluded pixels."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'product/src'))
from ai_ad_editor.media import ffmpeg_path, ffmpeg_version
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.utils import atomic_write_json, sha256_file


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', required=True)
    args = parser.parse_args()
    root = Path(args.output_root).resolve()
    if root.exists(): parser.error('Use a new local output root')
    configure_local_runtime(); root.mkdir(parents=True)
    width, height, frames = 192, 128, 8
    x, y = np.meshgrid(np.arange(width), np.arange(height))
    background = np.empty((height, width, 4), np.uint8)
    background[:, :, 0] = np.rint(55 + x * .65 + y * .15).astype(np.uint8)
    background[:, :, 1] = np.rint(85 + x * .3 + y * .45).astype(np.uint8)
    background[:, :, 2] = np.rint(180 - x * .35 + y * .15).astype(np.uint8)
    background[:, :, 3] = 255; background[:8, :8, 3] = 128
    truth = np.repeat(background[None], frames, axis=0); source = truth.copy(); mask = np.zeros_like(source)
    for index in range(1, frames):
        x1, y1 = 66 + index * 2, 48 + index
        source[index, y1:y1 + 26, x1:x1 + 30, :3] = [235, 25, 35]
        source[index, y1 + 4:y1 + 22, x1 + 5:x1 + 25, :3] = [30, 45, 230]
        mask[index, y1:y1 + 26, x1:x1 + 30, 3] = 255
    for name, array, audio in [('source.mov', source, True), ('mask.mov', mask, False)]:
        command = [ffmpeg_path(), '-nostdin', '-hide_banner', '-loglevel', 'error', '-n', '-f', 'rawvideo', '-pixel_format', 'rgba', '-video_size', f'{width}x{height}', '-framerate', '8', '-i', 'pipe:0']
        if audio: command += ['-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000']
        command += ['-t', '1', '-c:v', 'qtrle', '-pix_fmt', 'argb']
        if audio: command += ['-c:a', 'pcm_s16le']
        subprocess.run([*command, str(root / name)], input=array.tobytes(), capture_output=True, check=True)
    np.savez_compressed(root / 'ground-truth.npz', frames=truth)
    manifest = {'scope': 'controlled synthetic background only; no broad or natural-footage quality claim', 'width': width, 'height': height, 'frames': frames, 'fps': '8',
                'empty_mask_frames': 1, 'soft_source_alpha': 128, 'generator_sha256': 'sha256:' + sha256_file(Path(__file__)), 'ffmpeg': ffmpeg_version(),
                'artifacts': {name: 'sha256:' + sha256_file(root / name) for name in ['source.mov', 'mask.mov', 'ground-truth.npz']}}
    atomic_write_json(root / 'fixture.json', manifest)
    print(str(root / 'fixture.json'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
