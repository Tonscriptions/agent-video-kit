"""Isolate pinned upstream shutter arithmetic and native tmix alpha behavior.

Research only: no product source changes, browser, model or network requests.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('archive','runtime','output'):p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args();output=args.output.resolve();assert not output.exists();output.mkdir(parents=True)
    before=frozen();assert len(before)==216
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),'script_sha256':sha(Path(__file__)),
        'native_windows':sys.platform=='win32','virtualization':False,'browser':False,'product_integrated':False,
        'upstream_browser_render_executed':False,'network':False,'model_forwards':0,'frozen_before':before,'calls':[]}
    def call(argv,label,data=None):
        result=subprocess.run([str(x) for x in argv],input=data,capture_output=True,timeout=60)
        (output/(label+'.stderr.log')).write_bytes(result.stderr)
        record['calls'].append({'label':label,'argv':[str(x) for x in argv],'exit_code':result.returncode,
            'stdout_sha256':'sha256:'+hashlib.sha256(result.stdout).hexdigest(),
            'stderr_sha256':'sha256:'+hashlib.sha256(result.stderr).hexdigest()})
        assert result.returncode==0,result.stderr[-2000:].decode('utf8','replace')
        return result.stdout
    try:
        archive=args.archive.resolve();assert sha(archive)=='sha256:13e833529ea967824f1a587d6d9eee3892d0de05a0ab815f121ffa8405b9987f'
        member='openfilm-openfilm-7192264/packages/openfilm/src/render.mjs'
        with zipfile.ZipFile(archive) as z:raw=z.read(member)
        source=raw.decode('utf8');(output/'render.mjs.upstream.txt').write_bytes(raw)
        formula=re.search(r'const t = ([^;]+);',source).group(1)
        assert formula=='(f + (samples > 1 ? (k / samples - 0.5) * shutter : 0)) / fps'
        assert 'film.seek(Math.min(Math.max(0, t), duration - 1e-4))' in source
        record['upstream']={'commit':'71922644da5d6b67db2cc796d4e057f98999944f','archive_sha256':sha(archive),
            'member':member,'render_sha256':'sha256:'+hashlib.sha256(raw).hexdigest(),'formula':formula,
            'default_blur_samples':8,'default_shutter':.5,'license':'MIT; existing OPENFILM_LICENSE.txt applies'}
        cases=[{'f':f,'samples':n,'shutter':s,'fps_num':a,'fps_den':b,'duration':d}
            for f,n,s,a,b,d in [(0,1,.5,24,1,2),(4,1,.5,30000,1001,2),
                (0,8,.5,24,1,2),(12,8,.5,24,1,2),(12,8,.5,30000,1001,2),
                (47,16,1,24,1,2),(12,8,0,24,1,2),(47,8,4,24,1,2)]]
        runtime=json.loads(args.runtime.read_bytes());node=Path(runtime['node']).resolve()
        driver=output/'shutter-isolated.mjs'
        driver.write_text('const cases='+json.dumps(cases)+';\n'+
            'const formula=(f,k,samples,shutter,fps)=>'+formula+';\n'+
            'console.log(JSON.stringify(cases.map(c=>({...c,times:Array.from({length:c.samples},(_,k)=>{'+
            'const t=formula(c.f,k,c.samples,c.shutter,c.fps_num/c.fps_den);'+
            'return {raw:t,clamped:Math.min(Math.max(0,t),c.duration-1e-4)};} )}))));\n',encoding='utf8',newline='\n')
        observed=json.loads(call([node,driver],'node-shutter'));verified=0
        for case,actual in zip(cases,observed):
            fps=Fraction(case['fps_num'],case['fps_den']);n=case['samples'];s=Fraction(str(case['shutter']))
            rational=[]
            for k,row in enumerate(actual['times']):
                expected=(case['f']+(Fraction(k,n)-Fraction(1,2))*s)/fps if n>1 else Fraction(case['f'],1)/fps
                clamped=min(max(Fraction(0),expected),Fraction(str(case['duration']))-Fraction(1,10000))
                assert abs(float(expected)-row['raw'])<=1e-12 and abs(float(clamped)-row['clamped'])<=1e-12
                rational.append({'raw':str(expected),'clamped':str(clamped)});verified+=1
            actual['rational_reference']=rational
        assert len(observed)==8;record['formula_cases']=observed;record['verified_subframe_times']=verified
        record['interior_mean_bias']={'fps':'24','samples':8,'shutter':'1/2','seconds':'-1/768',
            'explanation':'Upstream left-endpoint samples have a negative mean offset. Midpoint samples would have mean zero; not silently substituted.'}
        write(output/'shutter-cases.json',observed)
        red=bytes((255,0,0,255))*4;blue=bytes((0,0,255,0))*4
        (output/'input-2x2-two-frame.rgba').write_bytes(red+blue)
        binary=Path(shutil.which('ffmpeg')).resolve();record['ffmpeg']={'path':str(binary),'sha256':sha(binary)}
        actual=call([binary,'-hide_banner','-v','error','-nostdin','-f','rawvideo','-pixel_format','rgba',
            '-video_size','2x2','-framerate','2','-i','pipe:0','-an','-filter_threads','1',
            '-vf','format=gbrap,tmix=frames=2,select=eq(n\\,1),format=rgba','-frames:v','1','-fps_mode','passthrough',
            '-threads','1','-f','rawvideo','-pix_fmt','rgba','pipe:1'],'native-tmix',red+blue)
        assert len(actual)==16 and all(actual[i:i+4]==actual[:4] for i in range(0,16,4))
        pixel=list(actual[:4]);assert all(abs(a-b)<=1 for a,b in zip(pixel,[127.5,0,127.5,127.5]))
        (output/'actual-tmix-2x2.rgba').write_bytes(actual)
        record['alpha_control']={'input_frames_rgba':[[255,0,0,255],[0,0,255,0]],'actual_native_tmix_rgba':pixel,
            'independent_premultiplied_reference_rgba':[255,0,0,128],
            'straight_hidden_blue_present':pixel[2]>0,'scope':'controlled gbrap tmix only; not the complete upstream browser/encoder pipeline'}
        record.update(status='passed_research_only',checks=8,full_capcut_parity=False,quality_accepted=False)
    except BaseException as exc:
        record.update(status='failed',error={'type':type(exc).__name__,'message':str(exc)});raise
    finally:
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),frozen_after=frozen())
        record['frozen_equal']=record['frozen_after']==before;write(output/'verification.json',record)
    assert record['frozen_equal']
    print(json.dumps({'status':record['status'],'cases':len(record['formula_cases']),
        'subframe_times':verified,'actual_native_tmix_rgba':pixel,'frozen_equal':True}))


if __name__=='__main__':main()
