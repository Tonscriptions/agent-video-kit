"""Exercise each native CPU control using previously inferred real landmarks."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import traceback

ROOT=Path(__file__).resolve().parents[1]


def sha(path):
    return 'sha256:'+hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('report','source','evidence','public'):
        parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args()
    for key,value in vars(args).items():setattr(args,key,value.resolve())
    args.evidence.mkdir(parents=True,exist_ok=False);args.public.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(__file__,args.evidence/'executed-probe.py')
    sys.path.insert(0,str(ROOT/'product/src'));sys.path.insert(0,str(ROOT/'scripts'))
    from run_frozen_regression import frozen
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),'frozen_before':frozen(),
            'report_sha256':sha(args.report),'source_sha256':sha(args.source),'model_forwards':0,
            'checks':[],'controls':{},'quality_accepted':False,'blocked_network_events':[]}
    def save():
        (args.evidence/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8',newline='\n')
    def check(name,value):
        record['checks'].append({'name':name,'passed':bool(value)})
        if not value:raise ValueError(name)
    def offline(event,parameters):
        if event.startswith(('socket.connect','socket.getaddrinfo','socket.gethostbyname','urllib.Request')):
            record['blocked_network_events'].append(event);raise RuntimeError('LOCAL_CONTROL_PROBE_NETWORK_REJECTED')
    save();sys.addaudithook(offline)
    try:
        from ai_ad_editor.face_geometry import retouch_frame
        import numpy as np
        import cv2
        cv2.setNumThreads(2)
        report=json.loads(args.report.read_bytes());source=report['source'];faces=report['response']['frames'][0]['faces']
        command=['ffmpeg','-nostdin','-v','error','-protocol_whitelist','file,pipe','-i',str(args.source),
                 '-map','0:v:0','-frames:v','1','-an','-pix_fmt','rgba','-f','rawvideo','pipe:1']
        decoded=subprocess.run(command,capture_output=True,check=True,timeout=60)
        raw=decoded.stdout
        record['decode']={'command':command,'exit_code':decoded.returncode,'stderr':decoded.stderr.decode('utf8',errors='replace')}
        check('original_frame_matches_model_report','sha256:'+hashlib.sha256(raw).hexdigest() == report['response']['frames'][0]['decoded_rgba_sha256'])
        rgba=np.frombuffer(raw,np.uint8).reshape(source['height'],source['width'],4)
        panels=[rgba[55:195,150:310,:3]]
        for key,strength in (('skin_smooth',.6),('exposure_ev',.25),('face_slim',.45),('eye_enlarge',.5)):
            output,support=retouch_frame(rgba,faces,{key:strength},transfer=source['color_transfer'])
            changed=np.any(output[:,:,:3] != rgba[:,:,:3],axis=2)
            check(key+'_actually_changes_rgb',changed.any())
            check(key+'_preserves_every_alpha_sample',np.array_equal(output[:,:,3],rgba[:,:,3]))
            check(key+'_preserves_all_outside_support_samples',np.array_equal(output[~support],rgba[~support]))
            check(key+'_does_not_modify_lower_half',np.array_equal(output[300:],rgba[300:]))
            ok,encoded=cv2.imencode('.png',cv2.cvtColor(output,cv2.COLOR_RGBA2BGRA))
            if not ok:raise ValueError('CONTROL_PNG_ENCODE_FAILED')
            path=args.public/(key+'.png');path.write_bytes(encoded.tobytes())
            record['controls'][key]={'strength':strength,'changed_rgb_pixels':int(changed.sum()),'support_pixels':int(support.sum()),
                                     'path':path.relative_to(ROOT).as_posix(),'bytes':path.stat().st_size,'sha256':sha(path)}
            panels.append(output[55:195,150:310,:3])
        neutral,_=retouch_frame(rgba,faces,{})
        absent,_=retouch_frame(rgba,[],{'skin_smooth':1,'exposure_ev':1,'face_slim':1,'eye_enlarge':1})
        unselected,_=retouch_frame(rgba,faces,{'skin_smooth':1,'face_slim':1},selected_ids=['face_9999'])
        check('neutral_all_rgba_samples_unchanged',np.array_equal(neutral,rgba))
        check('absent_faces_all_rgba_samples_unchanged',np.array_equal(absent,rgba))
        check('unselected_faces_all_rgba_samples_unchanged',np.array_equal(unselected,rgba))
        contact=np.concatenate(panels,axis=1)
        ok,encoded=cv2.imencode('.png',cv2.cvtColor(contact,cv2.COLOR_RGB2BGR))
        if not ok:raise ValueError('CONTACT_PNG_ENCODE_FAILED')
        path=args.public/'controls-contact.png';path.write_bytes(encoded.tobytes())
        record['contact']={'path':path.relative_to(ROOT).as_posix(),'sha256':sha(path),
                           'panel_order':['original','skin_smooth','exposure_ev','face_slim','eye_enlarge']}
        record['status']='passed_native_cpu_controls_no_new_model_forwards'
    except BaseException as exc:
        record.update(status='failed',error=type(exc).__name__+': '+str(exc),traceback=traceback.format_exc());raise
    finally:
        record['frozen_after']=frozen();record['frozen_equal']=record['frozen_before']==record['frozen_after']
        record['finished_at_utc']=datetime.now(timezone.utc).isoformat();save()
    print(json.dumps({'status':record['status'],'checks':len(record['checks']),'model_forwards':0,'frozen_equal':record['frozen_equal']}))


if __name__=='__main__':main()
