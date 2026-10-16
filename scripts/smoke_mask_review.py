"""Publish an actual quality.mask failure/pass on procedural lossless masks."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import io
import contextlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'product/src'))
from ai_ad_editor.cli import main
from ai_ad_editor.runtime import configure_local_runtime


def sha(path): return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')


def execute(argv, data=None):
    result = subprocess.run(argv, input=data, capture_output=True, timeout=120)
    if result.returncode: raise RuntimeError(result.stderr.decode('utf-8', 'replace'))
    return result.stdout


def run(output, work):
    configure_local_runtime()
    from PIL import Image, ImageDraw, ImageFont, ImageSequence
    import PIL
    import numpy as np
    if work.exists(): raise ValueError('Use a fresh project directory; existing work is never removed')
    output.mkdir(parents=True, exist_ok=True)
    calls = []
    def cli(*argv, expected_code=0):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream): code = main(list(map(str, argv)))
        result = json.loads(stream.getvalue())
        calls.append({'argv': list(map(str, argv)), 'exit_code': code, 'result': result})
        assert code == expected_code, result
        return result
    full, bad = [], []
    for index in range(32):
        image = Image.new('RGBA', (128, 192), (70, 210, 180, 0))
        d = ImageDraw.Draw(image)
        x = (index//4)%5-2
        d.ellipse((49+x, 12, 79+x, 42), fill=(70, 210, 180, 255))
        for box in [(45+x, 47, 83+x, 128), (21+x, 50, 45+x, 115), (83+x, 50, 107+x, 115),
                    (47+x, 127, 59+x, 181), (69+x, 127, 81+x, 181)]:
            d.rectangle(box, fill=(70, 210, 180, 255))
        full.append(np.asarray(image).copy())
        copy = np.asarray(image).copy()
        if 8 <= index < 16: copy[132:185, 44+x:63+x, 3] = 0
        bad.append(copy)
    full, bad = np.stack(full), np.stack(bad)
    for name, frames in [('mask-full.mov', full), ('mask-under-test.mov', bad)]:
        execute(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', '128x192', '-r', '8',
                 '-i', 'pipe:0', '-an', '-c:v', 'qtrle', '-pix_fmt', 'argb', str(output/name)], frames.tobytes())
    expectations = output/'expectations.json'
    x = (12//4)%5-2
    save(expectations, {'version': '1.0.0', 'coordinate_space': 'normalized-output', 'frames': [
        {'frame': 0, 'points': [{'x': .5, 'y': .4, 'expected': 'selected'}, {'x': .95, 'y': .95, 'expected': 'clear'}]},
        {'frame': 12, 'points': [{'x': (53+x)/128, 'y': 160/192, 'expected': 'selected', 'radius_pixels': 2}]},
        {'frame': 24, 'points': [{'x': .5, 'y': .4, 'expected': 'selected'}]}]})
    provenance = output/'fixture-provenance.json'
    save(provenance, {'kind': 'procedural-mask-review-regression-fixture', 'generator': 'scripts/smoke_mask_review.py',
                      'generator_sha256': sha(Path(__file__)), 'license_spdx': 'CC0-1.0', 'learned_model_runs': 0,
                      'change': 'Remove left leg alpha in frames 8..15; corrected fixture restores the authored geometry, not a model repair',
                      'third_party_natural_media': False, 'raster_preview_labels': 'Pillow built-in load_default; no font binary redistributed',
                      'source_sha256': {p.name: sha(p) for p in [output/'mask-full.mov', output/'mask-under-test.mov', expectations]}})
    cli('project', 'init', work, '--name', 'Public mask expectation failure and pass')
    for asset_id, name in [('full', 'mask-full.mov'), ('under_test', 'mask-under-test.mov')]:
        cli('media', 'ingest', '--project', work, '--input', output/name, '--asset-id', asset_id, '--source-url', 'local://procedural-mask-fixture',
            '--license-spdx', 'CC0-1.0', '--evidence', provenance, '--verification-status', 'verified', '--permitted-use', 'commercial_ad')
    before = {name: sha(work/name) for name in ['project.json', 'rights-ledger.json']}
    cli('quality', 'mask', '--project', work, '--asset-id', 'under_test', '--expectations', expectations, '--dry-run')
    failed = cli('quality', 'mask', '--project', work, '--asset-id', 'under_test', '--expectations', expectations,
                 '--report', 'validation/under-test.json', expected_code=2)
    passed = cli('quality', 'mask', '--project', work, '--asset-id', 'full', '--expectations', expectations, '--report', 'validation/full.json')
    assert before == {name: sha(work/name) for name in before}
    assert len(failed['data']['failed_points']) == 1 and failed['data']['failed_points'][0]['frame'] == 12
    assert passed['data']['checked_points'] == 4 and not passed['data']['failed_points']
    assert failed['data']['gray_sha256'] == 'sha256:'+hashlib.sha256(bad[:, :, :, 3].tobytes()).hexdigest()
    assert passed['data']['gray_sha256'] == 'sha256:'+hashlib.sha256(full[:, :, :, 3].tobytes()).hexdigest()
    for name, response in [('under-test-report.json', failed), ('full-report.json', passed)]: save(output/name, response['data'])
    panels = []
    for index in range(32):
        canvas = Image.new('RGB', (576, 248), '#101c2a'); d = ImageDraw.Draw(canvas)
        for col, (array, title) in enumerate([(full, 'FULL INPUT'), (bad, 'MASK UNDER TEST'), (full, 'CORRECTED FIXTURE')]):
            rgb = np.full((192, 128, 3), [23, 41, 58], np.uint8)
            rgb[array[index, :, :, 3] > 127] = [70, 210, 180]
            image = Image.fromarray(rgb).resize((128, 192))
            canvas.paste(image, (col*192+32, 30))
            d.text((col*192+8, 8), title, fill='white', font=ImageFont.load_default(size=14))
            if col == 1 and index == 12:
                cx = 192+32+53+x
                d.ellipse((cx-6, 30+154, cx+6, 30+166), outline='#ff615e', width=2)
        label = 'EXPECTED CHECK FAILURE / FRAME 12' if index == 12 else f'FRAME {index:02d}/31 | 8 FPS | PROCEDURAL / NO MODEL REPAIR'
        d.text((8, 229), label, fill='#ff8e89' if index == 12 else '#b9cddd', font=ImageFont.load_default(size=12))
        panels.append(np.asarray(canvas))
    array = np.stack(panels)
    mp4 = output/'mask-review-comparison.mp4'
    execute(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '576x248', '-r', '8', '-i', 'pipe:0',
             '-an', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-movflags', '+faststart', str(mp4)], array.tobytes())
    images = [Image.fromarray(frame).quantize(colors=64) for frame in panels]
    images[0].save(output/'mask-review-comparison.gif', save_all=True, append_images=images[1:],
                   duration=[120, 130]*16, loop=0, disposal=2, optimize=False)
    Image.fromarray(panels[12]).save(output/'contact-frame-12.png')
    probe = json.loads(execute(['ffprobe', '-v', 'error', '-count_frames', '-show_streams', '-of', 'json', str(mp4)]))
    assert probe['streams'][0]['nb_read_frames'] == '32' and probe['streams'][0]['avg_frame_rate'] == '8/1'
    decoded = execute(['ffmpeg', '-v', 'error', '-i', str(mp4), '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1'])
    assert len(decoded) == 32*576*248*3
    with Image.open(output/'mask-review-comparison.gif') as handle:
        durations = [frame.info['duration'] for frame in ImageSequence.Iterator(handle)]
        assert len(durations) == 32 and sum(durations) == 4000
    save(output/'evidence.json', {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'generator_sha256': sha(Path(__file__)),
         'source_sha256': {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted((ROOT/'product/src/ai_ad_editor').glob('*.py'))},
         'calls': calls, 'expected_failed_command_count': 1, 'expected_failed_points': 1, 'passed_points': 4,
         'project_and_ledger_unchanged_by_review': True, 'all_decoded_alpha_bytes_match_authored_arrays': True,
         'preview': {'probe': probe, 'gif_frames': len(durations), 'gif_frame_durations_ms': sorted(set(durations)), 'gif_total_ms': sum(durations), 'mp4_all_frames_decoded': True},
         'numpy_and_pillow_used_by_demo_only': {'numpy': np.__version__, 'pillow': PIL.__version__},
         'learned_model_runs': 0, 'natural_video_quality_accepted': False,
         'files': {p.name: {'sha256': sha(p), 'bytes': p.stat().st_size} for p in sorted(output.iterdir()) if p.is_file() and p.name != 'evidence.json'}})
    print(json.dumps({'expected_failure': 1, 'passing_checks': 4, 'output': str(output)}), flush=True)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path, required=True)
    args = parser.parse_args()
    run(args.output_dir.resolve(), args.work_dir.resolve())
