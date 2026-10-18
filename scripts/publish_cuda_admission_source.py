"""Publish the original CC0 input only; never present it as a repaired output."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import numpy as np
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'product/.runtime/cuda-admission-vace-real-20261019-v60/fixture'
PUBLIC=ROOT/'docs/assets/cuda-admission-source-20261019-v60'
EVIDENCE=ROOT/'docs/validation/evidence/cuda-admission-20261019-v60'
def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def main():
    if PUBLIC.exists() or (EVIDENCE/'source-publication.json').exists():raise ValueError('fresh original-input publication required')
    PUBLIC.mkdir(parents=True);calls=[]
    def command(args,name):
        result=subprocess.run(list(map(str,args)),capture_output=True,check=True,timeout=120)
        (EVIDENCE/('source-'+name+'.stdout.log')).write_bytes(result.stdout)
        (EVIDENCE/('source-'+name+'.stderr.log')).write_bytes(result.stderr)
        calls.append({'name':name,'command':list(map(str,args)),'exit_code':result.returncode,
                      'stdout_sha256':sha(EVIDENCE/('source-'+name+'.stdout.log')),
                      'stderr_sha256':sha(EVIDENCE/('source-'+name+'.stderr.log'))})
        return result.stdout
    for name in ('source.mov','mask.mov','ground-truth.npz'):shutil.copyfile(WORK/name,PUBLIC/name)
    if sha(PUBLIC/'source.mov')!='sha256:800f9903ca5256f196c0f9328671d41fd9e3ba25880760de24c0bb176e88b6c3':raise ValueError('original source changed')
    def decode(name):
        return np.frombuffer(command(['ffmpeg','-nostdin','-v','error','-i',PUBLIC/name,'-an','-fps_mode','passthrough','-pix_fmt','rgba','-f','rawvideo','pipe:1'],'decode-'+Path(name).stem),np.uint8).reshape(8,128,192,4)
    source=decode('source.mov');mask=decode('mask.mov');truth=np.load(PUBLIC/'ground-truth.npz',allow_pickle=False)['frames']
    panels=[];font=ImageFont.load_default(size=13)
    for index in range(8):
        panel=Image.new('RGB',(576,176),'#101722');draw=ImageDraw.Draw(panel)
        draw.text((6,3),'INPUT ONLY / NO NEW REPAIRED OUTPUT',fill='#ffce73',font=font)
        for column,(label,pixels) in enumerate((('Original source',source[index,:,:,:3]),
                ('Requested mask',np.repeat(mask[index,:,:,3:4],3,axis=2)),('Hidden background truth',truth[index,:,:,:3]))):
            draw.text((column*192+4,25),label,fill='white',font=font)
            panel.paste(Image.fromarray(pixels),(column*192,48))
        panels.append(panel)
    panels[0].save(PUBLIC/'input-only.gif',save_all=True,append_images=panels[1:],duration=[120,130]*4,loop=0,disposal=2)
    contact=Image.new('RGB',(576,176*3))
    for row,index in enumerate((0,4,7)):contact.paste(panels[index],(0,row*176))
    contact.save(PUBLIC/'input-contact.png')
    command(['ffmpeg','-nostdin','-v','error','-i',PUBLIC/'source.mov','-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart',PUBLIC/'source-preview.mp4'],'preview')
    save(PUBLIC/'provenance.json',{'source_and_truth_license':'CC0-1.0','new_source_scenes':0,
        'frames':8,'fps':'8/1','source_only':True,'new_repaired_output':False,'model_calls_in_publisher':0,
        'display_derivatives':'RGB GIF/MP4 only; no alpha/PCM preservation claim',
        'hidden_truth_is_not_model_output':True,'continuous_playback_reviewed':False,'audio_listening_reviewed':False})
    record={'status':'published_original_input_only_no_new_repair','published_at_utc':datetime.now(timezone.utc).isoformat(),
        'new_source_scenes':0,'new_repaired_output':False,'model_forward_calls':0,'calls':calls,
        'source_only':True,'frames':8,'contact_frame_indices':[0,4,7],
        'files':[{'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(PUBLIC.iterdir())],
        'generator_sha256':sha(Path(__file__))}
    save(EVIDENCE/'source-publication.json',record)
    print(json.dumps({'status':record['status'],'files':len(record['files']),'new_repaired_output':False}))

if __name__=='__main__':main()
