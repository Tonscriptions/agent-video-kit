"""Create legible comparison media from already rendered acceptance outputs.

No product CLI or model execution. The original preview is preserved because
its long row labels overlapped adjacent columns during static review.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,subprocess
import numpy as np
from PIL import Image,ImageDraw,ImageFont

def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def run(folder,font):
    names=('before','bilinear','area','reference');codes=('S01','S04','S06','S07');w,h,n,fps=192,108,16,8
    source={};inputs={}
    for code in codes:
        for name in names:
            path=folder/(code+'-'+name+'.mp4');inputs[path.name]=sha(path)
            raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-an','-pix_fmt','rgb24','-f','rawvideo','pipe:1'])
            source[(code,name)]=np.frombuffer(raw,np.uint8).reshape(n,h,w,3)
    label=ImageFont.truetype(str(font),14);frames=[]
    labels=('S01 3-pixel stripes','S04 crop + scale','S06 17-degree box','S07 soft alpha')
    for i in range(n):
        im=Image.new('RGB',(4*w,44+4*(h+28)),(20,24,32));draw=ImageDraw.Draw(im)
        for col,title in enumerate(('V31 actual','Default bilinear','Explicit area','Cell-area reference')):
            draw.text((col*w+6,12),title,font=label,fill='white')
            for row,code in enumerate(codes):
                y=44+row*(h+28);draw.text((col*w+6,y),labels[row],font=label,fill='white')
                im.paste(Image.fromarray(source[(code,names[col])][i]),(col*w,y+28))
        frames.append(im)
    for name,im in (('first',frames[0]),('last',frames[-1])):im.save(folder/('comparison-readable-'+name+'.png'))
    frames[0].save(folder/'comparison-readable.gif',save_all=True,append_images=frames[2::2],duration=250,loop=0,optimize=False,disposal=2)
    p=subprocess.run(['ffmpeg','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s','768x588','-r',str(fps),'-i','pipe:0',
                      '-an','-c:v','libx264','-crf','16','-pix_fmt','yuv444p',str(folder/'comparison-readable.mp4')],
                     input=b''.join(im.tobytes() for im in frames),capture_output=True)
    assert p.returncode==0,p.stderr.decode('utf-8','replace')
    durations=[]
    with Image.open(folder/'comparison-readable.gif') as im:
        for i in range(im.n_frames):im.seek(i);durations.append(im.info.get('duration',0))
    assert len(durations)==8 and sum(durations)==2000
    record={'created_at_utc':datetime.now(timezone.utc).isoformat(),'reason':'Original long row labels crossed columns; original files retained.',
            'source_files':inputs,'generator_sha256':sha(Path(__file__)),'font_sha256':sha(font),
            'new_cli_renders':0,'new_model_inference':0,'width':768,'height':588,'fps':8,'frames':16,'duration_seconds':2,
            'gif_frames':8,'gif_duration_ms':2000,'continuous_playback_review':False,'listening_review':False,
            'output_files':{p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(folder.glob('comparison-readable*'))}}
    (folder/'preview-revision.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'source_videos':len(inputs),'new_cli_renders':0,'gif_frames':8,'gif_ms':2000}))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--folder',type=Path,required=True);parser.add_argument('--font',type=Path,required=True)
    a=parser.parse_args();run(a.folder.resolve(),a.font.resolve())
