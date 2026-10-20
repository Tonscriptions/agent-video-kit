"""Independent native probe for u8 silence rounding before tempo changes."""
from __future__ import annotations
import argparse
import array
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();output=args.output.resolve();assert not output.exists()
    executable=shutil.which('ffmpeg');assert executable
    record={'network':False,'virtualization':False,'new_model_inference':0,
        'generator_sha256':'sha256:'+hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'ffmpeg_sha256':'sha256:'+hashlib.sha256(Path(executable).read_bytes()).hexdigest(),'cases':[]}
    for name,prefix in [('native-u8',''),('explicit-float','aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,')]:
        graph='anullsrc=r=48000:cl=stereo,'+prefix+'atrim=duration=2,areverse,atempo=2,aformat=sample_fmts=fltp,apad=whole_len=48000,atrim=end_sample=48000'
        command=[executable,'-v','error','-f','lavfi','-i',graph,'-f','s16le','pipe:1']
        result=subprocess.run(command,capture_output=True,check=True,timeout=60)
        values=array.array('h',result.stdout)
        record['cases'].append({'name':name,'command':command,'exit_code':result.returncode,
            'samples_per_channel':len(values)//2,'minimum':min(values),'maximum':max(values),
            'nonzero_samples':sum(x!=0 for x in values),'decoded_sha256':'sha256:'+hashlib.sha256(result.stdout).hexdigest(),
            'stderr':result.stderr.decode('utf8','replace')})
    record['baseline_offset_reproduced']=record['cases'][0]['nonzero_samples']>0 and record['cases'][1]['nonzero_samples']==0
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    assert record['baseline_offset_reproduced'];print(json.dumps({'baseline_offset_reproduced':True,'native_s16_offset':record['cases'][0]['minimum'],'float_nonzero_samples':0}))


if __name__=='__main__':main()
