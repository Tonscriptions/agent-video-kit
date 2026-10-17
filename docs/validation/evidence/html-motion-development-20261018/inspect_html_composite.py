from pathlib import Path
import sys,subprocess,json
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'product/src'))
from ai_ad_editor.media import ffmpeg_path
pub=ROOT/'docs/assets/html-motion-20261018';project=ROOT/'product/.runtime/html-motion-final-20261018/main'
def raw(p):return np.frombuffer(subprocess.check_output([ffmpeg_path(),'-v','error','-i',str(p),'-an','-pix_fmt','rgba','-f','rawvideo','pipe:1']),np.uint8).reshape(-1,360,640,4)
fg=raw(pub/'S01-alpha.mkv');actual=raw(pub/'S03-timeline.mkv')[:,:,:,:3];bg=np.asarray(Image.open(pub/'source.png').convert('RGB'))
a=fg[:,:,:,3:4]/255.;ref=np.rint(fg[:,:,:,:3]*a+bg[None]*(1-a)).astype(np.uint8);delta=abs(actual.astype(int)-ref.astype(int));bad=np.max(delta,axis=-1)>8
rows=[]
for i in (0,1,12,23):
    y,x=np.where(bad[i]);j=int(delta[i].reshape(-1,3).max(axis=-1).argmax());yy,xx=divmod(j,640)
    rows.append({'frame':i,'over8':len(y),'bbox':[int(x.min()),int(y.min()),int(x.max()),int(y.max())] if len(x) else None,
        'max_position':[xx,yy],'actual':actual[i,yy,xx].tolist(),'reference':ref[i,yy,xx].tolist(),'source':fg[i,yy,xx].tolist(),
        'alpha0_max':int(delta[i][fg[i,:,:,3]==0].max()),'opaque_max':int(delta[i][fg[i,:,:,3]==255].max()),
        'semi_max':int(delta[i][(fg[i,:,:,3]>0)&(fg[i,:,:,3]<255)].max())})
    Image.fromarray(actual[i]).save(pub/f'development-actual-{i:02}.png');Image.fromarray(ref[i]).save(pub/f'development-reference-{i:02}.png')
print(json.dumps(rows));(pub/'development-difference.json').write_text(json.dumps(rows,indent=2))
