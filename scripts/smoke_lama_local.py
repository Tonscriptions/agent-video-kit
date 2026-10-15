"""Run existing local LaMa/VACE weights, optional SAM2 masks, renders and gates."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'model', 'python', 'evidence', 'output-root'):
        parser.add_argument('--' + name, required=True)
    for name in ('mask', 'ground-truth', 'sam2-model', 'sam2-evidence', 'sam2-prompts'):
        parser.add_argument('--' + name, default=None)
    parser.add_argument('--sam2-object-id', type=int, action='append', default=None)
    parser.add_argument('--device', choices=['cpu', 'cuda'], default='cpu')
    parser.add_argument('--engine', choices=['lama','vace'], default='lama')
    parser.add_argument('--prompt', default=None)
    parser.add_argument('--negative-prompt', default=None)
    parser.add_argument('--seed', type=int, default=None)
    parser.add_argument('--inference-steps', type=int, default=None)
    parser.add_argument('--window-frames', type=int, default=None)
    parser.add_argument('--window-overlap', type=int, default=None)
    parser.add_argument('--execution-only', action='store_true', help='Skip redundant dry-run/inspect reports; formal commands retain all integrity checks')
    parser.add_argument('--mask-channel', choices=['alpha', 'luma'], default='alpha')
    parser.add_argument('--mask-grow', type=int, default=4)
    parser.add_argument('--mask-feather', type=float, default=0.)
    parser.add_argument('--model-max-edge', type=int, default=1024)
    args = parser.parse_args()
    if args.engine=='vace' and (args.device!='cuda' or not args.prompt):parser.error('VACE requires explicit CUDA and prompt')
    if args.engine=='lama' and any(getattr(args,k) is not None for k in ('prompt','negative_prompt','seed','inference_steps','window_frames','window_overlap')):parser.error('Prompt/window options require --engine vace')
    if bool(args.mask) == bool(args.sam2_model): parser.error('Choose an existing --mask or local SAM2 model/prompts')
    if args.sam2_model and not all((args.sam2_evidence, args.sam2_prompts)):
        parser.error('SAM2 requires its evidence and prompt JSON')
    for name in ('source', 'model', 'python', 'evidence', 'mask', 'ground_truth', 'sam2_model', 'sam2_evidence', 'sam2_prompts'):
        value = getattr(args, name)
        if value and not Path(value).exists(): parser.error('Existing local input required: ' + name)
    root = Path(args.output_root).resolve()
    if root.exists(): parser.error('Use a new output root')
    root.mkdir(parents=True)
    configure_local_runtime()
    checks = []
    def invoke(*argv, expected=0):
        capture = io.StringIO()
        with contextlib.redirect_stdout(capture): code = cli_main(list(argv))
        value = json.loads(capture.getvalue())
        checks.append({'command': value['command'], 'status': value['status'], 'exit_code': code})
        print(json.dumps(checks[-1]), flush=True)
        if code != expected: raise RuntimeError(capture.getvalue())
        return value
    project = root / 'project'
    invoke('project', 'init', str(project))
    source = invoke('media', 'ingest', '--project', str(project), '--input', str(Path(args.source).resolve()))['data']['asset']
    sam2 = None
    if args.sam2_model:
        invoke('media', 'adapter', 'register', '--project', str(project), '--adapter-id', 'sam2_local', '--engine', 'transformers-sam2-video-local-v1',
               '--model-path', str(Path(args.sam2_model).resolve()), '--executable', str(Path(args.python).resolve()), '--evidence', str(Path(args.sam2_evidence).resolve()), '--device', args.device)
        command = ['media', 'matting', '--project', str(project), '--asset-id', source['id'], '--adapter-id', 'sam2_local', '--derived-asset-id', 'selected_mask', '--prompts', str(Path(args.sam2_prompts).resolve()), '--mask-mode', 'binary']
        for oid in args.sam2_object_id or []: command += ['--object-id', str(oid)]
        sam2 = invoke(*command)['data']
        mask = sam2['asset']
    else:
        mask = invoke('media', 'ingest', '--project', str(project), '--input', str(Path(args.mask).resolve()))['data']['asset']
    adapter_id=args.engine+'_local'
    registration = ['media', 'adapter', 'register', '--project', str(project), '--adapter-id', adapter_id, '--engine', 'diffusers-wan-vace-local-v1' if args.engine=='vace' else 'torchscript-lama-local-v1',
                    '--model-path', str(Path(args.model).resolve()), '--executable', str(Path(args.python).resolve()), '--evidence', str(Path(args.evidence).resolve()), '--device', args.device]
    if not args.execution_only:invoke(*registration, '--dry-run')
    adapter = invoke(*registration)['data']['adapter']
    if not args.execution_only:assert invoke('media', 'adapter', 'inspect', '--project', str(project), '--adapter-id', adapter_id)['data']['verification']['ok']
    command = ['media', 'inpaint', '--project', str(project), '--asset-id', source['id'], '--mask-asset-id', mask['id'], '--adapter-id', adapter_id, '--derived-asset-id', 'repaired',
               '--mask-channel', args.mask_channel, '--mask-grow', str(args.mask_grow), '--mask-feather', str(args.mask_feather), '--model-max-edge', str(args.model_max_edge),
               '--apply', '--track-id', 'track_video_1', '--audio-track-id', 'track_audio_1']
    for name in ('prompt','negative_prompt','seed','inference_steps','window_frames','window_overlap'):
        value=getattr(args,name)
        if value is not None:command+=['--'+name.replace('_','-'),str(value)]
    planned = None if args.execution_only else invoke(*command, '--dry-run')['data']['plan']
    generated = invoke(*command)['data']; result = generated['inpainting']; info = result['video']; metrics = result['worker']['metrics']
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter
    w, h, frames = info['width'], info['height'], info['frames']
    if frames > 120 or w * h > 1280**2: raise RuntimeError('Smoke evidence decoder budget exceeded')
    def decode(path):
        raw = subprocess.run([ffmpeg_path(), '-nostdin', '-hide_banner', '-loglevel', 'error', '-i', str(path), '-an', '-f', 'rawvideo', '-pix_fmt', 'rgba', 'pipe:1'], capture_output=True, check=True).stdout
        return np.frombuffer(raw, np.uint8).reshape(-1, h, w, 4)
    source_frames = decode(project / source['uri']); repaired = decode(project / generated['asset']['uri'])
    mask_frames = decode(project / mask['uri'])
    if len(mask_frames) == 1: mask_frames = np.repeat(mask_frames, frames, axis=0)
    assert len(source_frames) == len(repaired) == len(mask_frames) == frames
    alpha_equal = np.array_equal(source_frames[:, :, :, 3], repaired[:, :, :, 3]); assert alpha_equal
    assert 'sha256:' + hashlib.sha256(source_frames.tobytes()).hexdigest() == metrics['source_rgba_sha256']
    assert 'sha256:' + hashlib.sha256(mask_frames.tobytes()).hexdigest() == metrics['decoded_mask_rgba_sha256']
    values = mask_frames[:, :, :, 3] if args.mask_channel == 'alpha' else np.einsum('...k,k->...', mask_frames[:, :, :, :3], np.array([.2126, .7152, .0722], np.float32))
    selected = values > 127.5
    if args.mask_grow:
        selected = np.array([np.asarray(Image.fromarray(v.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(args.mask_grow * 2 + 1))) != 0 for v in selected])
    outside = int(np.count_nonzero(np.any(repaired[:, :, :, :3] != source_frames[:, :, :, :3], axis=3) & ~selected)); assert outside == 0
    changed_inside = int(np.count_nonzero(np.any(repaired[:, :, :, :3] != source_frames[:, :, :, :3], axis=3) & selected))
    assert changed_inside > 0 and metrics['model_calls'] > 0
    ground = np.load(args.ground_truth, allow_pickle=False)['frames'] if args.ground_truth else None
    reconstruction = None
    if ground is not None:
        assert ground.shape == repaired.shape
        def psnr(a, b):
            mse = float(np.mean((a.astype(np.float64) - b.astype(np.float64))**2))
            return 100. if mse == 0 else float(10 * np.log10(255**2 / mse))
        before = psnr(source_frames[:, :, :, :3][selected], ground[:, :, :, :3][selected]); after = psnr(repaired[:, :, :, :3][selected], ground[:, :, :, :3][selected])
        error = repaired[:, :, :, :3].astype(np.float32) - ground[:, :, :, :3].astype(np.float32)
        intersections = selected[:-1] & selected[1:]
        temporal = float(np.abs(np.diff(error, axis=0))[intersections].mean()) if np.any(intersections) else None
        reconstruction = {'ground_truth_sha256': 'sha256:' + sha256_file(Path(args.ground_truth)), 'masked_psnr_before_db': before, 'masked_psnr_after_db': after,
                          'masked_psnr_improvement_db': after - before, 'consecutive_error_delta_mae_on_shared_mask': temporal, 'scope': 'this controlled synthetic background only'}
    payload = json.loads((project / 'project.json').read_text(encoding='utf-8')); payload['settings']['canvas'].update(width=w, height=h)
    rate = Fraction(info['fps']); payload['settings']['timebase']['display_fps'] = {'num': rate.numerator, 'den': rate.denominator}
    atomic_write_json(project / 'project.json', payload)
    output = project / 'renders/repaired.mp4'
    rendered = invoke('render', '--project', str(project), '--output', str(output), '--profile', 'custom', '--width', str(w), '--height', str(h), '--crf', '12')
    quality = invoke('quality', 'check', '--project', str(project), '--input', str(output), '--width', str(w), '--height', str(h), '--require-audio')
    invoke('validate', '--project', str(project)); invoke('policy', 'audit', '--project', str(project))
    rights = invoke('rights', 'check', '--project', str(project), expected=7)
    indices = sorted(set([0, frames // 2, frames - 1])); cell = 256; sheet = Image.new('RGB', (cell * (4 if ground is not None else 3), (cell + 22) * len(indices)), '#20232a'); draw = ImageDraw.Draw(sheet)
    for row, index in enumerate(indices):
        views = [('source', source_frames[index, :, :, :3]), ('mask', np.repeat(selected[index, :, :, None], 3, axis=2).astype(np.uint8) * 255), ('repaired', repaired[index, :, :, :3])]
        if ground is not None: views.append(('ground truth', ground[index, :, :, :3]))
        for col, (label, pixels) in enumerate(views):
            sheet.paste(Image.fromarray(pixels).resize((cell, cell)), (col * cell, row * (cell + 22) + 22)); draw.text((col * cell + 5, row * (cell + 22) + 4), f'{label} / frame {index}', fill='white')
    contact = root / 'contact-sheet.png'; sheet.save(contact)
    summary = {'checked_at_utc': now_iso(), 'checks': checks, 'adapter': adapter, 'source_sha256': source['sha256'], 'mask_sha256': mask['sha256'], 'plan': planned, 'inpainting': result,
               'redundant_preflight_reports_skipped':args.execution_only,
               'sam2': sam2, 'independent_pixel_checks': {'source_alpha_exact': alpha_equal, 'outside_mask_changed_pixels': outside, 'changed_inside_pixels': changed_inside},
               'controlled_reconstruction': reconstruction, 'render': {'sha256': 'sha256:' + sha256_file(output), 'manifest_sha256': 'sha256:' + sha256_file(Path(rendered['data']['manifest']))},
               'quality': quality['data'], 'rights_check': rights['data'], 'rights_expected_exit': 7, 'contact_sheet': str(contact), 'contact_sheet_sha256': 'sha256:' + sha256_file(contact),
               'runtime_network': 'disabled', 'runtime_downloads': False, 'docker_or_wsl_started': False, 'browser_started': False, 'broad_quality_accepted': False, 'model_commercial_license_accepted': False}
    atomic_write_json(root / 'summary.json', summary)
    print(json.dumps({'summary': str(root / 'summary.json'), 'metrics': metrics, 'controlled_reconstruction': reconstruction}, ensure_ascii=False), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
