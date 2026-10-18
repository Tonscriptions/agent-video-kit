"""Audit media and mux one AAC stream from the actual six lossless masters."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import wave

from PIL import Image

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def probe(path):
    return json.loads(subprocess.run(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(path)],
                                    capture_output=True,check=True).stdout)


def run(public,evidence):
    assert not evidence.exists()
    original=json.loads((public/'verification.json').read_bytes())
    assert original['status']=='passed_scoped_audio_routing'
    for row in original['files']:
        p=public/row['path'];assert sha(p)==row['sha256'] and p.stat().st_size==row['bytes'],p
    final=public/'audio-routing-showcase-exact.mp4';assert not final.exists()
    records=[]
    with tempfile.TemporaryDirectory(dir=ROOT/'product/.runtime',prefix='audio-routing-media-') as temp:
        work=Path(temp);raw=work/'masters.f32';listing=work/'previews.txt'
        with raw.open('wb') as out:
            for case in original['cases']:
                result=subprocess.run(['ffmpeg','-v','error','-i',str(public/case['lossless_output']),'-map','0:a:0',
                    '-f','f32le','-c:a','pcm_f32le','pipe:1'],capture_output=True,check=True)
                assert len(result.stdout)==case['output_samples']*8
                assert 'sha256:'+hashlib.sha256(result.stdout).hexdigest()==case['decoded_pcm_sha256']
                out.write(result.stdout)
                info=probe(public/case['preview']);video=next(s for s in info['streams'] if s['codec_type']=='video')
                assert int(video['nb_read_frames'])==round(case['duration_seconds']*12)
                records.append({'id':case['id'],'frames':int(video['nb_read_frames']),'samples':case['output_samples'],
                                'preview_probe':info})
        listing.write_text(''.join("file '"+(public/c['preview']).as_posix()+"'\n" for c in original['cases']),encoding='utf-8')
        subprocess.run(['ffmpeg','-v','error','-f','concat','-safe','0','-i',str(listing),'-f','f32le','-ar','48000','-ac','2','-i',str(raw),
            '-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-t','13','-movflags','+faststart',str(final)],
            capture_output=True,check=True)
        info=probe(final)
        assert float(info['format']['duration'])==13
        video=next(s for s in info['streams'] if s['codec_type']=='video')
        audio=next(s for s in info['streams'] if s['codec_type']=='audio')
        assert int(video['nb_read_frames'])==156 and float(video['duration'])==float(audio['duration'])==13
        contact=Image.new('RGB',(640*3,360))
        for index,t in enumerate((.5,6.5,11.5)):
            frame=work/(str(index)+'.png')
            subprocess.run(['ffmpeg','-v','error','-ss',str(t),'-i',str(final),'-frames:v','1',str(frame)],capture_output=True,check=True)
            with Image.open(frame) as im:contact.paste(im.convert('RGB'),(index*640,0))
        contact.save(public/'encoded-static-review.png')
    gif=public/'audio-routing-showcase.gif'
    with Image.open(gif) as im:
        duration=0
        for i in range(im.n_frames):im.seek(i);duration+=im.info.get('duration',0)
        gif_info={'width':im.width,'height':im.height,'frames':im.n_frames,'duration_ms':duration}
        assert (im.width,im.height,im.n_frames,duration)==(480,270,78,13000)
    inputs=[]
    for p in sorted(public.glob('*.wav')):
        with wave.open(str(p),'rb') as stream:
            assert (stream.getnframes(),stream.getframerate(),stream.getnchannels(),stream.getsampwidth())==(96000,48000,2,2)
            inputs.append({'path':p.name,'sha256':sha(p),'sample_frames':96000,'sample_rate':48000,'channels':2,'bits':16})
    record={'status':'passed_scoped_media_audit','generator_sha256':sha(Path(__file__)),'source_receipt_sha256':sha(public/'verification.json'),
        'original_inputs':inputs,'cases':records,'main_frames':156,'master_stereo_sample_frames':624000,
        'combined_exact_preview':{'path':final.name,'sha256':sha(final),'probe':info},'gif':gif_info,
        'original_concat_preview':{'path':'audio-routing-showcase.mp4','probe':probe(public/'audio-routing-showcase.mp4'),
            'limitation':'Six independently encoded AAC streams originally added 29.333 ms to the audio/container duration; preserved. Exact preview muxes once from float masters.'},
        'static_review':{'path':'encoded-static-review.png','sha256':sha(public/'encoded-static-review.png'),'moments_seconds':[.5,6.5,11.5],
                        'continuous_playback':False,'human_listening':False,'requires_agent_visual_review':True}}
    evidence.parent.mkdir(parents=True,exist_ok=True)
    evidence.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'status':record['status'],'frames':156,'master_sample_frames':624000,'gif':gif_info}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--public',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True)
    args=p.parse_args();run(args.public.resolve(),args.evidence.resolve())
