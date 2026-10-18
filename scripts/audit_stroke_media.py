"""Record original media dimensions/timing, generator bytes and static review separately."""
import argparse,hashlib,json,subprocess
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')


def run(output):
    from PIL import Image,ImageSequence
    assert not output.exists();public=ROOT/'docs/assets/stroke-motion-verified-20261018'
    real=json.loads((public/'verification.json').read_bytes())
    assert real['generator_sha256']==sha(ROOT/'scripts/smoke_stroke_motion.py')
    media=[]
    for p in sorted(public.iterdir()):
        if p.suffix not in {'.mp4','.nut'}:continue
        r=subprocess.run(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(p)],capture_output=True,timeout=60,check=True)
        probe=json.loads(r.stdout);video=next(x for x in probe['streams'] if x['codec_type']=='video')
        assert int(video['nb_read_frames'])==36 and video['r_frame_rate']=='12/1'
        assert int(video['height'])==216 and int(video['width'])==(768 if p.name=='comparison.mp4' else 384)
        media.append({'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p),'probe':probe})
    with Image.open(public/'comparison.gif') as im:
        # Read actual encoded frames: identical hold frames are merged by Pillow.
        durations=[]
        for index in range(im.n_frames):im.seek(index);durations.append(im.info['duration'])
        gif={'frames':im.n_frames,'size':list(im.size),'durations_ms':durations,'total_duration_ms':sum(durations),'sha256':sha(public/'comparison.gif')}
        assert gif['frames']==16 and gif['total_duration_ms']==2970
    evidence=ROOT/'docs/validation/evidence/stroke-real-verified-20261018'
    (evidence/'executed-generator.py').write_bytes((ROOT/'scripts/smoke_stroke_motion.py').read_bytes())
    save(evidence/'static-review.json',{'recorded_at_utc':datetime.now(timezone.utc).isoformat(),'artifact':'docs/assets/stroke-motion-verified-20261018/contact.png',
        'artifact_sha256':sha(public/'contact.png'),'method':'assistant image view, three static times in a contact sheet',
        'frames':[0,18,35],'observed':'empty first frame, completed A while I has not begun at 1.5s, full AI at 35/12s; source stays unchanged',
        'continuous_playback':False,'audio_listened':False,'natural_advertising_aesthetic_accepted':False})
    files={p.relative_to(ROOT).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(public.rglob('*')) if p.is_file()}
    save(output,{'status':'passed','media':media,'gif':gif,'files':files,'authored_audio_streams':0,'new_model_inference':0,
        'visual_review':'three static frames only; separate receipt','generator_sha256':sha(Path(__file__))})
    print(json.dumps({'status':'passed','media':len(media),'files':len(files),'gif_frames':gif['frames'],'gif_ms':gif['total_duration_ms']}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output.resolve())
