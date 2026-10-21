"""Prepare six actual MP4 frames; human/model viewing is a separate receipt."""
from datetime import datetime,timezone
import json,hashlib
from pathlib import Path
import shutil,subprocess
from PIL import Image,ImageDraw
from run_frozen_regression import sha

ROOT=Path(__file__).resolve().parents[1]
REL=ROOT/'docs/validation/evidence/color-precision-20261021-lab'
ASSETS=ROOT/'docs/assets/color-precision-20261021-lab'

def main():
    evidence=REL/'surface-cli-review-r1';assets=ASSETS/'surface-cli-review-r1'
    assert not evidence.exists() and not assets.exists();evidence.mkdir();assets.mkdir()
    record={'status':'prepared-not-viewed','viewed':False,'started_at_utc':datetime.now(timezone.utc).isoformat(),
        'script_sha256':sha(Path(__file__)),'calls':[],'inputs':{},'frames':[0,9,19],
        'continuous_playback_reviewed':False,'audio_present':False,'HDR_accepted':False,
        'natural_quality_accepted':False,'virtualization':False,'network':False}
    ffmpeg=shutil.which('ffmpeg');assert ffmpeg
    record['ffmpeg']={'path':ffmpeg,'sha256':sha(Path(ffmpeg))}
    sheet=Image.new('RGB',(3*320,2*230),(18,20,24));draw=ImageDraw.Draw(sheet)
    for row,name in enumerate(('original','affine')):
        source=ASSETS/'surface-cli-media-r1'/(name+'.mp4');record['inputs'][source.relative_to(ROOT).as_posix()]=sha(source)
        command=[ffmpeg,'-v','error','-i',str(source),'-vf',r'select=eq(n\,0)+eq(n\,9)+eq(n\,19)',
            '-pix_fmt','rgb24','-fps_mode','passthrough','-f','rawvideo','pipe:1']
        result=subprocess.run(command,capture_output=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
        assert result.returncode==0 and len(result.stdout)==3*160*96*3
        record['calls'].append({'command':command,'exit_code':result.returncode,'stdout_sha256':'sha256:'+hashlib.sha256(result.stdout).hexdigest()})
        for column,frame in enumerate((0,9,19)):
            raw=result.stdout[column*160*96*3:(column+1)*160*96*3]
            image=Image.frombytes('RGB',(160,96),raw).resize((320,192),Image.Resampling.NEAREST)
            sheet.paste(image,(column*320,row*230+32));draw.text((column*320+8,row*230+8),name+' linear-light core / frame '+str(frame),fill='white')
    image=assets/'actual-MP4-frames-0-9-19.png';sheet.save(image)
    record.update(output={'path':image.relative_to(ROOT).as_posix(),'bytes':image.stat().st_size,'sha256':sha(image)},finished_at_utc=datetime.now(timezone.utc).isoformat())
    (evidence/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    (evidence/'executed.script.py.txt').write_bytes(Path(__file__).read_bytes())
    print(str(image))

if __name__=='__main__':main()
