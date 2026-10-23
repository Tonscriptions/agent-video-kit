"""Record the five displayed original/output times; no playback/listening claim."""
from datetime import datetime,timezone
import json
from pathlib import Path
from run_frozen_regression import sha

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'docs/validation/evidence/float-shaper-20261023-lab/static-review-r1'

def main():
    path=WORK/'verification.json';value=json.loads(path.read_bytes())
    assert value['status']=='prepared-for-static-review' and value['panels_viewed']==0
    assert sha(ROOT/value['contact'])==value['contact_sha256']
    (WORK/'prepared-verification.json').write_bytes(path.read_bytes())
    value.update(status='observed-ten-static-original-and-actual-preview-panels',panels_viewed=10,
        reviewed_at_utc=datetime.now(timezone.utc).isoformat(),display_tool='view_image',
        observations=[
            'Five actual author times 3,5,9,13,16 displayed side by side; source circle position and authored overlays align in the stills.',
            'Standalone 1D, cubic/spline and combined-stage examples visibly change the gradient and circle color while retaining their layout.',
            'The headroom example at author16 visibly clips highlights to white/yellow; the independent raw oracle retains values above1 before the declared clip delivery edge.',
            'The displayed GIF has a finite palette and visible gradient bands in both columns. Float32/PNG16 numerical checks are recorded independently; this static GIF is not a smooth-gradient or natural-quality acceptance.'
        ],continuous_playback_review=False,listening_review=False,natural_quality_accepted=False,
        HDR_accepted=False,full_capcut_parity=False,review_script_sha256=sha(Path(__file__)))
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    (WORK/'executed-review-script.py.txt').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({'status':value['status'],'panels_viewed':10,'playback':False}))

if __name__=='__main__':main()
