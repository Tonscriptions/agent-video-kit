from pathlib import Path
import sys,json,subprocess
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'product/src'))
from ai_ad_editor.media import ffmpeg_path
pub=ROOT/'docs/assets/html-motion-20261018';out=pub/'development-exact-time.nut'
subprocess.run([ffmpeg_path(),'-v','error','-y','-i',str(pub/'S01-alpha.mkv'),'-vf','settb=1/12000,setpts=N*1000','-fps_mode','passthrough','-c:v','ffv1','-pix_fmt','bgra',str(out)],check=True)
manifest=json.loads((ROOT/'product/.runtime/html-motion-final-20261018/main/renders/S03-timeline.mkv.manifest.json').read_text(encoding='utf-8'))
command=manifest['command'];old=manifest['inputs'][1] if False else None
for i,part in enumerate(command):
    if str(part).endswith('1b4c9133da73a711322404314402765a.mkv'):command[i]=str(out)
    if part=='-progress':command[i+1]=str(pub/'development-exact-time-progress.log')
command[-1]=str(pub/'development-exact-time-timeline.mkv')
subprocess.run(command,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
def raw(p):return np.frombuffer(subprocess.check_output([ffmpeg_path(),'-v','error','-i',str(p),'-an','-pix_fmt','rgba','-f','rawvideo','pipe:1']),np.uint8).reshape(-1,360,640,4)
source=raw(pub/'S01-alpha.mkv');actual=raw(pub/'development-exact-time-timeline.mkv')[:,:,:,:3];bg=np.asarray(Image.open(pub/'source.png').convert('RGB'))
a=source[:,:,:,3:4]/255.;ref=np.rint(source[:,:,:,:3]*a+bg[None]*(1-a)).astype(np.uint8);delta=abs(actual.astype(int)-ref.astype(int))
record={'max_rgb_error':int(delta.max()),'mean_rgb_error':float(delta.mean()),'frames_over_8':[i for i,d in enumerate(delta) if d.max()>8]}
print(json.dumps(record));(pub/'development-exact-time-verification.json').write_text(json.dumps(record,indent=2))
