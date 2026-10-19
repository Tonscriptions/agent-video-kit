"""Decode public silent previews and publish labeled static review contacts."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
from PIL import Image,ImageDraw,ImageFont
import numpy as np
from openfilm_workflow_evidence import ROOT,sha,save


def run(output):
    output.mkdir(parents=True,exist_ok=False)
    font=ImageFont.truetype(str(ROOT/'docs/assets/magnetic-reorder-v53-r5-20261018/DejaVuSans.ttf'),19)
    rows=[]
    def picture(path,index):
        raw=subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(path),'-an','-vf',f'select=eq(n\\,{index})',
                            '-frames:v','1','-pix_fmt','rgb24','-f','rawvideo','pipe:1'],capture_output=True,check=True).stdout
        return Image.fromarray(np.frombuffer(raw,np.uint8).reshape(360,640,3))
    def contact(name,samples):
        image=Image.new('RGB',(1280,394*len(samples)))
        for row,pair in enumerate(samples):
            for col,(label,path,index) in enumerate(pair):
                image.paste(picture(path,index),(col*640,row*394+34))
                ImageDraw.Draw(image).text((col*640+12,row*394+6),label,font=font,fill='white')
        image.save(output/name)
        rows.append({'path':(output/name).relative_to(ROOT).as_posix(),'sha256':sha(output/name),
            'samples':[[{'label':label,'source':path.relative_to(ROOT).as_posix(),'source_sha256':sha(path),'frame':index}
                        for label,path,index in pair] for pair in samples]})
    reference=ROOT/'docs/assets/openfilm-workflow-reference-20261019-v61-r1'
    contact('reference-contact.png',[[('REFERENCE / different content',reference/'reference-input.mp4',n),
            ('REBUILT / replacement assets',reference/'remade-preview.mp4',n)] for n in (0,4,12)])
    shorts=ROOT/'docs/assets/openfilm-workflow-shorts-20261019-v61-r4'
    contact('shorts-contact.png',[[('SHORT 1 / silent preview',shorts/'short-1-silent.mp4',a),
            ('SHORT 2 / silent preview',shorts/'short-2-silent.mp4',b)] for a,b in ((0,0),(16,28),(31,61))])
    screen=ROOT/'docs/assets/openfilm-workflow-screen-20261019-v61-r3'
    contact('screen-contact.png',[[('ACTUAL TEST PAGE / source',screen/'screen-input-preview.mp4',a),
            ('EDITED / action then result',screen/'screen-demo-preview.mp4',b)] for a,b in ((8,0),(28,20),(36,28))])
    save(output/'contacts.json',{'status':'published_static_contacts_not_visual_review','published_at_utc':datetime.now(timezone.utc).isoformat(),
        'generator_sha256':sha(Path(__file__)),'contacts':rows,'continuous_playback_reviewed':False,'audio_listened':False,
        'input_audio_published':False,'natural_quality_accepted':False})
    (output/'executed-contact-publisher.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({'contacts':len(rows),'status':'published_static_contacts_not_visual_review'}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output.resolve())
