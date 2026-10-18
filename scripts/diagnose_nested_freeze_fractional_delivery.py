"""Probe a low-rate fractional root without editing the frozen product."""
import argparse,hashlib,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from run_frozen_regression import frozen

def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

def run(work,evidence):
    work.mkdir(parents=True,exist_ok=False);evidence.mkdir(parents=True,exist_ok=False)
    (evidence/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    before=frozen();calls=[];env=dict(os.environ);env.update(TEMP=str(work),TMP=str(work),TMPDIR=str(work),PYTHONDONTWRITEBYTECODE='1')
    bootstrap='import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();from ai_ad_editor.cli import main;raise SystemExit(main())'
    def cli(*values):
        r=subprocess.run([sys.executable,'-E','-B','-X','utf8','-c',bootstrap,str(ROOT/'product/src'),*map(str,values)],
            cwd=ROOT,env=env,capture_output=True,timeout=180)
        n=len(calls)+1;(evidence/f'{n:02}.stdout.json').write_bytes(r.stdout);(evidence/f'{n:02}.stderr.log').write_bytes(r.stderr)
        result=json.loads(r.stdout);calls.append({'args':list(map(str,values)),'exit_code':r.returncode})
        return r.returncode,result
    project=work/'project';code,_=cli('convert','import','--input',ROOT/'docs/assets/nested-freeze-v51-final-20261018/NF06-project.zip','--output',project)
    assert code==0
    p=json.loads((project/'project.json').read_bytes());p['sequences'][0]['duration_tick']=360900;save(project/'project.json',p)
    mkv=project/'renders/fractional.mkv';code,_=cli('render','--project',project,'--output',mkv,'--container','mkv',
        '--audio-codec','pcm_f32le','--pixel-format','yuv444p','--crf','0','--publish');assert code==0
    v=subprocess.check_output(['ffmpeg','-v','error','-i',str(mkv),'-an','-pix_fmt','rgb24','-f','rawvideo','pipe:1'])
    a=subprocess.check_output(['ffmpeg','-v','error','-i',str(mkv),'-vn','-ar','48000','-ac','2','-f','f32le','pipe:1'])
    assert len(v)//(240*136*3)==41 and len(a)//8==192480
    mp4=project/'renders/fractional.mp4';code,result=cli('render','--project',project,'--output',mp4,'--publish')
    assert code in (0,6),result
    after=frozen();assert after==before
    save(evidence/'verification.json',{'status':'research_delivery_gate_probe','authored_duration_tick':360900,'ticks_per_second':90000,
        'display_fps':{'num':10,'den':1},'expected_display_frames':41,'expected_audio_sample_frames':192480,
        'mkv_actual_display_frames':len(v)//(240*136*3),'mkv_actual_stereo_sample_frames':len(a)//8,
        'mp4_cli_exit_code':code,'mp4_quality_result':result,'mp4_published':mp4.exists(),'calls':calls,'cli_calls':len(calls),
        'frozen_equal':True,'frozen_before':before,'frozen_after':after,'new_model_forwards':0,'browser_invocations':0,
        'continuous_playback':False,'listening_review':False,'generator_sha256':sha(Path(__file__)),
        'mkv_sha256':sha(mkv),'rgb_sha256':'sha256:'+hashlib.sha256(v).hexdigest(),'pcm_sha256':'sha256:'+hashlib.sha256(a).hexdigest()})
    print(json.dumps({'mkv_frames':41,'mkv_sample_frames':192480,'mp4_exit_code':code,'mp4_errors':result.get('errors')}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True)
    a=p.parse_args();run(a.work.resolve(),a.evidence.resolve())
