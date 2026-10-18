"""Separate native pixel conversion from VP9 exact-alpha delivery; research only."""
import argparse,hashlib,json,subprocess
from pathlib import Path

def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()

def run(work,evidence):
    import numpy as np
    work.mkdir(parents=True,exist_ok=False);evidence.mkdir(parents=True,exist_ok=False)
    (evidence/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    width,height=256,8
    a=np.zeros((height,width,4),dtype='uint8');a[:,:,:3]=[48,96,144];a[:,:,3]=np.arange(width,dtype='uint8')[None,:]
    source=work/'rgba.raw';source.write_bytes(a.tobytes())
    common=['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgba','-s',f'{width}x{height}','-r','1','-i',str(source)]
    exact_graph='[0:v]split=2[c][a];[a]alphaextract,format=gray[exact];[c]format=yuv420p[yuv];[yuv][exact]alphamerge,format=yuva420p[out]'
    rows=[]
    def assess(raw):
        actual=np.frombuffer(raw,dtype='uint8').reshape(-1,height,width,4)
        delta=np.abs(actual[0,:,:,3].astype(int)-a[:,:,3].astype(int))
        return {'decoded_frames':len(actual),'mismatch_alpha_pixels':int(np.count_nonzero(delta)),
            'max_alpha_error':int(delta.max()),'alpha_row':actual[0,0,:,3].tolist(),
            'exact_alpha_gate':bool(np.array_equal(actual[0,:,:,3],a[:,:,3])),
            'rgba_sha256':'sha256:'+hashlib.sha256(raw).hexdigest()}
    for name,filters in [('format420',['-vf','format=yuva420p']),('format444',['-vf','format=yuva444p']),
                         ('split_alpha',['-filter_complex',exact_graph,'-map','[out]'])]:
        command=[*common,*filters,'-frames:v','1','-an','-pix_fmt','rgba','-f','rawvideo','pipe:1']
        r=subprocess.run(command,capture_output=True,timeout=60)
        (evidence/(name+'.stderr.log')).write_bytes(r.stderr);assert r.returncode==0,r.stderr
        rows.append({'name':name,'type':'unencoded-conversion','command':command,**assess(r.stdout)})
    for name,filters,extra in [('vp9_default',['-vf','format=yuva420p'],[]),
                               ('vp9_lossless',['-vf','format=yuva420p'],['-lossless','1']),
                               ('vp9_split_alpha',['-filter_complex',exact_graph,'-map','[out]'],['-lossless','1'])]:
        path=work/(name+'.webm');command=[*common,*filters,'-frames:v','1','-an','-c:v','libvpx-vp9',
            '-pix_fmt','yuva420p','-crf','0','-b:v','0',*extra,str(path)]
        r=subprocess.run(command,capture_output=True,timeout=60)
        (evidence/(name+'.stderr.log')).write_bytes(r.stderr);assert r.returncode==0,r.stderr
        decoder=['ffmpeg','-v','error','-c:v','libvpx-vp9','-i',str(path),'-an','-pix_fmt','rgba','-f','rawvideo','pipe:1']
        decoded=subprocess.run(decoder,capture_output=True,timeout=60);assert decoded.returncode==0,decoded.stderr
        rows.append({'name':name,'type':'actual-vp9-encode-and-decode','command':command,'decoder':decoder,
            'webm_sha256':sha(path),**assess(decoded.stdout)})
    record={'status':'research_diagnostic_completed','original_alpha_levels':256,'threshold_max_alpha_error':0,
        'cases':rows,'product_source_mutated':False,'production_delivery_alpha_accepted':False,
        'new_model_forwards':0,'browser_invocations':0,'virtualization':False,'source_sha256':sha(source),
        'generator_sha256':sha(Path(__file__)),'ffmpeg_version':subprocess.check_output(['ffmpeg','-version']).decode('utf-8').splitlines()[0]}
    (evidence/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'status':record['status'],'results':[{k:r[k] for k in ['name','max_alpha_error','mismatch_alpha_pixels','exact_alpha_gate']} for r in rows]}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True)
    a=p.parse_args();run(a.work.resolve(),a.evidence.resolve())
