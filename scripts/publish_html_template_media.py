"""Publish browser-compatible previews, exact lossless copies and a 2s GIF."""
from __future__ import annotations
import argparse,json,subprocess,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'product/src'))
from ai_ad_editor.media import ffmpeg_path,ffprobe_path
from ai_ad_editor.runtime import configure_local_runtime
from smoke_fragments import frozen,save,sha


def run(public,evidence):
    import numpy as np
    from PIL import Image,ImageSequence
    configure_local_runtime();before=frozen()
    record=json.loads((evidence/'verification.json').read_text(encoding='utf-8'))
    assert record['status']=='passed' and record['frozen_after']==before
    assert 'initial_generated_media' not in record,'already published'
    for name,item in record['media'].items():
        assert sha(public/name)==item['sha256'] and (public/name).stat().st_size==item['bytes']
    def command(args,data=None):
        result=subprocess.run(list(map(str,args)),input=data,capture_output=True,timeout=90)
        assert result.returncode==0,result.stderr.decode(errors='replace')
        return result.stdout
    arrays=[]
    for name in ('original','changed','restored'):
        raw=command([ffmpeg_path(),'-v','error','-i',public/(name+'-alpha.nut'),'-f','rawvideo','-pix_fmt','rgba','-threads','1','pipe:1'])
        value=np.frombuffer(raw,np.uint8).reshape(12,216,384,4);assert np.all(value[:,:,:,3]==255)
        arrays.append(value[:,:,:,:3].copy())
    arrays.append(np.concatenate(arrays,axis=2))
    checks=[]
    for name,array in zip(('original','changed','restored','comparison'),arrays):
        path=public/(name+'.mp4');archive=public/(name+'-lossless.mp4');assert not archive.exists()
        path.rename(archive)
        decoded=command([ffmpeg_path(),'-v','error','-i',archive,'-f','rawvideo','-pix_fmt','rgb24','-threads','1','pipe:1'])
        assert decoded==array.tobytes()
        command([ffmpeg_path(),'-v','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{array.shape[2]}x216','-r','6','-i','pipe:0',
            '-an','-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart','-threads','1',path],array.tobytes())
        info=json.loads(command([ffprobe_path(),'-v','error','-count_frames','-show_streams','-show_format','-of','json',path]))
        streams=info['streams'];assert len(streams)==1
        video=streams[0];assert video['pix_fmt']=='yuv420p' and int(video['nb_read_frames'])==12 and video['avg_frame_rate']=='6/1'
        assert float(info['format']['duration'])==2.
        checks.append({'file':path.name,'width':video['width'],'height':video['height'],'frames':12,'fps':'6/1','seconds':2,
            'lossless_reference':archive.name,'lossless_decoded_rgb_exact':True,'display_encoding':'lossy H.264 YUV420p CRF18'})
    # Reuse actual decoded frames; no page/model is rerun. GIF time is in
    # 10 ms units, and [170,160,170] repeated gives exactly 2000 ms.
    frames=[Image.fromarray(value).resize((768,144),Image.Resampling.LANCZOS) for value in arrays[-1]]
    frames[0].save(public/'comparison.gif',save_all=True,append_images=frames[1:],duration=[170,160,170]*4,loop=0,disposal=2)
    with Image.open(public/'comparison.gif') as gif:
        durations=[frame.info.get('duration',0) for frame in ImageSequence.Iterator(gif)]
        assert len(durations)==12 and sum(durations)==2000 and gif.size==(768,144)
    assert before==frozen()
    publication={'status':'passed','source_frozen_equal':True,'videos':checks,'gif':{'frames':12,'width':768,'height':144,
        'duration_ms':2000,'frame_duration_ms':durations,'audio':False},'page_or_model_rerun':False,
        'static_visual_review':{'contact':'contact.png','frames':[0,5,11],'columns':['original','override','null-reset'],
            'observed':'color, copy and product replacement visible; reset matches original animation at these samples',
            'continuous_playback':False,'listening':'no audio in fixture'},'generator_sha256':sha(Path(__file__))}
    save(evidence/'media-publication.json',publication)
    record['initial_generated_media']=record['media']
    record['media']={p.relative_to(public).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(public.rglob('*')) if p.is_file()}
    record['media_publication_sha256']=sha(evidence/'media-publication.json')
    record['visual_review']='one contact sheet: actual frames 0/5/11, original/override/reset columns; static only'
    save(evidence/'verification.json',record)
    print(json.dumps({'media_files':len(record['media']),'gif_ms':2000,'source_frozen_equal':True}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--public',type=Path,required=True);parser.add_argument('--evidence',type=Path,required=True)
    args=parser.parse_args();run(args.public.resolve(),args.evidence.resolve())
