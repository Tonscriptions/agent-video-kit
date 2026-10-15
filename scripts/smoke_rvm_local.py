"""Exercise existing local RVM weights through CLI, alpha composition and gates."""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'product/src'))
from ai_ad_editor.cli import main as cli_main
from ai_ad_editor.media import ffmpeg_path
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.utils import atomic_write_json, now_iso, sha256_file


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'model', 'python', 'evidence', 'output-root'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--max-edge', type=int, default=512)
    args = parser.parse_args()
    configure_local_runtime()
    for name in ('source', 'model', 'python', 'evidence'):
        if not Path(getattr(args, name)).is_file():
            parser.error('All input paths must already exist locally: ' + name)
    root = Path(args.output_root).resolve()
    if root.exists():
        parser.error('Use a new output root')
    root.mkdir(parents=True)
    checks = []
    def invoke(*argv, expected=0):
        capture = io.StringIO()
        with contextlib.redirect_stdout(capture):
            code = cli_main(list(argv))
        value = json.loads(capture.getvalue())
        checks.append({'command': value['command'], 'status': value['status'], 'exit_code': code})
        print(json.dumps(checks[-1]), flush=True)
        if code != expected:
            raise RuntimeError(capture.getvalue())
        return value
    project = root / 'project'
    invoke('project', 'init', str(project))
    source = invoke('media', 'ingest', '--project', str(project), '--input', str(Path(args.source).resolve()))['data']['asset']
    registration = ['media', 'adapter', 'register', '--project', str(project), '--adapter-id', 'rvm_local', '--engine', 'rvm-onnx-cpu-matting-v1',
                    '--model-path', str(Path(args.model).resolve()), '--executable', str(Path(args.python).resolve()), '--evidence', str(Path(args.evidence).resolve())]
    invoke(*registration, '--dry-run')
    adapter = invoke(*registration)['data']['adapter']
    inspected = invoke('media', 'adapter', 'inspect', '--project', str(project), '--adapter-id', 'rvm_local')
    assert inspected['data']['verification']['ok']
    changes = project / 'cache' / 'setup.json'
    atomic_write_json(changes, {'operations': [{'op': 'add_track', 'track_id': 'cutout', 'kind': 'video', 'order': 2}]})
    invoke('timeline', 'compose', '--project', str(project), '--input', str(changes))
    matting = ['media', 'matting', '--project', str(project), '--asset-id', source['id'], '--adapter-id', 'rvm_local', '--derived-asset-id', 'person_alpha',
               '--max-edge', str(args.max_edge), '--apply', '--track-id', 'cutout', '--audio-track-id', 'track_audio_1']
    planned = invoke(*matting, '--dry-run')
    generated = invoke(*matting)['data']
    result = generated['matting']
    info = result['video']
    width, height, frames = info['width'], info['height'], info['frames']
    import numpy as np
    from PIL import Image, ImageDraw
    def decode(path, frame, *, rgba=False):
        decoder = ['-c:v', 'libvpx-vp9'] if Path(path).suffix.lower() == '.webm' else []
        command = [ffmpeg_path(), '-nostdin', '-hide_banner', '-loglevel', 'error', *decoder, '-i', str(path), '-vf', f'select=eq(n\\,{frame}),scale={width}:{height}', '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgba' if rgba else 'rgb24', 'pipe:1']
        data = subprocess.run(command, capture_output=True, check=True).stdout
        return np.frombuffer(data, dtype=np.uint8).reshape(height, width, 4 if rgba else 3)
    indices = [0, frames // 2, frames - 1]
    alpha_path = project / generated['asset']['uri']
    rgba_frames = [decode(alpha_path, i, rgba=True) for i in indices]
    metrics = result['worker']['metrics']
    if metrics['opaque_pixels'] < width * height or metrics['transparent_pixels'] < width * height or metrics['soft_alpha_pixels'] < 1:
        raise RuntimeError('Controlled portrait must demonstrate opaque, transparent and soft alpha')
    payload = json.loads((project / 'project.json').read_text(encoding='utf-8'))
    payload['settings']['canvas'].update(width=width, height=height)
    rate = Fraction(info['fps'])
    payload['settings']['timebase']['display_fps'] = {'num': rate.numerator, 'den': rate.denominator}
    atomic_write_json(project / 'project.json', payload)
    bg_assets = []
    render_results = []
    compositions = []
    for name, color in [('green', (30, 185, 90)), ('purple', (105, 45, 165))]:
        background = root / (name + '.png')
        Image.new('RGB', (width, height), color).save(background)
        bg = invoke('media', 'ingest', '--project', str(project), '--input', str(background))['data']['asset']
        bg_assets.append(bg)
        ops = [{'op': 'append_clip', 'track_id': 'track_video_1', 'asset_id': bg['id'], 'id': 'background', 'source_in_tick': 0, 'source_out_tick': generated['generated_clip']['duration_tick']}] if len(bg_assets) == 1 else [{'op': 'update_clip', 'track_id': 'track_video_1', 'clip_id': 'background', 'patch': {'asset_id': bg['id']}}]
        atomic_write_json(changes, {'operations': ops})
        invoke('timeline', 'compose', '--project', str(project), '--input', str(changes))
        output = project / 'renders' / (name + '.mp4')
        rendered = invoke('render', '--project', str(project), '--output', str(output), '--profile', 'custom', '--width', str(width), '--height', str(height), '--crf', '12')
        invoke('quality', 'check', '--project', str(project), '--input', str(output), '--width', str(width), '--height', str(height), '--require-audio')
        rows = []
        decoded = []
        for index, rgba in zip(indices, rgba_frames):
            actual = decode(output, index)
            a = rgba[:, :, 3:].astype(np.float32) / 255
            expected = rgba[:, :, :3].astype(np.float32) * a + np.array(color, dtype=np.float32) * (1 - a)
            error = np.abs(actual.astype(np.float32) - expected)
            row = {'frame': index, 'mean_abs_rgb_error': float(error.mean()), 'p99_abs_rgb_error': float(np.quantile(error, .99))}
            if row['mean_abs_rgb_error'] > 6 or row['p99_abs_rgb_error'] > 32:
                raise RuntimeError('Timeline composition differs from independent straight-alpha blend: ' + str(row))
            rows.append(row)
            decoded.append(actual)
        compositions.append(decoded)
        render_results.append({'background': name, 'sha256': 'sha256:' + sha256_file(output), 'manifest_sha256': 'sha256:' + sha256_file(Path(rendered['data']['manifest'])), 'pixel_comparison': rows})
    atomic_write_json(changes, {'operations': [{'op': 'remove_clip', 'clip_id': 'background'}]})
    invoke('timeline', 'compose', '--project', str(project), '--input', str(changes))
    transparent = project / 'renders' / 'person-alpha.webm'
    transparent_render = invoke('render', '--project', str(project), '--output', str(transparent), '--profile', 'custom', '--width', str(width), '--height', str(height),
                                '--container', 'webm', '--video-codec', 'libvpx-vp9', '--audio-codec', 'libopus', '--pixel-format', 'yuva420p', '--crf', '18')
    invoke('quality', 'check', '--project', str(project), '--input', str(transparent), '--width', str(width), '--height', str(height), '--require-audio')
    alpha_errors = []
    for index, reference in zip(indices, rgba_frames):
        decoded = decode(transparent, index, rgba=True)
        error = np.abs(decoded[:, :, 3].astype(np.float32) - reference[:, :, 3].astype(np.float32))
        item = {'frame': index, 'mean_abs_alpha_error': float(error.mean()), 'p99_abs_alpha_error': float(np.quantile(error, .99))}
        if item['mean_abs_alpha_error'] > 1 or decoded[:, :, 3].min() != 0 or decoded[:, :, 3].max() != 255:
            raise RuntimeError('Transparent delivery lost alpha: ' + str(item))
        alpha_errors.append(item)
    transparent_summary = {'sha256': 'sha256:' + sha256_file(transparent), 'manifest_sha256': 'sha256:' + sha256_file(Path(transparent_render['data']['manifest'])),
                           'verification_decoder': 'libvpx-vp9', 'alpha_comparison': alpha_errors}
    invoke('validate', '--project', str(project))
    invoke('policy', 'audit', '--project', str(project))
    rights = invoke('rights', 'check', '--project', str(project), expected=7)
    cell_w, cell_h = 256, 278
    sheet = Image.new('RGB', (cell_w * 4, cell_h * 3), '#20232a')
    draw = ImageDraw.Draw(sheet)
    source_path = project / source['uri']
    for row, index in enumerate(indices):
        rgba = rgba_frames[row]
        views = [decode(source_path, index), np.repeat(rgba[:, :, 3:], 3, axis=2), compositions[0][row], compositions[1][row]]
        for col, (label, view) in enumerate(zip(('source', 'alpha', 'green render', 'purple render'), views)):
            thumbnail = Image.fromarray(view).resize((cell_w, 256))
            sheet.paste(thumbnail, (col * cell_w, row * cell_h + 22))
            draw.text((col * cell_w + 6, row * cell_h + 5), f'{label} / frame {index}', fill='white')
    sheet_path = root / 'contact-sheet.png'
    sheet.save(sheet_path)
    summary = {'checked_at_utc': now_iso(), 'checks': checks, 'source_sha256': source['sha256'], 'adapter': adapter,
               'plan': planned['data']['plan'], 'matting': result, 'renders': render_results, 'transparent_delivery': transparent_summary, 'rights_expected_exit': 7, 'rights_check': rights['data'],
               'contact_sheet': str(sheet_path), 'contact_sheet_sha256': 'sha256:' + sha256_file(sheet_path),
               'runtime_network': 'disabled', 'runtime_downloads': False, 'docker_or_wsl_started': False, 'browser_started': False,
               'broad_natural_human_video_quality_accepted': False, 'human_visual_review_completed': False, 'full_jianying_parity_accepted': False}
    atomic_write_json(root / 'summary.json', summary)
    print(json.dumps({'output': str(root), 'frames': frames, 'rgba_verified': result['rgba_roundtrip_verified'], 'metrics': metrics}), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
