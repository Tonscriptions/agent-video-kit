import sys,copy,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'product/src'));sys.path.insert(0,str(ROOT/'product/tests'))
from test_clip_windows import ClipWindowTests,TPS
from ai_ad_editor.clip_windows import apply_operation
from PIL import Image
import numpy as np
ClipWindowTests.setUpClass();case=ClipWindowTests();case.setUp()
v=case.seq['tracks'][0]['clips'][0]
background=copy.deepcopy(v);background['id']='background';background['source_in_tick']=0;background['source_out_tick']=4*TPS
case.seq['tracks'].append({'id':'back','kind':'video','order':-1,'clips':[background]})
v['crop']={'x':0,'y':0,'width':120,'height':136,'fit':'contain'}
old=case.pixels_and_samples(case.project)
project,_=apply_operation(case.project,case.sid,{'op':'split_clip','clip_id':'v','at_tick':2*TPS})
new=case.pixels_and_samples(project)
a=np.frombuffer(new[0][0],np.uint8).reshape(136,240,3);b=np.frombuffer(old[0][0],np.uint8).reshape(136,240,3)
d=np.abs(a.astype(np.int16)-b.astype(np.int16))
out=ROOT/'product/.runtime/window-padding-diagnostic';out.mkdir(exist_ok=True)
Image.fromarray(a).save(out/'actual.png');Image.fromarray(b).save(out/'expected.png')
record={'max_rgb_difference':int(d.max()),'mean_rgb_difference':float(d.mean()),'first_frame_equal':new[0][0]==old[0][0]}
(out/'verification.json').write_text(json.dumps(record,indent=2),encoding='utf-8');print(json.dumps(record));case.doCleanups()
