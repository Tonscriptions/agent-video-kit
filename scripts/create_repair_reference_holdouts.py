"""Independent, fixed-seed background truths generated before opaque occluders."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'product/src')]
from ai_ad_editor.runtime import configure_local_runtime
configure_local_runtime()
from ai_ad_editor.rvm_worker import install_network_guard
EVENTS = []
install_network_guard(EVENTS)
import cv2
import numpy as np


def fixtures():
    frames, height, width = 12, 96, 160
    y, x = np.indices((height, width), dtype=np.float32)
    result = {}
    for number, name in enumerate(('stationary', 'two_motion_cut', 'elastic_exposure')):
        seed = 20261018 + number
        random = np.random.default_rng(seed)
        textures = [cv2.GaussianBlur(random.integers(25, 230, (160, 240, 3), dtype=np.uint8), (5, 5), 0)
                    for _ in range(2)]
        truth = np.empty((frames, height, width, 4), np.uint8)
        truth[:, :, :, 3] = 255
        selected = np.zeros((frames, height, width), bool)
        preserved = np.zeros_like(selected)
        for i in range(frames):
            if name == 'stationary':
                rgb = textures[0][16:16+height, 24:24+width]
            elif name == 'two_motion_cut':
                local = i % 6
                top = cv2.remap(textures[0], x + 24 + 1.5 * local, y + 16, cv2.INTER_LINEAR)
                bottom = cv2.remap(textures[1], x + 24 - local, y + 16 + .3 * local, cv2.INTER_LINEAR)
                rgb = np.where((y < 48)[:, :, None], top, bottom)
                if i >= 6:
                    rgb = np.clip(rgb.astype(np.int16) + [15, -8, 10], 0, 255).astype(np.uint8)
            else:
                rgb = cv2.remap(textures[0], x + 24 + 1.2 * i + 2 * np.sin(y / 15 + .25*i),
                                y + 16 + .3*i + np.sin(x / 17 + .4*i), cv2.INTER_LINEAR)
                rgb = np.clip(rgb.astype(np.float32) + .6*i, 0, 255).astype(np.uint8)
                preserved[i, 18:33, 108:120] = True
                rgb[preserved[i]] = [10, 225, 20]
            truth[i, :, :, :3] = rgb
            left = 5 + 10*i
            selected[i, 28:65, left:left+22] = True
            selected[i] &= ~preserved[i]
        source = truth.copy()
        source[selected, :3] = [245, 8, 210]
        fallback = source.copy()
        fallback[selected, :3] = [110, 110, 110]
        arrays = {'source': source, 'selected': selected, 'forbidden': selected | preserved,
                  'fallback': fallback, 'truth': truth, 'preserved_region': preserved}
        if name == 'two_motion_cut':
            arrays['rigid_upper_region'] = selected & (y[None] < 48)
            arrays['rigid_lower_region'] = selected & (y[None] >= 48)
        result[name] = (arrays, {'seed': seed, 'scene_cuts': [6] if name == 'two_motion_cut' else [],
            'min_donors': 2, 'width': width, 'height': height, 'frames': frames,
            'fps': {'num': 12, 'den': 1}, 'truth_precedes_occlusion': True,
            'description': {'stationary': 'stationary texture positive control',
                'two_motion_cut': 'opposite independently moving surfaces and an explicit color cut',
                'elastic_exposure': 'nonrigid texture with exposure change and preserved foreground exclusion'}[name]})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.is_relative_to(ROOT / 'product/.runtime')
    output.mkdir(parents=True, exist_ok=False)
    files = {}
    for name, (arrays, description) in fixtures().items():
        path = output / (name + '.npz')
        np.savez_compressed(path, **arrays)
        files[name] = {**description, 'path': str(path),
                       'sha256': 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()}
    record = {'status': 'generated_before_candidate_evaluation', 'license': 'CC0-1.0',
        'generator': 'scripts/create_repair_reference_holdouts.py',
        'generator_sha256': 'sha256:' + hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'network_guard_events': EVENTS, 'cases': files,
        'evaluation_gate': 'Per region candidate MSE and same-canvas error-delta MAE <= paired baseline, no tolerance relaxation; natural quality is separate.'}
    (output / 'manifest.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'cases': len(files), 'manifest': str(output / 'manifest.json')}))


if __name__ == '__main__':
    main()
