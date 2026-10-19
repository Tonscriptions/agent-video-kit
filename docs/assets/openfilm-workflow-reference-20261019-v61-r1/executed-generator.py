"""Rebuild an original reference's cut/motion structure with distinct local assets."""
import argparse
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from openfilm_workflow_evidence import Evidence,FPS,H,SR,TPS,W,append,font,save,sha,wav

# Eight hand-authored samples of the requested symmetric quadratic pan.
CENTERS=[240+160*p/49 for p in (0,2,8,18,31,41,47,49)]


def run(work,output):
    evidence=Evidence(work,output,Path(__file__));error=None;measurements={}
    try:
        label_font=font(evidence.output)
        save(evidence.output/'provenance.json',{'license_spdx':'CC0-1.0','creator':'Agent Video Kit workflow fixture authors',
            'scope':'original procedural images, reference, production tone and text',
            'font':{'file':'DejaVuSans.ttf','sha256':sha(evidence.output/'DejaVuSans.ttf'),'notice':'LICENSE_DEJAVU','license':'Bitstream-Vera'},
            'reference_target':'same cuts and box motion with original replacement content; not pixel-identical style matching'})
        background=(20,27,44); colors=[(36,150,218),(208,123,35),(124,83,209)]
        Image.new('RGB',(W,H),background).save(evidence.output/'background.png')
        for index,word in enumerate(('AGENT','EDIT','EXPORT')):
            image=Image.new('RGBA',(W,H));draw=ImageDraw.Draw(image)
            draw.rectangle((240,130,399,229),fill=(*colors[index],255))
            draw.text((254,167),word,font=label_font,fill='white')
            image.save(evidence.output/f'card-{index}.png')
        reference=[]
        for index,word in enumerate(('LOOK','MOVE','CUT')):
            for n in range(FPS):
                center=round(CENTERS[n]);image=Image.new('RGB',(W,H),background);draw=ImageDraw.Draw(image)
                draw.rectangle((center-80,130,center+79,229),fill=(25,185,135))
                draw.text((center-64,167),word,font=label_font,fill='white');reference.append(np.asarray(image))
        original=evidence.output/'reference.mkv'
        evidence.ffmpeg('-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',FPS,'-i','pipe:0',
                        '-an','-c:v','ffv1','-pix_fmt','bgr0',original,data=np.stack(reference).tobytes())
        t=np.arange(3*SR)/SR; notes=np.repeat([330,440,550],SR)
        pcm=np.rint(np.stack([.10*np.sin(2*np.pi*notes*t),.08*np.cos(2*np.pi*(notes+70)*t)],axis=1)*32767).astype('<i2')
        wav(evidence.output/'production.wav',pcm)
        project=evidence.project('reference-remake',3)
        for path,aid in [('background.png','background'),('production.wav','music'),*[(f'card-{i}.png',f'card-{i}') for i in range(3)]]:
            evidence.ingest(project,evidence.output/path,aid)
        evidence.compose(project,'rebuild',[
            {'op':'add_track','id':'backdrop','kind':'video','order':-1},
            append('background','bg','backdrop',0,3*TPS),
            *[append(f'card-{i}',f'shot-{i}','track_video_1',i*TPS,TPS) for i in range(3)],
            append('music','own-music','track_audio_1',0,3*TPS)])
        for i in range(3):
            evidence.cli('motion','apply','--project',project,'--clip-id',f'shot-{i}',
                         '--preset','pan_right','--amount','.25','--start-tick','0','--end-tick',TPS*(FPS-1)//FPS)
        target=evidence.render(project,'remade')
        frames=evidence.video(target);sound=evidence.audio(target)
        if len(frames)!=3*FPS or sound.shape!=pcm.shape:raise ValueError('unexpected frame/audio lengths')
        pcm_error=float(np.max(np.abs(sound-pcm.astype(np.float32)/32768)))
        if pcm_error>2e-6:raise ValueError('replacement production PCM changed')
        geometry=[]
        for index,image in enumerate(frames):
            color=np.array(colors[index//FPS]);mask=np.max(np.abs(image.astype(np.int16)-color),axis=2)<10
            ys,xs=np.nonzero(mask)
            if not len(xs):raise ValueError('production card missing')
            expected=CENTERS[index%FPS]-.5
            delta=abs((int(xs.min())+int(xs.max()))/2-expected)
            if delta>2 or abs((int(xs.max())-int(xs.min())+1)-160)>3:raise ValueError('independent card motion mismatch')
            geometry.append({'frame':index,'expected_center_x':expected,'observed_box':[int(xs.min()),int(ys.min()),int(xs.max()),int(ys.max())],'center_error_px':delta})
        p=json.loads((project/'project.json').read_bytes())
        if any(asset['sha256']==sha(original) for asset in p['assets']):raise ValueError('reference leaked into production graph')
        for i in range(3):
            clip=next(t for t in p['sequences'][0]['tracks'] if t['id']=='track_video_1')['clips'][i]
            if clip['timeline_start_tick']!=i*TPS or clip['duration_tick']!=TPS:raise ValueError('cut points changed')
        evidence.cli('convert','export','--project',project,'--target-format','package','--output',evidence.output/'remade.aevpkg.zip')
        evidence.preview(original,'reference-input');evidence.preview(target,'remade-preview')
        save(evidence.output/'geometry.json',geometry)
        measurements={'case':'reference-remake','frames':len(frames),'stereo_sample_frames':len(sound),
                      'max_pcm_error':pcm_error,'max_center_error_px':max(row['center_error_px'] for row in geometry),
                      'reference_in_production_graph':False,'reference_content_replaced':True,
                      'cut_ticks':[0,TPS,2*TPS,3*TPS],'comparison_scope':'cut clock and independently authored card geometry; content differs',
                      'new_original_source_scenes':1,'automatic_reference_understanding_accepted':False}
    except Exception as exc:error=exc;raise
    finally:evidence.finish(error,**measurements)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.work,args.output)
