"""Audit actual encoded previews, PCM masters, manifests and static review extraction."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import subprocess
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
def digest(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()
def sha(path):return digest(path.read_bytes())
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')


def run(public,output):
    from PIL import Image,ImageDraw,ImageSequence
    assert not output.exists();r=json.loads((public/'verification.json').read_bytes())
    assert r['frozen_before']==r['frozen_after']==frozen() and len(frozen())==184
    assert len(r['cases'])==9
    assert r['main_frames']==344 and r['stereo_sample_frames']==1651200
    assert max(c['max_pcm_error'] for c in r['cases'])<=2e-6 and max(c['max_rgb_error'] for c in r['cases'])<=2
    assert len([c for c in r['cli_calls'] if c['expected_exit_code']==2])==2
    for row in r['files']:
        p=public/row['path'];assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],p
    assert sha(ROOT/'scripts/smoke_complete_output_retime.py')==sha(public/'executed-generator.py')
    for call in r['cli_calls']:
        assert call['exit_code']==call['expected_exit_code'] and sha(public/call['result'])==call['result_sha256']
    previews=[]
    for row in r['cases']:
        p=public/(row['name']+'.mp4')
        probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(p)]))
        v=next(s for s in probe['streams'] if s['codec_type']=='video');a=next(s for s in probe['streams'] if s['codec_type']=='audio')
        assert (int(v['width']),int(v['height']),v['avg_frame_rate'])==(160,64,'10/1')
        assert int(v['nb_read_frames'])==row['frames'] and float(v['start_time'])==float(a['start_time'])==0
        duration=Fraction(row['frames'],10)
        assert abs(Fraction(v['duration'])-duration)<=Fraction(1,1000000)
        assert abs(Fraction(a['duration'])-duration)<=Fraction(1,48000)
        pts=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_frames',
            '-show_entries','frame=best_effort_timestamp_time','-of','json',str(p)]))['frames']
        assert len(pts)==row['frames'] and all(Fraction(f['best_effort_timestamp_time'])==Fraction(i,10) for i,f in enumerate(pts))
        raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(public/(row['name']+'.mkv')),'-map','0:a:0','-vn','-f','f32le','pipe:1'])
        assert len(raw)==row['stereo_sample_frames']*8 and digest(raw)==row['decoded_pcm_sha256']
        previews.append({'path':p.name,'sha256':sha(p),'frames':len(pts),'duration_seconds':float(duration),'probe':probe})
    with Image.open(public/'retime.gif') as gif:
        durations=[]
        for f in ImageSequence.Iterator(gif):durations.append(f.info.get('duration',0))
        assert gif.size==(480,192) and len(durations)>0 and sum(durations)==4300
    review=Image.new('RGB',(960,432),(24,24,24));items=[]
    for i,(name,at) in enumerate([('RT04',1.4),('RT04',1.6),('RT03',1.4),('RT09',1.1)]):
        raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(public/(name+'.mp4')),'-ss',str(at),'-frames:v','1',
            '-f','rawvideo','-pix_fmt','rgb24','pipe:1'])
        assert len(raw)==160*64*3
        image=Image.frombytes('RGB',(160,64),raw).resize((480,192),Image.Resampling.NEAREST)
        x,y=(i%2)*480,(i//2)*216;review.paste(image,(x,y+24));ImageDraw.Draw(review).text((x+8,y+5),f'{name} encoded MP4 / {at:.1f} s',fill='white')
        items.append({'case':name,'seconds':at,'decoded_frame_sha256':digest(raw)})
    review.save(public/'encoded-static-review.png')
    record={'status':'passed_scoped_media_audit','checked_at_utc':datetime.now(timezone.utc).isoformat(),
        'generator_sha256':sha(Path(__file__)),'source_receipt_sha256':sha(public/'verification.json'),
        'previews':previews,'gif':{'width':480,'height':192,'frames':len(durations),'duration_ms':sum(durations)},
        'static_review':{'path':'encoded-static-review.png','sha256':sha(public/'encoded-static-review.png'),'items':items,
                        'continuous_playback':False,'human_listening':False},
        'master_frames':344,'master_stereo_sample_frames':1651200,'other_machine_accepted':False}
    output.parent.mkdir(parents=True,exist_ok=True);save(output,record)
    print(json.dumps({k:record[k] for k in ('status','master_frames','master_stereo_sample_frames','gif')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--public',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.public.resolve(),a.output.resolve())
