"""Encode actual synthetic research arrays; never publish natural footage."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'product/src')]
from ai_ad_editor.runtime import configure_local_runtime
configure_local_runtime()
from ai_ad_editor.rvm_worker import install_network_guard
EVENTS=[]
install_network_guard(EVENTS)
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from ai_ad_editor.media import ffmpeg_path, ffprobe_path


def sha(path):
    return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def run(args):
    report=json.loads(args.evidence.read_text(encoding='utf-8-sig'))
    assert report['status']=='completed'
    development=json.loads(args.development.read_text(encoding='utf-8-sig'))
    target=args.output.resolve()
    assert target.is_relative_to(ROOT/'docs/assets')
    target.mkdir(parents=True,exist_ok=False)
    font_source=ROOT/'docs/assets/html-motion-20261018/template/font.ttf'
    (target/'font.ttf').write_bytes(font_source.read_bytes())
    font=ImageFont.truetype(str(target/'font.ttf'),12)
    streams=[]
    def process(command,raw=None):
        result=subprocess.run(command,input=raw,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
        assert result.returncode==0,result.stderr[-3000:].decode(errors='replace')
        return result.stdout
    def lossless(path,frames):
        n,h,w,_=frames.shape
        process([ffmpeg_path(),'-v','error','-nostdin','-n','-f','rawvideo','-pixel_format','rgba',
            '-video_size',f'{w}x{h}','-framerate','12','-i','pipe:0','-an','-c:v','ffv1','-pix_fmt','bgra',str(path)],frames.tobytes())
        raw=process([ffmpeg_path(),'-v','error','-i',str(path),'-an','-pix_fmt','rgba','-f','rawvideo','pipe:1'])
        assert raw==frames.tobytes(),path.name
        probe=json.loads(process([ffprobe_path(),'-v','error','-select_streams','v:0','-show_frames','-show_streams',
            '-show_entries','frame=best_effort_timestamp:stream=width,height,time_base,avg_frame_rate,codec_name,pix_fmt','-of','json',str(path)]))
        from fractions import Fraction
        stream=probe['streams'][0]
        assert len(probe['frames'])==n and all(int(f['best_effort_timestamp'])*Fraction(stream['time_base'])==Fraction(i,12)
            for i,f in enumerate(probe['frames']))
        streams.append({'path':path.name,'frames':n,'width':w,'height':h,'fps':12,
            'rgba_sha256':'sha256:'+hashlib.sha256(raw).hexdigest(),'time_base':stream['time_base'],'every_pts_exact':True})
        return np.frombuffer(raw,dtype=np.uint8).reshape(frames.shape)
    def preview(input_path,output_path):
        process([ffmpeg_path(),'-v','error','-nostdin','-n','-i',str(input_path),'-an','-c:v','libx264',
                 '-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(output_path)])
    cases={}
    for name in ('two_surfaces','two_motion_cut','elastic_exposure'):
        item=report['cases'][name]
        original=Path(item['artifact'])
        assert sha(original)==item['artifact_sha256']
        with np.load(original,allow_pickle=False) as data:
            arrays={key:data[key] for key in ('source','forbidden','selected','fallback','truth','baseline','output','contributed')}
            arrays.update({key:data[key] for key in data.files if key.endswith('_region')})
        prefix=target/name
        np.savez_compressed(prefix.with_suffix('.npz'),**arrays)
        source=lossless(target/(name+'-input.nut'),arrays['source'])
        output=lossless(target/(name+'-candidate.nut'),arrays['output'])
        preview(target/(name+'-input.nut'),target/(name+'-input.mp4'))
        preview(target/(name+'-candidate.nut'),target/(name+'-candidate.mp4'))
        panels=[('INPUT',source),('REFERENCE',arrays['baseline'])]
        if name=='two_surfaces':
            old=development['cases'][name]
            path=Path(old['artifact'])
            assert sha(path)==old['artifact_sha256']
            with np.load(path,allow_pickle=False) as data:
                failed=data['output']
                assert np.array_equal(data['source'],source)
            failed=lossless(target/(name+'-failed-v1.nut'),failed)
            panels.append(('FAILED V1',failed))
        panels.extend([('CANDIDATE V3',output),('TRUTH',arrays['truth'])])
        images=[]
        n,h,w,_=source.shape
        for index in range(n):
            image=Image.new('RGB',(len(panels)*w,h+32),'#11181f')
            draw=ImageDraw.Draw(image)
            for column,(label,frames) in enumerate(panels):
                image.paste(Image.fromarray(frames[index]).convert('RGB'),(column*w,32))
                draw.text((column*w+4,2),label,fill='white',font=font)
                draw.text((column*w+4,17),'RESEARCH',fill='#ffbb55',font=font)
            images.append(image)
            if index in (0,n//2,n-1):
                image.save(target/(name+f'-frame-{index:02}.png'))
        raw=np.stack([np.asarray(image.convert('RGBA')) for image in images])
        comparison=target/(name+'-comparison.nut')
        lossless(comparison,raw)
        preview(comparison,target/(name+'-comparison.mp4'))
        gif=target/(name+'-comparison.gif')
        images[0].save(gif,save_all=True,append_images=images[1:],duration=[80,80,90]*4,loop=0,optimize=False,disposal=2)
        with Image.open(gif) as decoded:
            delays=[]
            for i in range(decoded.n_frames):
                decoded.seek(i);delays.append(decoded.info['duration'])
            assert decoded.n_frames==12 and sum(delays)==1000
        cases[name]={'origin_npz':str(original),'origin_npz_sha256':sha(original), 'frames':n,'width':w,'height':h,
            'source_fps':12,'source_duration_seconds':n/12,'gif_frames':12,'gif_duration_ms':sum(delays),
            'candidate_equals_reference_rgba':np.array_equal(output,arrays['baseline']),
            'changed_candidate_rgb_pixels':int(np.any(output[:,:,:,:3]!=arrays['baseline'][:,:,:,:3],axis=3).sum()),
            'panels':[name for name,_ in panels],'product_integrated':False}
    files={p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(target.iterdir()) if p.is_file()}
    record={'status':'encoded_and_every_lossless_frame_verified','generator':'scripts/build_coherent_reference_media.py',
        'generator_sha256':sha(Path(__file__)),'license':'CC0-1.0 original synthetic inputs and AgentGrid font',
        'model_runs':0,'network_guard_events':EVENTS,'natural_media_published':False,'product_integrated':False,
        'continuous_playback_reviewed':False,'listening_reviewed':False,'audio_streams_expected':0,
        'preview_mp4_is_lossy_not_pixel_oracle':True,'cases':cases,'lossless_streams':streams,'files':files}
    (target/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'cases':len(cases),'files':len(files)+1,'lossless_video_streams':len(streams),'natural_media_published':False}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--development',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args())
