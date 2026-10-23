"""Select five actual GIF author times for a bounded static review."""
from datetime import datetime,timezone
import json
from pathlib import Path
from PIL import Image,ImageDraw
from run_frozen_regression import sha

ROOT=Path(__file__).resolve().parents[1]
REL=ROOT/'docs/validation/evidence/float-shaper-20261023-lab'
ASSETS=ROOT/'docs/assets/float-shaper-20261023-r1'

def main():
    media=json.loads((REL/'media-r1/verification.json').read_bytes())
    assert media['status']=='passed-public-CLI-floating-shaper-and-native-float-previews'
    output=REL/'static-review-r1';output.mkdir(exist_ok=False)
    image=Image.open(ASSETS/'comparison.gif');selected=[(3,0),(5,2),(9,6),(13,10),(16,13)]
    panels=[]
    for author,index in selected:
        image.seek(index);panel=image.convert('RGB');ImageDraw.Draw(panel).text((218,7),f'AUTHOR f{author}',fill='white')
        panels.append(panel)
    image.close();contact=Image.new('RGB',(panels[0].width,sum(p.height for p in panels)))
    top=0
    for panel in panels:contact.paste(panel,(0,top));top+=panel.height
    path=ROOT/'docs/assets/float-shaper-review-20261023-r1/contact.png';path.parent.mkdir(exist_ok=False);contact.save(path)
    receipt=dict(status='prepared-for-static-review',at_utc=datetime.now(timezone.utc).isoformat(),
        source_media_sha256=sha(REL/'media-r1/verification.json'),gif_sha256=sha(ASSETS/'comparison.gif'),
        author_frames=[a for a,_ in selected],panels_available=10,panels_viewed=0,contact=str(path.relative_to(ROOT)),
        contact_sha256=sha(path),continuous_playback_review=False,listening_review=False,
        natural_quality_accepted=False,HDR_accepted=False,full_capcut_parity=False)
    (output/'verification.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    (output/'executed-script.py.txt').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({'contact':str(path),'available_panels':10,'panels_viewed':0},ensure_ascii=False))

if __name__=='__main__':main()
