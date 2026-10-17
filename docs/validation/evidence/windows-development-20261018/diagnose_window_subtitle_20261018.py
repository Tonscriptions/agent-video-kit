import sys,unittest,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'product/src'));sys.path.insert(0,str(ROOT/'product/tests'))
from test_clip_windows import ClipWindowTests
import numpy as np
from PIL import Image
from ai_ad_editor.runtime import configure_local_runtime
configure_local_runtime()
def diagnostic(self,actual,expected):
    record=[]
    out=ROOT/'product/.runtime/window-subtitle-diagnostic';out.mkdir(exist_ok=True)
    for index,(x,y) in enumerate(zip(actual[0],expected[0])):
        a=np.frombuffer(x,dtype=np.uint8).reshape(136,240,3)
        b=np.frombuffer(y,dtype=np.uint8).reshape(136,240,3)
        d=np.abs(a.astype(np.int16)-b.astype(np.int16))
        record.append({'frame':index,'max':int(d.max()),'mean':float(d.mean()),'changed_channels':int(np.count_nonzero(d))})
        if index in [0,15,20]:
            Image.fromarray(a).save(out/f'actual-{index}.png');Image.fromarray(b).save(out/f'expected-{index}.png')
    (out/'metrics.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps(record[:2]+record[15:16]+record[20:21]))
ClipWindowTests.same_media=diagnostic
unittest.main(module='test_clip_windows',argv=['diagnostic','ClipWindowTests.test_subtitle_file_split_keeps_original_cues_and_animation'],exit=False)
