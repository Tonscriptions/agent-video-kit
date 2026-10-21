"""Retain exact native direct/cache surface differences without weakening tests."""
import json
import argparse
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'product/src'),str(ROOT/'product/tests')]
from ai_ad_editor.runtime import configure_local_runtime
configure_local_runtime()
from ai_ad_editor.media import ffmpeg_path,ffprobe_path
from ai_ad_editor import reverse_cache as cache,reverse_video_clock as clock
from ai_ad_editor.render import build_filter_graph
from ai_ad_editor.utils import sha256_file
import test_cfr_boundaries as helpers
from PIL import Image

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    target=parser.parse_args().output.resolve()
    target.mkdir(exist_ok=False)
    temp=ROOT/'product/.runtime/temp';temp.mkdir(exist_ok=True,parents=True);tempfile.tempdir=str(temp)
    h=helpers.CFRBoundaryTests(methodName='runTest');h.setUp();records=[]
    try:
        source=h.work/'pattern.mp4'
        raw=b''.join(bytes((x*7,y*11,(x*3+y*5+i*9)%256,255))
            for i in range(30) for y in range(helpers.H) for x in range(helpers.W))
        h.run_native([ffmpeg_path(),'-v','error','-f','rawvideo','-pixel_format','rgba',
            '-video_size',f'{helpers.W}x{helpers.H}','-framerate','25','-i','pipe:0',
            '-c:v','libx264','-pix_fmt','yuv420p',source],data=raw)
        for angle,flip in [(0,0),(90,0),(90,1)]:
            path=h.work/f'o-{angle}-{flip}.mp4'
            h.run_native([ffmpeg_path(),'-v','error','-display_rotation:v:0',str(angle),
                *(['-display_hflip:v:0'] if flip else []),'-i',source,'-map','0:v:0','-c','copy',path])
            p,s,_=h.project(path,patch={'reverse':True})
            expected,metadata,_=h.render(p,s)
            with patch.object(clock,'MAX_SELECTED_BUFFER_BYTES',2*helpers.W*helpers.H*16):
                inputs,_,planned,_=build_filter_graph(h.root,p,s)
                jobs=cache.materialize(h.root,planned,h.root/'renders/.tmp/orientation')
                actual,_,_=h.render(p,s)
            job=jobs[0];differences=[]
            for n,(left,right) in enumerate(zip(expected,actual)):
                delta=[(i,a,b) for i,(a,b) in enumerate(zip(left,right)) if a!=b]
                if delta:differences.append({'output_frame':n,'different_bytes':len(delta),
                    'max_error':max(abs(a-b) for _,a,b in delta),'first_differences':delta[:8]})
            name=f'{angle}-{flip}'
            if differences:
                n=differences[0]['output_frame']
                for kind,frames in [('expected',expected),('actual',actual)]:
                    Image.frombytes('RGBA',(helpers.W,helpers.H),frames[n]).save(target/f'{name}-{kind}.png')
            probe=lambda value:json.loads(h.run_native([ffprobe_path(),'-v','error','-show_streams','-show_format','-of','json',value]))
            records.append({'angle':angle,'flip':flip,'input_flags':inputs[:-1],
                'planned_metadata':planned,'direct_metadata':metadata,'differences':differences,
                'source_probe':probe(path),'cache_probe':probe(job['output'])})
        (target/'run.json').write_text(json.dumps({'implementation_sha256':'sha256:'+sha256_file(Path(cache.__file__)),
            'records':records},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        print(json.dumps([{'angle':r['angle'],'flip':r['flip'],'different_frames':len(r['differences']),
            'first':r['differences'][:1]} for r in records]))
    finally:h.doCleanups()

if __name__=='__main__':main()
