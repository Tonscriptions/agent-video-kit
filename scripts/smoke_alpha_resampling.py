"""Reproduce real CLI alpha-resize outputs against an archived local Git baseline."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASELINE = '5790433af0ca4119b3c7eba9816e27accb2dd949'


def sha(path):
    return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')


def run(output, work):
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont, ImageSequence
    import PIL

    if work.exists() or output.exists():
        raise ValueError('Use fresh output and work directories; existing evidence is never overwritten')
    work.mkdir(parents=True)
    output.mkdir(parents=True)
    archive = subprocess.run(['git', '-c', 'core.autocrlf=false', 'archive', '--format=zip', BASELINE, 'product/src'], cwd=ROOT, capture_output=True, check=True).stdout
    baseline = work/'baseline'
    with zipfile.ZipFile(io.BytesIO(archive)) as package:
        for name in package.namelist():
            if name in {'product/', 'product/src/'}:
                continue
            if not name.startswith('product/src/') or not (baseline/name).resolve().is_relative_to(baseline.resolve()):
                raise ValueError('Unexpected baseline archive path')
        package.extractall(baseline)
    baseline_src = baseline/'product/src'
    current_src = ROOT/'product/src'
    baseline_render_hash = sha(baseline_src/'ai_ad_editor/render.py')
    current_render_hash = sha(current_src/'ai_ad_editor/render.py')
    project = work/'project'
    calls = []
    bootstrap = 'import sys; sys.path.insert(0,sys.argv.pop(1)); from ai_ad_editor.runtime import configure_local_runtime; configure_local_runtime(); from ai_ad_editor.cli import main; raise SystemExit(main())'

    def cli(*args, baseline=False):
        began = time.monotonic()
        src = baseline_src if baseline else current_src
        result = subprocess.run([sys.executable, '-I', '-B', '-X', 'utf8', '-c', bootstrap, str(src), *map(str, args)], cwd=ROOT, capture_output=True, timeout=180)
        value = json.loads(result.stdout.decode('utf-8-sig'))
        calls.append({'argv': list(map(str, args)), 'baseline': baseline, 'source_path': str(src), 'exit_code': result.returncode, 'seconds': time.monotonic()-began, 'result': value})
        save(work/'partial-calls.json', calls)
        if result.returncode:
            raise RuntimeError(value)
        return value

    def compose(operations):
        path = work/'changes.json'
        save(path, {'operations': operations})
        cli('timeline', 'compose', '--project', project, '--input', path)

    def ffmpeg(args, data=None):
        result = subprocess.run(['ffmpeg', '-v', 'error', *args], input=data, capture_output=True, timeout=180)
        if result.returncode:
            raise RuntimeError(result.stderr.decode('utf-8', 'replace'))
        return result.stdout

    def decode(path):
        raw = ffmpeg(['-i', str(path), '-map', '0:v:0', '-an', '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1'])
        return np.frombuffer(raw, np.uint8).reshape(-1, 288, 512, 3)

    frames = []
    centers = []
    for i in range(32):
        x = 56+12*i
        y = 144+round(38*math.sin(i*math.pi/15.5))
        image = Image.new('RGB', (512, 288), '#16354d')
        draw = ImageDraw.Draw(image)
        draw.rectangle((256, 0, 511, 287), fill='#ddd8ca')
        for gx in range(0, 512, 32):
            draw.line((gx, 0, gx, 287), fill='#5e8091' if gx < 256 else '#b9b2a3')
        draw.rounded_rectangle((x-28, y-48, x+27, y+47), radius=9, fill='#3bbda6')
        draw.rectangle((x-20, y-20, x+19, y+17), fill='#f5eee3')
        frames.append(np.asarray(image).copy())
        centers.append([float(x), float(y)])
    ffmpeg(['-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '512x288', '-r', '8', '-i', 'pipe:0', '-an', '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p', str(output/'source.mp4')], np.stack(frames).tobytes())
    marker = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(marker)
    draw.ellipse((8, 8, 55, 55), outline=(255, 0, 255, 255), width=4)
    draw.line((0, 31, 63, 31), fill=(255, 0, 255, 255), width=2)
    draw.line((31, 0, 31, 63), fill=(255, 0, 255, 255), width=2)
    marker.save(output/'marker-black.png')
    green = np.asarray(marker).copy()
    green[green[:, :, 3] == 0, :3] = (0, 255, 0)
    Image.fromarray(green).save(output/'marker-green.png')
    save(output/'truth.json', {'centers_source_pixels': centers, 'transparent_rgb_only_differs': True, 'scale': .09})
    provenance = output/'fixture-provenance.json'
    save(provenance, {'license_spdx': 'CC0-1.0', 'author': 'Agent Video Kit synthetic fixture', 'generated_by': 'scripts/smoke_alpha_resampling.py', 'third_party_media': False, 'learned_model_inference': False, 'font_binary_distributed': False, 'audio': False, 'inputs': {n: sha(output/n) for n in ['source.mp4', 'marker-black.png', 'marker-green.png', 'truth.json']}})
    cli('project', 'init', project, '--name', 'Alpha resampling hidden RGB invariance')
    for asset, name in [('source', 'source.mp4'), ('marker_black', 'marker-black.png'), ('marker_green', 'marker-green.png')]:
        cli('media', 'ingest', '--project', project, '--input', output/name, '--asset-id', asset, '--source-url', 'local://authored-alpha-resampling-fixture', '--license-spdx', 'CC0-1.0', '--evidence', provenance, '--verification-status', 'verified', '--permitted-use', 'commercial_ad')
    value = json.loads((project/'project.json').read_text(encoding='utf-8-sig'))
    value['settings']['canvas'].update(width=512, height=288)
    value['settings']['timebase']['display_fps'] = {'num': 8, 'den': 1}
    save(project/'project.json', value)
    keyframes = []
    for axis, extent in [(0, 512), (1, 288)]:
        keys = [{'at_tick': i*11250, 'value': c[axis]/extent, 'interpolation': 'linear'} for i, c in enumerate(centers)]
        keys.append({**keys[-1], 'at_tick': 360000})
        keyframes.append({'property': 'transform.position.'+('x' if axis == 0 else 'y'), 'keyframes': keys})
    compose([{'op': 'append_clip', 'track_id': 'track_video_1', 'id': 'source_clip', 'asset_id': 'source', 'source_in_tick': 0, 'source_out_tick': 360000}, {'op': 'add_track', 'track_id': 'labels', 'kind': 'video', 'order': 3}, {'op': 'append_clip', 'track_id': 'labels', 'id': 'label_clip', 'asset_id': 'marker_black', 'source_in_tick': 0, 'source_out_tick': 360000, 'duration_tick': 360000, 'transform': {'scale': .09}, 'keyframes': keyframes}])
    for color in ['black', 'green']:
        if color == 'green':
            compose([{'op': 'update_clip', 'track_id': 'labels', 'clip_id': 'label_clip', 'patch': {'asset_id': 'marker_green'}}])
        for prefix in ['before', 'after']:
            rendered = project/f'renders/{prefix}-{color}.mp4'
            cli('render', '--project', project, '--output', rendered, '--publish', baseline=(prefix == 'before'))
            shutil.copy2(rendered, output/rendered.name)
            shutil.copy2(Path(str(rendered)+'.manifest.json'), output/(rendered.name+'.manifest.json'))
    decoded = {n: decode(output/(n+'.mp4')) for n in ['source', 'before-black', 'before-green', 'after-black', 'after-green']}
    invariance = {}
    for prefix in ['before', 'after']:
        diff = np.abs(decoded[prefix+'-black'].astype(np.int16)-decoded[prefix+'-green'].astype(np.int16))
        invariance[prefix] = {'maximum_rgb_difference': int(diff.max()), 'changed_rgb_components': int(np.count_nonzero(diff)), 'mean_absolute_rgb_difference': float(diff.mean()), 'frames': 32}
    assert invariance['before']['maximum_rgb_difference'] > 0
    assert invariance['after']['maximum_rgb_difference'] == 0, invariance
    previews = []
    for i in range(32):
        sheet = Image.new('RGB', (1152, 320), '#142131')
        draw = ImageDraw.Draw(sheet)
        for col, (name, title) in enumerate([('source', 'ORIGINAL'), ('before-black', 'BEFORE / STRAIGHT RGB'), ('after-black', 'AFTER / PREMULTIPLIED')]):
            draw.text((col*384+8, 6), title, fill='white', font=ImageFont.load_default(size=16))
            sheet.paste(Image.fromarray(decoded[name][i]).resize((384, 216), Image.Resampling.LANCZOS), (col*384, 32))
            x, y = centers[i]
            inset = Image.fromarray(decoded[name][i]).crop((int(x)-16, int(y)-16, int(x)+16, int(y)+16)).resize((64, 64), Image.Resampling.NEAREST)
            sheet.paste(inset, (col*384+8, 252))
            draw.text((col*384+82, 268), 'actual decoded pixels / 2x', fill='white')
        previews.append(sheet)
    ffmpeg(['-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '1152x320', '-r', '8', '-i', 'pipe:0', '-an', '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p', str(output/'alpha-resampling-comparison.mp4')], np.stack([np.asarray(f) for f in previews]).tobytes())
    previews[0].save(output/'alpha-resampling-comparison.gif', save_all=True, append_images=previews[1:], duration=[120, 130]*16, loop=0, optimize=False, disposal=2)
    previews[16].save(output/'contact-frame-16.png')
    with Image.open(output/'alpha-resampling-comparison.gif') as gif:
        durations = [f.info['duration'] for f in ImageSequence.Iterator(gif)]
        assert len(durations) == 32 and sum(durations) == 4000
    probes = {}
    for name in ['source.mp4', 'before-black.mp4', 'before-green.mp4', 'after-black.mp4', 'after-green.mp4', 'alpha-resampling-comparison.mp4']:
        result = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,avg_frame_rate,nb_read_frames,duration', '-of', 'json', str(output/name)], capture_output=True, check=True)
        video = json.loads(result.stdout)['streams'][0]
        assert int(video['nb_read_frames']) == 32 and video['avg_frame_rate'] == '8/1' and float(video['duration']) == 4.
        probes[name] = video
    hashes = {p.name: sha(p) for p in sorted(output.iterdir()) if p.is_file()}
    record = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'baseline_ref': BASELINE, 'baseline_render_sha256': baseline_render_hash, 'current_render_sha256': current_render_hash, 'script_sha256': sha(Path(__file__)), 'fixture': {'width': 512, 'height': 288, 'frames': 32, 'fps': 8, 'seconds': 4, 'scale': .09, 'license_spdx': 'CC0-1.0'}, 'cli_calls': calls, 'hidden_rgb_invariance': invariance, 'probes': probes, 'gif': {'frames': 32, 'durations_ms': durations, 'total_duration_ms': sum(durations)}, 'file_sha256': hashes, 'new_inference_runs': 0, 'continuous_playback_reviewed': False, 'audio_tested': False, 'natural_quality_accepted': False}
    save(output/'evidence.json', record)
    assert sha(current_src/'ai_ad_editor/render.py') == current_render_hash
    print(json.dumps({'calls': len(calls), 'hidden_rgb_invariance': invariance, 'output': str(output)}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path, required=True)
    args = parser.parse_args()
    run(args.output_dir.resolve(), args.work_dir.resolve())
