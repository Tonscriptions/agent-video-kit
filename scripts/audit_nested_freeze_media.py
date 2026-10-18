"""Recheck encoded media, raw logs, frozen bytes and actual GIF durations."""
from __future__ import annotations
import argparse,hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from run_frozen_regression import frozen

def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def run(public,work,evidence):
    from PIL import Image,ImageDraw,ImageFont
    evidence.mkdir(parents=True,exist_ok=False)
    (evidence/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    original=json.loads((public/'verification.json').read_bytes())
    assert original['generator_sha256']==sha(ROOT/'scripts/smoke_nested_freeze.py')==sha(public/'executed-generator.py')
    assert original['frozen_before']==original['frozen_after']==frozen()
    assert original['status']=='core_passed_delivery_alpha_failed' and not original['all_delivery_gates_passed']
    for name,value in original['files'].items():assert sha(public/name)==value['sha256'],name
    copied=[]
    for pattern in ('*.log','*-manifest.json','*.graph.json','*.ffgraph','*request.json','calls.json'):
        for p in sorted(work.glob(pattern)):
            if p.name in copied:continue
            shutil.copyfile(p,evidence/p.name);copied.append(p.name)
    assert len(original['calls'])==30 and all(c['exit_code']==c['expected_exit_code']==0 for c in original['calls'])
    for c in original['calls']:
        for stream in ('stdout','stderr'):
            assert sha(evidence/f'{c["index"]:03}.{stream}.log')==c[stream+'_sha256']
    mains=[];gifs=[];previews=[];contact_frames=None
    for case in original['cases']:
        name=case['name'];alpha=name=='NF07';p=public/(name+('.nut' if alpha else '.mkv'))
        r=subprocess.run(['ffprobe','-v','error','-show_streams','-show_format','-show_frames',
            '-show_entries','frame=media_type,best_effort_timestamp_time:stream:format','-of','json',str(p)],capture_output=True,check=True,timeout=60)
        probe=json.loads(r.stdout);video=next(s for s in probe['streams'] if s['codec_type']=='video')
        frames=[x for x in probe['frames'] if x['media_type']=='video']
        assert len(frames)==case['frames'] and video['width']==240 and video['height']==136 and video['r_frame_rate']=='10/1'
        assert all(abs(float(x['best_effort_timestamp_time'])-i/10)<=.000501 for i,x in enumerate(frames))
        raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(p),'-map','0:v:0','-an',
            '-pix_fmt','rgba' if alpha else 'rgb24','-f','rawvideo','pipe:1'])
        pcm=subprocess.check_output(['ffmpeg','-v','error','-i',str(p),'-map','0:a:0','-vn','-ar','48000','-ac','2','-f','f32le','pipe:1'])
        assert 'sha256:'+hashlib.sha256(raw).hexdigest()==case['rgb_sha256']
        assert 'sha256:'+hashlib.sha256(pcm).hexdigest()==case['pcm_sha256'] and len(pcm)==case['stereo_sample_frames']*8
        manifest=evidence/(name+('.graph.json' if alpha else '-manifest.json'))
        assert sha(manifest)==case['manifest_sha256']
        mains.append({'name':name,'path':p.relative_to(ROOT).as_posix(),'frames':len(frames),'file_sha256':sha(p),
            'stereo_sample_frames':len(pcm)//8,'probe':probe})
        if name=='NF06':contact_frames=raw
        if alpha:continue
        with Image.open(public/(name+'.gif')) as im:
            ds=[]
            for i in range(im.n_frames):im.seek(i);ds.append(im.info['duration'])
            assert im.size==(480,272) and sum(ds)==case['frames']*100
            gifs.append({'name':name,'encoded_image_frames':im.n_frames,'durations_ms':ds,'total_duration_ms':sum(ds),
                'sha256':sha(public/(name+'.gif'))})
        preview=public/(name+'.mp4')
        probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-show_streams','-of','json',str(preview)]))
        v=next(s for s in probe['streams'] if s['codec_type']=='video')
        assert int(v['nb_read_frames'])==case['frames'] and (v['width'],v['height'])==(240,136)
        previews.append({'name':name,'sha256':sha(preview),'probe':probe})
    contact=Image.new('RGB',(960,616),'#131820');draw=ImageDraw.Draw(contact)
    font=ImageFont.truetype(str(public/'DejaVuSans.ttf'),18)
    for n,index in enumerate((9,15,19,25)):
        start=index*240*136*3;im=Image.frombytes('RGB',(240,136),contact_frames[start:start+240*136*3])
        im.save(public/f'NF06-frame-{index:03}.png')
        x=(n%2)*480;y=(n//2)*308
        draw.text((x+10,y+8),f'frame {index:02}   t={index/10:.1f}s',font=font,fill='white')
        contact.paste(im.resize((480,272),Image.Resampling.NEAREST),(x,y+36))
    contact.save(public/'NF06-contact.png')
    save(evidence/'media-audit.json',{'status':'passed_scoped_checks','main_frames':sum(x['frames'] for x in mains),
        'stereo_sample_frames':sum(x['stereo_sample_frames'] for x in mains),'mains':mains,'gifs':gifs,'previews':previews,
        'frozen_files':len(frozen()),'frozen_equal_to_executed_smoke':True,'source_cli_calls':30,'raw_evidence_files':copied,
        'contact_frames':[9,15,19,25],'static_review_not_automatically_claimed':True,'all_delivery_gates_passed':False,
        'delivery_alpha':original['delivery_alpha'],'generator_sha256':sha(Path(__file__)),
        'public_files':{p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(public.iterdir()) if p.is_file()}})
    print(json.dumps({'status':'passed_scoped_checks','main_frames':327,'gif_files':len(gifs),'raw_evidence_files':len(copied)}))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ('public','work','evidence'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,k).resolve() for k in ('public','work','evidence')))
