"""Retain native FFmpeg alpha round-trip measurements for a full 8-bit ramp."""
import argparse,hashlib,json,subprocess
from pathlib import Path
import numpy as np


def run(output):
    output.mkdir(parents=True,exist_ok=False)
    ramp=np.zeros((4,256,4),dtype='uint8');ramp[:,:,:3]=90;ramp[:,:,3]=np.arange(256)
    candidates={'identity':'null', 'rgba-float-rgba':'format=gbrapf32le,format=rgba',
        'rgba-16bit-rgba':'format=gbrap16le,format=rgba',
        'premul-float-scale':'format=gbrapf32le,premultiply=inplace=1,scale=256:4,unpremultiply=inplace=1,format=rgba',
        'premul-float-no-scale':'format=gbrapf32le,premultiply=inplace=1,unpremultiply=inplace=1,format=rgba',
        'premul-16bit-scale':'format=gbrap16le,premultiply=inplace=1,scale=256:4,unpremultiply=inplace=1,format=rgba'}
    rows=[]
    command=['ffmpeg','-v','error','-f','rawvideo','-pix_fmt','rgba','-s','256x4','-r','1','-i','pipe:0']
    for name,graph in candidates.items():
        args=[*command,'-vf',graph,'-an','-frames:v','1','-pix_fmt','rgba','-f','rawvideo','pipe:1']
        p=subprocess.run(args,input=ramp.tobytes(),capture_output=True,timeout=30)
        assert p.returncode==0,p.stderr
        actual=np.frombuffer(p.stdout,dtype='uint8').reshape(4,256,4)[0,:,3]
        rows.append({'name':name,'command':args,'alpha':actual.tolist(),
                     'mismatch':int(np.count_nonzero(actual!=np.arange(256))),
                     'max_error':int(np.max(np.abs(actual.astype(int)-np.arange(256))))})
    graph='color=c=black@0:s=256x4:r=1:d=1,format=rgba[b];[b][0:v]overlay=x=0:y=0:format=auto[v]'
    args=[*command,'-filter_complex',graph,'-map','[v]','-an','-frames:v','1','-pix_fmt','rgba','-f','rawvideo','pipe:1']
    p=subprocess.run(args,input=ramp.tobytes(),capture_output=True,timeout=30);assert p.returncode==0,p.stderr
    actual=np.frombuffer(p.stdout,dtype='uint8').reshape(4,256,4)[0,:,3]
    rows.append({'name':'transparent-source-over','command':args,'alpha':actual.tolist(),
                 'mismatch':int(np.count_nonzero(actual!=np.arange(256))),
                 'max_error':int(np.max(np.abs(actual.astype(int)-np.arange(256))))})
    record={'source':'self-authored full uint8 alpha ramp','rows':rows,
            'generator_sha256':'sha256:'+hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (output/'verification.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps([{k:r[k] for k in ('name','mismatch','max_error')} for r in rows]))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);run(p.parse_args().output.resolve())
