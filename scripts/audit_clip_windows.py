"""Re-decode published takes and independently select the fixed original cuts."""
from __future__ import annotations
import argparse,hashlib,json,subprocess
from pathlib import Path
from fractions import Fraction
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]

def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,v):path.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def decode(path,audio=False):
    flags=['-vn','-ar','48000','-ac','2','-f','f32le'] if audio else ['-an','-pix_fmt','rgb24','-f','rawvideo']
    raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),*flags,'pipe:1'])
    return np.frombuffer(raw,dtype='<f4').reshape(-1,2) if audio else np.frombuffer(raw,dtype=np.uint8).reshape(-1,136,240,3)
def run(public,output):
    record=json.loads((public/'verification.json').read_text(encoding='utf-8'))
    assert record['frozen_equal'] and record['source_before']==record['source_after']
    for path,value in record['source_after'].items():assert sha(ROOT/path)==value,path
    for path,value in record['files'].items():assert sha(public/path)==value['sha256'],path
    for call in record['calls']:
        raw=(public/f'cli-{call["index"]:03}-stdout.log').read_bytes()
        assert 'sha256:'+hashlib.sha256(raw).hexdigest()==call['stdout_sha256']
        assert call['exit_code']==call['expected_exit_code']
    cases=[];comparison=[]
    for item in record['cases']:
        name=item['case'];original='C02' if name=='C08' else name
        video,audio=decode(public/f'{original}-original.mkv'),decode(public/f'{original}-original.mkv',True)
        if name in ('C02','C05','C08'):
            video=np.concatenate((video[:10],video[20:]));audio=np.concatenate((audio[:48000],audio[96000:]))
        elif name=='C03':video,audio=video[15:35],audio[72000:168000]
        elif name=='C06':video,audio=video[10:30],audio[48000:144000]
        elif name=='C07':
            video=np.concatenate((video[:10],np.zeros_like(video[:10]),video[10:]))
            audio=np.concatenate((audio[:48000],np.zeros_like(audio[:48000]),audio[48000:]))
        actual,samples=decode(public/f'{name}-actual.mkv'),decode(public/f'{name}-actual.mkv',True)
        assert np.array_equal(actual,video),name
        assert np.array_equal(samples,audio),name
        assert np.isfinite(samples).all()
        for label,data in [('rgb',actual),('pcm',samples)]:
            assert 'sha256:'+hashlib.sha256(data.tobytes()).hexdigest()==item[label+'_sha256']
        assert np.array_equal(decode(public/f'{name}-actual.mp4'),actual)
        cases.append({'case':name,'frames':len(actual),'stereo_sample_frames':len(samples),
            'rgb_and_pcm_exact_fixed_original_selection':True,'mp4_picture_exact_mkv':True})
        if name in ('C02','C03'):comparison.append((video,actual))
    probes={};videos=audios=0
    for path in sorted(public.iterdir()):
        if path.suffix.lower() not in {'.mkv','.mp4','.wav'}:continue
        result=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(path)]))
        probes[path.name]=result
        videos+=sum(s['codec_type']=='video' for s in result['streams'])
        audios+=sum(s['codec_type']=='audio' for s in result['streams'])
        subprocess.run(['ffmpeg','-v','error','-i',str(path),'-f','null','-'],check=True,capture_output=True)
    for case in cases:
        for ext in ('mkv','mp4'):
            result=probes[f'{case["case"]}-actual.{ext}']
            stream=next(s for s in result['streams'] if s['codec_type']=='video')
            assert (stream['width'],stream['height'])==(240,136)
            assert Fraction(stream['avg_frame_rate'])==10 and int(stream['nb_read_frames'])==case['frames']
            assert abs(float(result['format']['duration'])-case['frames']/10)<.05
    with Image.open(public/'comparison.gif') as image:
        gif={'width':image.width,'height':image.height,'encoded_frames':image.n_frames,
            'duration_ms':sum(image.seek(i) or image.info.get('duration',0) for i in range(image.n_frames))}
    assert gif['width']==480 and gif['height']==272 and gif['duration_ms']==2000
    stills=[]
    for index in (0,10,19):
        stills.append(np.concatenate([np.concatenate([original[index],actual[index]],axis=1) for original,actual in comparison],axis=0))
    Image.fromarray(np.concatenate(stills,axis=0)).save(public/'comparison-static.png')
    files={p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in public.iterdir() if p.is_file()}
    result={'status':'passed','cases':cases,'cli_count':len(record['calls']),'video_streams':videos,'audio_streams':audios,
        'gif':gif,'probes':probes,'public_files':len(files),'public_bytes':sum(f['bytes'] for f in files.values()),'public_sha256':files,
        'static_review_candidate':str(public/'comparison-static.png'),
        'limits':['fixed-V37-original-render-not-independent-image-algorithm','controlled-CC0-counters-not-natural-ad-quality',
            'AAC-preview-audio-not-lossless-reference','no-continuous-playback-or-listening','no-new-model-inference']}
    save(output,result)
    print(json.dumps({k:result[k] for k in ['status','public_files','public_bytes','video_streams','audio_streams','gif']}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--public',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.public.resolve(),a.output.resolve())
