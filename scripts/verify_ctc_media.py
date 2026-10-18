"""Actual encoded highlight clocks and original PCM, independent of CTC truth."""
import argparse,contextlib,hashlib,io,itertools,json,shutil,subprocess,sys,time,wave
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'product/src'),str(ROOT/'scripts')]
from ai_ad_editor.cli import main
from ai_ad_editor.project import load_project,save_project
from ai_ad_editor.runtime import configure_local_runtime
from run_frozen_regression import frozen


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def run(args):
    import numpy as np
    from PIL import Image
    root,public,evidence=args.project.resolve(),args.public.resolve(),args.evidence.resolve()
    evidence.mkdir(parents=True,exist_ok=False);configure_local_runtime();before=frozen();calls=[]
    def cli(*values):
        out=io.StringIO();started=time.monotonic()
        with contextlib.redirect_stdout(out):code=main(list(map(str,values)))
        row={'args':list(map(str,values)),'exit_code':code,'seconds':time.monotonic()-started,'result':json.loads(out.getvalue())}
        calls.append(row);save(evidence/f'cli-{len(calls):02}.json',row);assert code==0,row
        return row['result']
    def ff(*values):
        r=subprocess.run(['ffmpeg','-v','error','-nostdin',*map(str,values)],capture_output=True,timeout=240)
        assert r.returncode==0,r.stderr.decode(errors='replace');return r.stdout
    _,project=load_project(root)
    # First author accidentally mixed the MP4's AAC and the separate WAV.
    # Preserve that encoded failure; correct the author, never change input PCM.
    initial=public/'aligned-lossless.mkv'
    assert initial.is_file() and not (public/'initial-double-audio.mkv').exists()
    shutil.copyfile(initial,public/'initial-double-audio.mkv')
    project['sequences'][0]['tracks'][0]['clips'][0]['audio']={'mute':True}
    project['settings']['audio'].update(sample_rate=16000,channels=1)
    save_project(root,project)
    output=root/'renders/aligned-verified.mkv'
    cli('render','--project',root,'--output',output,'--profile','custom','--width','1280','--height','720',
        '--container','mkv','--audio-codec','pcm_f32le','--pixel-format','yuv444p','--crf','0')
    cli('validate','--project',root)
    shutil.copyfile(output,public/'aligned-verified.mkv')
    alignment=json.loads((root/'assets/aligned/short.json').read_text(encoding='utf-8'))
    cue=alignment['display_cues'][0];tps=alignment['ticks_per_second']
    intervals=[(cue['start_tick']/tps+w['start'],cue['start_tick']/tps+w['end']) for w in cue['word_timing']]
    def frames(path):
        p=subprocess.Popen(['ffmpeg','-v','error','-nostdin','-i',str(path),'-f','rawvideo','-pix_fmt','rgb24','-'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            while data:=p.stdout.read(1280*720*3):
                assert len(data)==1280*720*3
                yield np.frombuffer(data,np.uint8).reshape(720,1280,3)
            error=p.stderr.read();assert p.wait(timeout=30)==0,error
        finally:
            p.stdout.close();p.stderr.close()
            if p.poll() is None:p.kill();p.wait(timeout=10)
    raw_hash=hashlib.sha256();pixel_equal=True;observations=[];contacts=[]
    selected={0,round(sum(intervals[1])/2*30),235}
    for i,(old,new) in enumerate(itertools.zip_longest(frames(initial),frames(output))):
        assert old is not None and new is not None
        pixel_equal=pixel_equal and bool(np.array_equal(old,new))
        raw_hash.update(new.tobytes())
        yellow=int(np.count_nonzero((new[:,:,0]>150)&(new[:,:,1]>150)&(new[:,:,2]<80)))
        expected=any(a<=i/30<b for a,b in intervals)
        observations.append({'frame':i,'yellow_pixels':yellow,'expected_highlight':expected,'matches':bool(yellow>0)==expected})
        if i in selected:contacts.append(Image.fromarray(new).resize((640,360)))
    with wave.open(str(public/'input.wav'),'rb') as stream:
        source=np.frombuffer(stream.readframes(stream.getnframes()),dtype='<i2').astype(np.float32)/32768
    pcm=np.frombuffer(ff('-i',output,'-map','0:a:0','-f','f32le','-acodec','pcm_f32le','-'),dtype='<f4')
    audio_equal=len(source)==len(pcm) and bool(np.array_equal(source,pcm))
    pcm_error=float(np.max(np.abs(source-pcm))) if len(source)==len(pcm) else None
    ff('-n','-i',output,'-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','128k',public/'result.mp4')
    ff('-n','-i',public/'input.mp4','-i',public/'result.mp4','-filter_complex',
       '[0:v]scale=640:360[l];[1:v]scale=640:360[r];[l][r]hstack=inputs=2[v]',
       '-map','[v]','-map','1:a:0','-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-shortest',public/'comparison.mp4')
    ff('-n','-i',public/'comparison.mp4','-filter_complex',
       'fps=10,scale=960:-2:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse',public/'comparison.gif')
    contact=Image.new('RGB',(640*len(contacts),360))
    for i,image in enumerate(contacts):contact.paste(image,(i*640,0))
    contact.save(public/'contact.png')
    with Image.open(public/'comparison.gif') as gif:
        gif_frames=gif.n_frames;gif_ms=0
        for i in range(gif_frames):gif.seek(i);gif_ms+=gif.info.get('duration',0)
    after=frozen()
    report={'status':'verified' if pixel_equal and audio_equal and all(x['matches'] for x in observations) and after==before else 'failed',
        'frozen_before':before,'frozen_after':after,'frozen_equal':after==before,'cli_calls':len(calls),
        'encoded_frames':len(observations),'expected_frames':236,'width':1280,'height':720,'fps':30,
        'all_rgb_equal_to_initial':pixel_equal,'rgb_sha256':'sha256:'+raw_hash.hexdigest(),
        'highlight_frame_checks':observations,'highlight_clock_matches':all(x['matches'] for x in observations),
        'source_audio_samples':len(source),'encoded_audio_samples':len(pcm),'sample_rate':16000,'channels':1,
        'pcm_equal_to_original':audio_equal,'pcm_max_error':pcm_error,'gif_frames':gif_frames,'gif_duration_ms':gif_ms,
        'static_contact_frames':sorted(selected),'static_review':False,'continuous_playback_review':False,'listening_review':False,
        'initial_authoring_failure':'MP4 AAC plus separate WAV double mixed; old output preserved. Explicit picture mute and mono16k source clock applied.',
        'files':{p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in public.iterdir() if p.is_file()},
        'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    save(evidence/'verification.json',report)
    assert report['status']=='verified',report['status']
    print(json.dumps({k:report[k] for k in ('status','encoded_frames','pcm_equal_to_original','highlight_clock_matches','gif_frames','gif_duration_ms')}))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('project','public','evidence'):p.add_argument('--'+name,type=Path,required=True)
    run(p.parse_args())
