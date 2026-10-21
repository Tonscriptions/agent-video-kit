"""Extract actual encoded frames for a separate static visual review."""
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path
import shutil,subprocess
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
REL=ROOT/'docs/validation/evidence/color-precision-20261021-lab'
ASSETS=ROOT/'docs/assets/color-precision-20261021-lab'
def sha(data):return 'sha256:'+hashlib.sha256(data).hexdigest()
def main():
    evidence=REL/'native-source-review-r1';assets=ASSETS/'native-source-review-r1';assert not evidence.exists() and not assets.exists()
    evidence.mkdir(parents=True);assets.mkdir(parents=True)
    native=json.loads((REL/'native-source-media-r1/verification.json').read_bytes());assert native['status'].startswith('passed-')
    expected={row['path']:row['sha256'] for row in native['assets']}
    record={'status':'prepared-actual-encoded-static-review-not-yet-viewed','prepared_at_utc':datetime.now(timezone.utc).isoformat(),
        'calls':[],'viewed':False,'continuous_playback_reviewed':False,'audio_listened':False,'HDR_accepted':False,
        'editor_integrated':False,'source_receipt_sha256':sha((REL/'native-source-media-r1/verification.json').read_bytes()),
        'script_sha256':sha(Path(__file__).read_bytes()),'layout':'Top original composite; bottom affine. Columns native MP4 frames 0,9,19.'}
    sheet=Image.new('RGB',(160*3,96*2))
    for row,name in enumerate(('original','affine')):
        source=ASSETS/'native-source-media-r1'/(name+'.mp4');assert sha(source.read_bytes())==expected[source.relative_to(ROOT).as_posix()]
        command=[shutil.which('ffmpeg'),'-v','error','-i',str(source),'-vf','select=eq(n\,0)+eq(n\,9)+eq(n\,19)',
            '-fps_mode','passthrough','-pix_fmt','rgb24','-f','rawvideo','pipe:1']
        p=subprocess.run(command,capture_output=True,timeout=90,creationflags=subprocess.CREATE_NO_WINDOW)
        assert p.returncode==0 and len(p.stdout)==160*96*3*3,p.stderr.decode('utf8','replace')
        record['calls'].append({'command':command,'exit_code':p.returncode,'input_sha256':sha(source.read_bytes()),
            'stdout_bytes':len(p.stdout),'stdout_sha256':sha(p.stdout),'stderr_sha256':sha(p.stderr)})
        for col in range(3):sheet.paste(Image.frombytes('RGB',(160,96),p.stdout[col*160*96*3:(col+1)*160*96*3]),(col*160,row*96))
    target=assets/'actual-MP4-frames-0-9-19.png';sheet.resize((960,384),Image.Resampling.NEAREST).save(target)
    record['image']={'path':target.relative_to(ROOT).as_posix(),'sha256':sha(target.read_bytes()),'width':960,'height':384}
    (evidence/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    (evidence/'executed.script.py.txt').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({'status':record['status'],'path':str(target)}))
if __name__=='__main__':main()
