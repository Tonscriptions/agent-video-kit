"""Bind actual displayed contact frames and independently inspect GIF timing."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from PIL import Image
from run_frozen_regression import sha

ROOT = Path(__file__).resolve().parents[1]
REL = ROOT/'docs/validation/evidence/float-standard-20261022-lab'
ASSETS = ROOT/'docs/assets/float-standard-20261022-r4'


def main():
    out = REL/'static-review-r1.json'
    assert not out.exists()
    media = json.loads((REL/'media-r4/verification.json').read_bytes())
    assert media['status'] == 'passed-public-CLI-original-and-edited-native-float-media'
    with Image.open(ASSETS/'comparison.gif') as gif:
        durations = []
        for n in range(gif.n_frames):
            gif.seek(n); durations.append(gif.info.get('duration'))
        assert gif.n_frames == 20 and durations == [100]*20 and gif.size == (640, 208)
    record = {'status': 'reviewed-actual-CLI-stills-and-GIF-clock-not-playback',
        'at_utc': datetime.now(timezone.utc).isoformat(), 'image': (ASSETS/'contact.png').relative_to(ROOT).as_posix(),
        'image_sha256': sha(ASSETS/'contact.png'), 'viewed_with': 'functions view_image',
        'actual_source_video_frame_indices': [0, 10, 19], 'original_and_edited_frames_viewed': 6,
        'observations': ['Original moving colored rectangle and binary frame counter are visible.',
            'Edited circle moves left to right and rotates over the base; reversed content differs at corresponding times.',
            'Screen blend brightens the circular region; no obvious opaque black rectangle surrounds it in these stills.'],
        'gif': {'sha256': sha(ASSETS/'comparison.gif'), 'frames': 20, 'duration_ms_each': durations,
                'total_duration_ms': sum(durations), 'dimensions': [640, 208]},
        'source_receipt_sha256': sha(REL/'media-r4/verification.json'),
        'continuous_playback_review': False, 'listening_review': False, 'natural_HDR_quality_accepted': False,
        'full_capcut_parity': False, 'generator_sha256': sha(Path(__file__))}
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    print(json.dumps({k: record[k] for k in ['status', 'actual_source_video_frame_indices', 'original_and_edited_frames_viewed']}))


if __name__ == '__main__':
    main()
