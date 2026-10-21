"""Observe actual float32 negotiation/math in installed native FFmpeg filters."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
REL=ROOT/'docs/validation/evidence/color-precision-20261021-lab/float-filter-support-r1'
assert not REL.exists();REL.mkdir(parents=True)
exe=shutil.which('ffmpeg');assert exe
def sha(path):return 'sha256:'+hashlib.sha256(Path(path).read_bytes()).hexdigest()
W,H=32,16
base='nullsrc=s=32x16:r=1:d=1,format=gbrapf32le,geq=r=0.123456789:g=0.234567891:b=0.345678912:a=0.456789123'
other='nullsrc=s=32x16:r=1:d=1,format=gbrapf32le,geq=r=0.987654321:g=0.876543219:b=0.765432198:a=0.654321987'
cases={
 'geq':('[0:v]geq=r=0.123456789:g=0.234567891:b=0.345678912:a=0.456789123[v]',False),
 'premultiply':('[0:v]premultiply=inplace=1[v]',False),
 'scale':('[0:v]scale=32:16[v]',False),
 'rotate_identity':('[0:v]rotate=angle=0:c=none[v]',False),
 'blend_average':('[0:v][1:v]blend=all_expr=(A+B)/2[v]',True),
 'maskedmerge':('[0:v]split=2[a][m];[a][1:v][m]maskedmerge[v]',True),
 'overlay_auto':('[0:v][1:v]overlay=x=0:y=0:format=auto[v]',True),
 'alphaextract':('[0:v]alphaextract,format=gbrapf32le[v]',False),
 'alphamerge':('[0:v]split=2[c][a];[a]alphaextract[mask];[c][mask]alphamerge[v]',False),
 'xfade':('[0:v][1:v]xfade=transition=fade:duration=1:offset=0[v]',True),
 'curves_identity':('[0:v]curves=all=0/0\ 1/1[v]',False),
 'lutrgb_identity':('[0:v]lutrgb=r=val:g=val:b=val:a=val[v]',False),
 'gblur_identity':('[0:v]gblur=sigma=0[v]',False),
}
record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),'ffmpeg':{'path':exe,'sha256':sha(exe)},
    'script_sha256':sha(__file__),'cases':{},'native_windows':True,'virtualization':False,'network':False,
    'product_integration':False,'HDR_accepted':False,'full_capcut_parity':False}
try:
 for name,(graph,second) in cases.items():
    command=[exe,'-hide_banner','-v','verbose','-filter_complex_threads','1','-f','lavfi','-i',base]
    if second:command+=['-f','lavfi','-i',other]
    command+=['-filter_complex',graph,'-map','[v]','-frames:v','1','-pix_fmt','gbrapf32le','-f','rawvideo','pipe:1']
    result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
    (REL/(name+'.stderr.log')).write_bytes(result.stderr)
    if result.returncode==0:(REL/(name+'.gbrapf32le')).write_bytes(result.stdout)
    text=result.stderr.decode('utf8','replace')
    row={'command':command,'exit_code':result.returncode,'stdout_bytes':len(result.stdout),
        'stdout_sha256':'sha256:'+hashlib.sha256(result.stdout).hexdigest(),'stderr_sha256':sha(REL/(name+'.stderr.log')),
        'auto_inserted_scales':[line for line in text.splitlines() if 'auto-inserting filter' in line or ('fmt:' in line and '->' in line)]}
    if result.returncode==0 and len(result.stdout)==W*H*4*4:
        planes=np.frombuffer(result.stdout,dtype='<f4').reshape(4,H,W)
        row['actual_first_pixel_GBRA']=[float(plane[0,0]) for plane in planes]
        row['finite']=bool(np.isfinite(planes).all())
        row['unique_per_plane']=[int(np.unique(plane).size) for plane in planes]
    record['cases'][name]=row
 record['status']='observed-installed-native-filter-negotiation'
finally:
 record['finished_at_utc']=datetime.now(timezone.utc).isoformat()
 (REL/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
 (REL/'executed-probe.py.txt').write_bytes(Path(__file__).read_bytes())
print(json.dumps({name:{'exit_code':row['exit_code'],'values':row.get('actual_first_pixel_GBRA'),
    'automatic_conversions':len(row['auto_inserted_scales'])} for name,row in record['cases'].items()},ensure_ascii=False))
