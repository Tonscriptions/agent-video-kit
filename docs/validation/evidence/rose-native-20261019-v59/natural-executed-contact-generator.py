"""Publish actual ROSE research output and byte-verified original comparisons.

Only the procedural CC0 case is public. Natural pixels and all weights remain
in ignored local storage. Publishing executes no model or browser.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from prepare_rose_research import sha, save
from run_rose_research import command, decode, scores
from smoke_fragments import frozen


def contact_sheet(views, titles, output):
    """Make the same four-frame static aid for public and private inspection."""
    from PIL import Image, ImageDraw, ImageFont
    if not views or len(views) != len(titles):
        raise ValueError('ROSE_CONTACT_VIEWS_AND_TITLES_REQUIRED')
    _, h, w, _ = views[0][1].shape
    if any(values.shape != (32, h, w, 4) for _, values in views):
        raise ValueError('ROSE_CONTACT_EXPECTS_SAME_32_FRAME_GEOMETRY')
    font = ImageFont.load_default(size=16)
    canvas = Image.new('RGB', (w*4, (h+24)*len(views)), '#101722')
    draw = ImageDraw.Draw(canvas)
    for row, ((_, values), title) in enumerate(zip(views, titles)):
        for col, index in enumerate((0, 10, 21, 31)):
            x, y = col*w, row*(h+24)
            draw.text((x+6, y+2), f'{title} / frame {index}', fill='white', font=font)
            canvas.paste(Image.fromarray(values[index, :, :, :3]), (x, y+24))
    canvas.save(output)


def publish(public, natural, prepared, acquisition, assets, evidence):
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    assets.mkdir(parents=True, exist_ok=False)
    evidence.mkdir(parents=True, exist_ok=False)
    (evidence/'executed-publisher.py').write_bytes(Path(__file__).read_bytes())
    shutil.copyfile(ROOT/'docs/validation/ROSE本地模型获取与离线预检_2026-10-19.md',
                    evidence/'historical-preflight-report.md')
    shutil.copyfile(ROOT/'skills/video-cut-local-models/SKILL.md',
                    evidence/'historical-preflight-SKILL.md')
    before = frozen()
    records = {}
    for name, work in [('public', public), ('natural', natural)]:
        record = json.loads((work/'verification.json').read_bytes())
        if record['status'] != 'execution_verified_quality_unaccepted' or record['product_integrated']:
            raise ValueError('ROSE_REAL_RESEARCH_RESULT_REQUIRED')
        if json.loads((work/'product-before.json').read_bytes()) != before or json.loads((work/'product-after.json').read_bytes()) != before:
            raise ValueError('ROSE_PRODUCT_INPUTS_NOT_FROZEN')
        observation = json.loads((work/'windows-process-monitor.json').read_bytes())
        if observation['status'] != 'monitor_ended' or not observation['read_only'] or observation['samples'] < 1:
            raise ValueError('ROSE_COMPLETED_READ_ONLY_PROCESS_OBSERVATION_REQUIRED')
        record['windows_process_observation'] = observation
        records[name] = record
        for file in ('case.json', 'request.json', 'verification.json', 'worker-response.json', 'worker.log',
                     'executed-runner.py', 'executed-worker.py', 'windows-process-monitor.json',
                     'windows-process-samples.jsonl', 'executed-process-monitor.py'):
            shutil.copyfile(work/file, evidence/(name+'-'+file))
        execution_log = work.parent/(work.name+'-execution.log')
        shutil.copyfile(execution_log, evidence/(name+'-parent-execution.log'))
        if (work/'gpu-resource-snapshots.jsonl').is_file():
            record['global_gpu_snapshots'] = [json.loads(line) for line in
                (work/'gpu-resource-snapshots.jsonl').read_text(encoding='utf-8').splitlines()]
            for file in ('gpu-resource-snapshots.jsonl', 'executed-gpu-sampler.py'):
                shutil.copyfile(work/file, evidence/(name+'-'+file))
    raw = np.load(public/'output/raw-result.npy', allow_pickle=False)
    original = np.load(public/'input.npy', allow_pickle=False)
    result = np.load(public/'final.npy', allow_pickle=False)
    truth = np.load(public/'independent-truth.npy', allow_pickle=False)
    mask = np.load(public/'effective-selection.npy', allow_pickle=False)
    lama = np.load(public/'lama.npy', allow_pickle=False)
    fgt = np.load(public/'fgt.npy', allow_pickle=False)
    raw_rgba = original.copy()
    raw_rgba[:, :, :, :3] = raw
    views = [('source', original), ('lama', lama), ('fgt', fgt),
             ('rose-raw', raw_rgba), ('rose-selected', result), ('truth', truth)]
    master_records = []
    for name, rgba in views:
        n, h, w, _ = rgba.shape
        path = assets/(name+'-lossless.mp4')
        command(['ffmpeg', '-nostdin', '-v', 'error', '-f', 'rawvideo', '-pixel_format', 'rgba',
                 '-video_size', f'{w}x{h}', '-framerate', '8', '-i', 'pipe:0', '-an',
                 '-c:v', 'libx264rgb', '-crf', '0', '-preset', 'medium', '-pix_fmt', 'rgb24',
                 '-video_track_timescale', '8', '-movflags', '+faststart', path], data=rgba.tobytes())
        decoded = decode(path, n, h, w)
        if not np.array_equal(decoded, rgba):
            raise RuntimeError('ROSE_PUBLIC_LOSSLESS_MASTER_MISMATCH: '+name)
        from fractions import Fraction
        info = json.loads(command(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_frames',
            '-show_entries', 'frame=pts_time', '-of', 'json', path]))
        if [Fraction(x['pts_time']) for x in info['frames']] != [Fraction(i, 8) for i in range(n)]:
            raise RuntimeError('ROSE_PUBLIC_PTS_MISMATCH: '+name)
        master_records.append({'name': name, 'frames': n, 'width': w, 'height': h, 'fps': '8/1',
            'decoded_rgba_sha256': 'sha256:'+hashlib.sha256(decoded.tobytes()).hexdigest(),
            'decoded_rgba_bytes': decoded.nbytes, 'exact_rgba': True, 'every_pts_exact': True,
            'opaque_alpha_only': True})
        command(['ffmpeg', '-nostdin', '-v', 'error', '-i', path, '-an', '-c:v', 'libx264',
                 '-crf', '18', '-pix_fmt', 'yuv420p', '-video_track_timescale', '8',
                 '-movflags', '+faststart', assets/(name+'.mp4')])
    font = ImageFont.load_default(size=16)
    titles = ['Original occluded source', 'LaMa (historical)', 'FGT (historical)',
              'ROSE raw full frame', 'ROSE selected region only', 'Independent hidden truth']
    n, h, w, _ = original.shape
    panels = []
    for index in range(n):
        frame = Image.new('RGB', (w*3, (h+24)*2), '#101722')
        draw = ImageDraw.Draw(frame)
        for j, ((_, values), title) in enumerate(zip(views, titles)):
            x, y = (j % 3)*w, (j//3)*(h+24)
            draw.text((x+8, y+2), title, fill='white', font=font)
            frame.paste(Image.fromarray(values[index, :, :, :3]), (x, y+24))
        panels.append(frame)
    rgb = np.stack([np.asarray(x) for x in panels])
    command(['ffmpeg', '-nostdin', '-v', 'error', '-f', 'rawvideo', '-pixel_format', 'rgb24',
             '-video_size', f'{w*3}x{(h+24)*2}', '-framerate', '8', '-i', 'pipe:0', '-an',
             '-c:v', 'libx264', '-crf', '17', '-pix_fmt', 'yuv420p', '-video_track_timescale', '8',
             '-movflags', '+faststart', assets/'comparison.mp4'], data=rgb.tobytes())
    gif = [x.resize((w*3//2, h+24), Image.Resampling.LANCZOS).quantize(colors=128) for x in panels]
    durations = [120 if i % 2 == 0 else 130 for i in range(n)]
    gif[0].save(assets/'comparison.gif', save_all=True, append_images=gif[1:], duration=durations,
                loop=0, disposal=2, optimize=False)
    with Image.open(assets/'comparison.gif') as check:
        if check.n_frames != 32:
            raise RuntimeError('ROSE_GIF_FRAME_COUNT_CHANGED')
        actual_durations = []
        for i in range(check.n_frames):
            check.seek(i)
            actual_durations.append(check.info['duration'])
        if actual_durations != durations:
            raise RuntimeError('ROSE_GIF_CLOCK_CHANGED')
    # A contact sheet is a static inspection aid, never a continuous-play review.
    contact_sheet(views, titles, assets/'contact.png')
    static_review = json.loads((public/'static-review.json').read_bytes())
    if (static_review['contact_sha256'] != sha(assets/'contact.png')
            or static_review['contact_generator_sha256'] != sha(public/'executed-contact-generator.py')
            or static_review['frame_indices'] != [0, 10, 21, 31]
            or static_review['continuous_playback_reviewed'] or static_review['audio_listening_reviewed']):
        raise ValueError('ROSE_PUBLIC_STATIC_REVIEW_DOES_NOT_MATCH_PUBLISHED_CONTACT')
    for file in ('static-review.json', 'executed-contact-generator.py'):
        shutil.copyfile(public/file, evidence/('public-'+file))
    # Natural contact remains private. No natural source/result pixels are copied.
    private_source = np.load(natural/'input.npy', allow_pickle=False)
    private_result = np.load(natural/'final.npy', allow_pickle=False)
    contact_sheet([('source', private_source), ('selected', private_result)],
                  ['Private source', 'ROSE selected only'], natural/'private-contact.png')
    prep = json.loads((prepared/'preparation.json').read_bytes())
    origin = ROOT/'product/.runtime/temporal-model-audit-20261018/Kunbyte-AI__ROSE/source'
    original_archive = evidence/'pinned-original-core.zip'
    with zipfile.ZipFile(original_archive, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for row in prep['original_files']:
            path = origin/row['path']
            if sha(path) != row['sha256']:
                raise ValueError('ROSE_ORIGINAL_SOURCE_CHANGED')
            archive.writestr(row['path'], path.read_bytes())
    for file in ('preparation.json', 'compatibility.patch', 'executed-preparer.py'):
        shutil.copyfile(prepared/file, evidence/file)
    acquisition_dir = acquisition.parent
    for path in acquisition_dir.iterdir():
        if path.is_file():
            shutil.copyfile(path, evidence/('acquisition-'+path.name))
    provenance = {'source': 'unchanged V44 procedural CC0-1.0 fixture; scripts/run_fgt_research.py: public_fixture',
        'source_truth_license': 'CC0-1.0', 'model_outputs': 'actual ROSE/FGT/LaMa research; not a production quality acceptance',
        'new_model': 'ROSE author Transformer + Wan author T5 and VAE; no CLIP reference',
        'frames': 32, 'model_frames': 33, 'fps': '8/1', 'duration_seconds': 4,
        'alpha': 'all source alpha is 255; RGB H.264 cannot prove arbitrary-alpha preservation',
        'lossless_masters': master_records, 'display_mp4_and_gif': 'lossy display derivatives; not used for pixel scores',
        'gif_frame_durations_ms': durations, 'audio': False, 'natural_pixels_published': False,
        'raw_and_selected_outputs_separate': True, 'generator_sha256': sha(Path(__file__))}
    save(assets/'provenance.json', provenance)
    after = frozen()
    if before != after:
        raise ValueError('ROSE_PRODUCTION_BYTES_CHANGED_WHILE_PUBLISHING')
    files = [{'path': p.relative_to(ROOT).as_posix(), 'sha256': sha(p), 'bytes': p.stat().st_size}
             for folder in (assets, evidence) for p in sorted(folder.iterdir()) if p.is_file()]
    result = {'status': 'actual_inference_published_quality_unaccepted', 'product_integrated': False,
        'research_only': True, 'public': records['public'], 'natural': records['natural'],
        'public_master_count': len(master_records), 'public_lossless_master_frames': sum(r['frames'] for r in master_records),
        'production_files_frozen': len(before), 'production_sha256': before, 'files': files,
        'model_calls_during_publication': 0, 'natural_pixels_published': False,
        'public_static_contact_reviewed': True, 'natural_static_contact_reviewed_at_publication': False,
        'private_contact_sha256': sha(natural/'private-contact.png'),
        'full_product_regression_rerun': False, 'latest_historical_regression': 'V58 1357/1357',
        'continuous_playback_reviewed': False, 'audio_listening_reviewed': False}
    save(evidence/'verification.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('public', 'natural', 'prepared', 'acquisition', 'assets', 'evidence'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    publish(**{k: v.resolve() for k, v in vars(args).items()})
