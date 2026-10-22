"""Bind the actually viewed source contact sheet and the measured GIF clock."""
import json
from pathlib import Path
from PIL import Image
from run_frozen_regression import sha

ROOT = Path(__file__).resolve().parents[1]
REL = ROOT/'docs/validation/evidence/float-preview-20261022-lab'
ASSETS = ROOT/'docs/assets/float-preview-20261022-r1'


def main():
    target = REL/'static-review-r1.json'; assert not target.exists()
    media = json.loads((REL/'media-r1/verification.json').read_bytes())
    assert media['status'] == 'passed-public-CLI-original-edited-and-native-float-previews'
    gif = Image.open(ASSETS/'comparison.gif'); times = []
    for index in range(gif.n_frames):
        gif.seek(index); times.append(gif.info.get('duration'))
    assert gif.n_frames == 14 and times == [100]*14
    result = {'status': 'reviewed-actual-CLI-preview-stills-and-GIF-clock-not-playback',
        'source_author_frame_indices': [3, 10, 16], 'preview_local_frame_indices': [0, 7, 13],
        'viewed_image_panels': 6, 'contact_sheet_viewed_with': 'view_image',
        'observations': ['moving original colour block and frame counter visible',
                         'actual preview has the reversed circular overlay at changing positions and rotations',
                         'no obvious black rectangle surrounding the circle in these selected stills'],
        'GIF_frames': 14, 'GIF_durations_ms': times, 'GIF_total_ms': sum(times),
        'continuous_playback_review': False, 'listening_review': False, 'natural_quality_accepted': False,
        'files': {p.name: sha(p) for p in [ASSETS/'comparison.gif', ASSETS/'contact.png', ASSETS/'range.mp4', ASSETS/'original-range.mp4']},
        'media_receipt_sha256': sha(REL/'media-r1/verification.json'), 'generator_sha256': sha(Path(__file__))}
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    print(json.dumps({'status': result['status'], 'viewed_panels': 6, 'GIF_frames': 14}))


if __name__ == '__main__':
    main()
