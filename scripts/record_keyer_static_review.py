"""Bind the actually viewed five-scene contact to immutable media receipts."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REL = ROOT/'docs/validation/evidence/float-keyer-20261023-lab'


def sha(path):
    return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    previous = REL/'static-review-r1.json'
    value = json.loads(previous.read_bytes())
    assert value['status'] == 'prepared-static-contact-not-yet-reviewed'
    for name in ('source', 'contact'):
        assert sha(ROOT/value[name]) == value[name+'_sha256']
    output = REL/'static-review-r2.json'
    assert not output.exists()
    result = dict(value, status='reviewed-five-static-scenes-with-explicit-quality-limits',
        at_utc=datetime.now(timezone.utc).isoformat(), previous_prepared_receipt_sha256=sha(previous),
        script_sha256=sha(Path(__file__)), selected_author_frames=[3,5,9,13,16],
        observed_scenes=['green','blue_chroma','feather','despill','headroom'],
        observation='Ten static input/output panels viewed. Synthetic red subject and time markers remain visible; green/blue backgrounds are suppressed in the first scenarios, feather changes the boundary, animated partial intensity retains some background, and headroom visibly clips at delivery. Residual ring color is visible. This is not natural-person matte quality acceptance.',
        viewed_static_panels=10, continuous_playback_review=False, listening_review=False,
        natural_quality_accepted=False, HDR_accepted=False, full_capcut_parity=False)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    print(json.dumps({'status':result['status'],'viewed_static_panels':10}, ensure_ascii=False))


if __name__ == '__main__':
    main()
