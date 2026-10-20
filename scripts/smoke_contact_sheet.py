"""Run real source/installed CLI contact sheets against a local public fixture."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from PIL import Image
from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path, value): path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('work','evidence','assets','source','preview','source-origin'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--installed',type=Path)
    args=p.parse_args()
    work,evidence,assets=(v.resolve() for v in (args.work,args.evidence,args.assets))
    assert not any(v.exists() for v in (work,evidence,assets))
    for path in (work,evidence,assets):path.mkdir(parents=True)
    env=dict(os.environ);env.update(TEMP=str(ROOT/'product/.runtime/temp'),TMP=str(ROOT/'product/.runtime/temp'),
        TMPDIR=str(ROOT/'product/.runtime/temp'),PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(ROOT/'product/src'))
    prefix=([sys.executable,'-I','-S','-B','-X','utf8',str(args.installed.resolve()/'run.py')] if args.installed else
        [sys.executable,'-E','-B','-X','utf8','-c',
         'import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.cli import main;sys.exit(main())',str(ROOT/'product/src')])
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),'script_sha256':sha(__file__),
        'native_windows':sys.platform=='win32','virtualization':False,'installed':str(args.installed) if args.installed else None,
        'frozen_before':frozen(),'calls':[],'checks':[],'goal_complete':False,'full_capcut_parity':False}
    def save():write(evidence/'verification.json',record)
    def check(name,ok,**details):
        record['checks'].append({'name':name,'ok':bool(ok),**details});save()
        if not ok:raise AssertionError(name)
    def run(label,command,*,expect=0,binary=False):
        command=list(map(str,command));start=time.monotonic()
        r=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,timeout=600)
        (evidence/(label+'.stderr.log')).write_bytes(r.stderr)
        if not binary:(evidence/(label+'.stdout.log')).write_bytes(r.stdout)
        record['calls'].append({'label':label,'command':command,'exit_code':r.returncode,'expected_exit':expect,
            'seconds':time.monotonic()-start,'stdout_bytes':len(r.stdout),'stdout_sha256':hashlib.sha256(r.stdout).hexdigest(),
            'stderr_sha256':hashlib.sha256(r.stderr).hexdigest()});save()
        if r.returncode!=expect:raise AssertionError(label+': '+r.stderr[-1500:].decode('utf8','replace'))
        return r.stdout
    def cli(label,*argv,expect=0):
        return json.loads(run('cli-'+label,[*prefix,*argv],expect=expect))
    try:
        source=assets/'source.mkv';shutil.copyfile(args.source.resolve(),source)
        shutil.copyfile(args.preview.resolve(),assets/'source-preview.mp4')
        shutil.copyfile(args.source_origin.resolve(),assets/'original-source-origin.json')
        write(assets/'source-origin.json',{'fixture':'local CC0 moving geometry and stereo tones from V70',
            'original':str(args.source.resolve()),'sha256':'sha256:'+sha(source),'no_new_remote_media':True,
            'original_origin':'original-source-origin.json','annotation':'Pillow embedded default inspection font; not part of the original footage'})
        webm=assets/'source-alpha.webm'
        run('encode-alpha',['ffmpeg','-hide_banner','-v','error','-nostdin','-y','-i',source,
            '-c:v','libvpx-vp9','-lossless','1','-pix_fmt','yuva420p','-c:a','libopus',webm])
        raw=run('decode-whole-alpha',['ffmpeg','-hide_banner','-v','error','-nostdin','-c:v','libvpx-vp9',
            '-i',webm,'-map','0:v:0','-f','rawvideo','-pix_fmt','rgba','pipe:1'],binary=True)
        frame_bytes=320*180*4
        check('whole-alpha-source-has-24-frames',len(raw)==24*frame_bytes)
        reference=[raw[i:i+frame_bytes] for i in range(0,len(raw),frame_bytes)]
        record['source_frame_rgba_sha256']=[hashlib.sha256(f).hexdigest() for f in reference]
        project=work/'project'
        cli('init','project','init',str(project),'--name','Native alpha contact sheet')
        cli('ingest','media','ingest','--project',str(project),'--input',str(webm),'--asset-id','alpha')
        author=project/'project.json';before=author.read_bytes()
        command=['media','contact-sheet','--project',str(project),'--asset-id','alpha','--output','validation/contact']
        for value in ('0','.17','.75','1.5'):command.extend(['--at-seconds',value])
        plan=cli('dry',*command,'--dry-run')
        check('dry-run-no-output-no-author-change',plan['status']=='planned' and not (project/'validation/contact').exists() and author.read_bytes()==before)
        reply=cli('four-views',*command);folder=Path(reply['data']['output'])
        report=json.loads((folder/'manifest.json').read_bytes())
        check('actual-anchor-clock',[f['relative_seconds'] for f in report['frames']]==[0,.25,.75,1.5])
        check('alpha-aware-native-decoder',report['plan']['decoder']=='libvpx-vp9')
        check('all-owned-processes-reaped',report['process_cleanup']['all_children_reaped'] and not report['process_cleanup']['active_after_cleanup'])
        check('read-only-author-data',author.read_bytes()==before)
        check('no-automatic-quality-acceptance',not report['quality_accepted'] and not reply['data']['quality_accepted'])
        with Image.open(folder/'contact.png') as image:
            sheet=image.convert('RGB');check('bounded-sheet-dimensions',sheet.size==(2560,444))
            for row,index in zip(report['frames'],(0,3,9,18)):
                with Image.open(folder/row['path']) as frame:
                    pixels=frame.convert('RGBA').tobytes()
                check(f'frame-{index}-whole-decode-identity',pixels==reference[index])
                check(f'frame-{index}-has-transparent-and-opaque',row['alpha_extrema']==[0,255])
                for panel in row['panels']:
                    actual=sheet.crop((panel['x'],panel['y'],panel['x']+320,panel['y']+180)).tobytes()
                    expected=bytearray()
                    for y in range(180):
                        for x in range(320):
                            r,g,b,a=pixels[(y*320+x)*4:(y*320+x+1)*4]
                            gray=255 if panel['view']=='light' else 0
                            if panel['view']=='checker':gray=192 if (x//12+y//12)%2 else 96
                            expected.extend([a,a,a] if panel['view']=='alpha' else
                                            [(v*a+gray*(255-a)+127)//255 for v in (r,g,b)])
                    check(f'frame-{index}-{panel["view"]}-independent-pixels',actual==bytes(expected))
        old={p.name:sha(p) for p in folder.iterdir() if p.is_file()}
        refused=cli('existing',*command,expect=2)
        check('existing-output-unmodified',not refused['ok'] and old=={p.name:sha(p) for p in folder.iterdir() if p.is_file()})
        cancel=project/'operations/contact-cancel';cancel.touch()
        denied=cli('precancel','media','contact-sheet','--project',str(project),'--asset-id','alpha',
            '--output','validation/cancelled','--cancel-file',str(cancel),expect=8)
        check('precancel-no-output',denied['errors'][0]['code']=='CANCELLED' and not (project/'validation/cancelled').exists())
        outside=cli('external','media','contact-sheet','--project',str(project),'--asset-id','alpha',
            '--output',str(work/'outside'),expect=2)
        check('outside-output-rejected',not outside['ok'] and not (work/'outside').exists())
        shutil.copytree(folder,assets/'contact')
        record['contact_manifest']=report
        record['cli_calls']=sum(c['label'].startswith('cli-') for c in record['calls'])
        record['public_files']=[{'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)}
            for p in sorted(assets.rglob('*')) if p.is_file()]
        record.update(status='passed',static_review='pending',continuous_playback_reviewed=False,audio_listening_reviewed=False)
    except BaseException as exc:
        record.update(status='failed',error={'type':type(exc).__name__,'message':str(exc)})
        raise
    finally:
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),frozen_after=frozen())
        record['frozen_equal']=record['frozen_before']==record['frozen_after'];save()
    if not record['frozen_equal']:raise AssertionError('product bytes changed')
    print(json.dumps({'status':record['status'],'checks':len(record['checks']),'cli_calls':record['cli_calls'],'frozen_equal':record['frozen_equal']}))


if __name__=='__main__':main()
