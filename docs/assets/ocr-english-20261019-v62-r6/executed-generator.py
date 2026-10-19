"""Real native OCR calls over original controlled media; no DOM/answer to worker."""
from __future__ import annotations
import argparse, gzip, hashlib, json, os, shutil, subprocess, sys, traceback
from pathlib import Path
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
NATIVE=Path('D:/dev/comfyui/ComfyUI_windows_portable_nvidia_0_30_0/ComfyUI_windows_portable/python_embeded/python.exe')
MODEL=ROOT/'sources/models/rapidocr-1.3.25-20261019-v62/extracted/rapidocr_onnxruntime/models'


def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')


def run(work,output,kind,installed=None):
    work.mkdir(parents=True,exist_ok=False);output.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(Path(__file__),output/'executed-generator.py')
    before=frozen();calls=[]
    record={'status':'running','frozen_before':before,'calls':calls,'kind':kind,'network_during_runtime':False,
            'model_source':'rapidocr-onnxruntime-1.3.25','generator_sha256':sha(Path(__file__)),
            'controlled_source':True,'natural_quality_accepted':False,'continuous_playback_or_listening':False,
            'installed_root':str(installed) if installed else None}
    bootstrap='import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.cli import main;raise SystemExit(main())'
    env=dict(os.environ);env.update(TEMP=str(work),TMP=str(work),TMPDIR=str(work),PYTHONDONTWRITEBYTECODE='1',AI_AD_EDITOR_RUNTIME_DIR=str(work/'runtime'))
    def cli(*args,expected=0):
        name=f'{len(calls)+1:03d}'
        prefix=[sys.executable,'-I','-S','-B','-X','utf8',str(installed/'run.py')] if installed else [sys.executable,'-E','-B','-X','utf8','-c',bootstrap,str(ROOT/'product/src')]
        command=[*prefix,*map(str,args)]
        result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,timeout=700)
        (output/(name+'.stdout.json')).write_bytes(result.stdout);(output/(name+'.stderr.log')).write_bytes(result.stderr)
        calls.append({'command':command,'kind':'cli','exit_code':result.returncode,'expected_exit_code':expected,
            'stdout':name+'.stdout.json','stderr':name+'.stderr.log','stdout_sha256':sha(output/(name+'.stdout.json')),
            'stderr_sha256':sha(output/(name+'.stderr.log'))})
        save(output/'verification.json',record)
        value=json.loads(result.stdout)
        if result.returncode!=expected:raise RuntimeError(json.dumps(value,ensure_ascii=False)[-5500:])
        return value
    def native(*args):
        name=f'{len(calls)+1:03d}'
        command=list(map(str,args));result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,timeout=180)
        compressed=len(result.stdout)>65536;stdout=name+('.stdout.gz' if compressed else '.stdout')
        (output/stdout).write_bytes(gzip.compress(result.stdout,mtime=0) if compressed else result.stdout)
        (output/(name+'.stderr.log')).write_bytes(result.stderr)
        calls.append({'command':command,'kind':'native','exit_code':result.returncode,'expected_exit_code':0,
            'stdout':stdout,'stderr':name+'.stderr.log','stdout_sha256':sha(output/stdout),
            'stderr_sha256':sha(output/(name+'.stderr.log')),'stdout_compressed':compressed,
            'stdout_decoded_sha256':'sha256:'+hashlib.sha256(result.stdout).hexdigest(),'stdout_decoded_bytes':len(result.stdout)})
        save(output/'verification.json',record)
        if result.returncode:raise RuntimeError(result.stderr.decode('utf-8',errors='replace')[-4000:])
        return result.stdout
    try:
        project=work/'project';cli('project','init',project)
        if kind=='english':
            origin=ROOT/'docs/assets/openfilm-workflow-screen-20261019-v61-r3'
            source=output/'original-screen.mkv'
            # The historical capture is silent; explicitly mux its original
            # six-second procedural tone, rather than treating generated
            # output silence as preservation of source audio.
            native('ffmpeg','-nostdin','-v','error','-n','-i',origin/'screen-input.mkv','-i',origin/'original-tone.wav',
                   '-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','pcm_f32le','-shortest',source)
            record['original_components']=[{'path':str(origin/n),'sha256':sha(origin/n)} for n in ('screen-input.mkv','original-tone.wav')]
            original_kind='video';indices=['--start-frame','0','--end-frame','48','--step-frames','8']
        else:
            from PIL import Image,ImageDraw,ImageFont
            source=output/'original-chinese.png'
            font_source=ROOT/'sources/upstream/concat/src/crates/concat/fonts/NotoSansCJKsc-Concat.otf'
            image=Image.new('RGB',(960,540),(244,247,252));draw=ImageDraw.Draw(image);font=ImageFont.truetype(str(font_source),36)
            truths=[]
            for x,y,text in ((70,70,'本地视频剪辑'),(70,190,'预览广告效果'),(70,310,'保存当前方案')):
                draw.text((x,y),text,font=font,fill=(20,35,55));truths.append({'text':text,'glyph_bbox':list(draw.textbbox((x,y),text,font=font))})
            latin=ImageFont.truetype(str(ROOT/'docs/assets/openfilm-workflow-screen-20261019-v61-r3/DejaVuSans.ttf'),36)
            cursor=570.;bounds=[]
            for ch in '价格199元':
                selected=latin if ch.isascii() else font
                draw.text((cursor,445),ch,font=selected,fill=(20,35,55),anchor='ls')
                bounds.append(draw.textbbox((cursor,445),ch,font=selected,anchor='ls'));cursor+=selected.getlength(ch)
            truths.append({'text':'价格199元','glyph_bbox':[min(b[0] for b in bounds),min(b[1] for b in bounds),max(b[2] for b in bounds),max(b[3] for b in bounds)],'explicit_latin_fallback':True})
            image.save(source);save(output/'expected-chinese.json',{'truth_source':'authored_original_text_and_font_bbox_not_model_output','targets':truths})
            original_kind='image';indices=['--end-frame','1','--step-frames','1']
        source_asset=cli('media','ingest','--project',project,'--input',source)['data']['asset']['id']
        cli('ocr','adapter','register','--project',project,'--adapter-id','ocr_v62','--model-path',MODEL,
            '--python-executable',NATIVE,'--evidence',ROOT/'docs/validation/evidence/ocr-acquisition-20261019-v62/sources.json',
            '--license-spdx','Apache-2.0','--creator','PaddleOCR / RapidOCR')
        baseline=(project/'project.json').read_bytes()
        cli('ocr','scan','--project',project,'--asset-id',source_asset,'--adapter-id','ocr_v62',
            '--output','validation/text.json',*indices,'--dry-run')
        assert baseline==(project/'project.json').read_bytes()
        cli('ocr','scan','--project',project,'--asset-id',source_asset,'--adapter-id','ocr_v62',
            '--output','validation/text.json',*indices)
        shutil.copyfile(project/'validation/text.json',output/'ocr-report.json')
        if kind=='english':
            value=json.loads((project/'project.json').read_bytes())
            value['settings']['canvas'].update(width=640,height=360)
            value['settings']['timebase']['display_fps']={'num':8,'den':1}
            save(project/'project.json',value)
            compose=output/'compose.json';save(compose,{'operations':[
                {'op':'append_clip','track_id':'track_video_1','id':'screen','asset_id':source_asset,'source_in_tick':0,'source_out_tick':540000,'link_id':'screen_group'},
                {'op':'append_clip','track_id':'track_audio_1','id':'sound','asset_id':source_asset,'source_in_tick':0,'source_out_tick':540000,'link_id':'screen_group'}]})
            cli('timeline','compose','--project',project,'--input',compose)
            variants=[]
            # Explicit demonstration queries selected after the first development scan.
            # They prove editable geometry, not a blind OCR accuracy benchmark.
            for name,query,index in (('select','Select local campaign',0),('preview','Preview headline',8),
                                     ('save','Save plan in this page',0),('result','Plan saved locally in page state.',32)):
                variant=work/name;shutil.copytree(project,variant)
                baseline=(variant/'project.json').read_bytes()
                options=['ocr','anchors','--project',variant,'--report','validation/text.json','--clip-id','screen',
                         '--query',query,'--frame-index',str(index),'--zoom','1.5','--hold-seconds','.5','--return-seconds','.5']
                cli(*options,'--apply','--dry-run');assert baseline==(variant/'project.json').read_bytes()
                applied=cli(*options,'--apply');save(output/(name+'.anchor.json'),applied['data']['plan'])
                target=variant/'renders'/f'{name}.mkv'
                rendered=cli('render','--project',variant,'--output',target,'--container','mkv',
                    '--pixel-format','yuv444p','--crf','0','--audio-codec','pcm_f32le')
                shutil.copyfile(target,output/target.name);shutil.copyfile(rendered['data']['manifest'],output/(name+'.render-manifest.json'))
                cli('quality','check','--project',variant,'--input',target,'--require-audio')
                cli('policy','audit','--project',variant)
                cli('rights','check','--project',variant,'--target','commercial_ad',expected=7)
                native('ffmpeg','-nostdin','-v','error','-n','-i',target,'-an','-c:v','libx264','-crf','17','-pix_fmt','yuv420p',output/(name+'.mp4'))
                native('ffmpeg','-nostdin','-v','error','-n','-i',target,'-an','-vf',
                       'fps=8,scale=480:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse',output/(name+'.gif'))
                package=output/(name+'.aevpkg.zip')
                cli('convert','export','--project',variant,'--target-format','package','--output',package)
                variants.append({'name':name,'query':query,'source_frame':index,'project':str(variant),'render':str(target)})
            cli('ocr','anchors','--project',project,'--report','validation/text.json','--clip-id','screen',
                '--query','OPEN LOCAL VIDEO','--frame-index','24','--apply',expected=2)
            for name,flags,expected in (('timeout',['--timeout','.1'],6),('cancel',['--cancel-file',str(project/'cancel.flag')],8)):
                if name=='cancel':(project/'cancel.flag').write_text('cancel',encoding='utf-8')
                metadata=tuple((project/n).read_bytes() for n in ('project.json','rights-ledger.json','project.lock.json'))
                cli('ocr','scan','--project',project,'--asset-id',source_asset,'--adapter-id','ocr_v62',
                    '--output','validation/'+name+'.json',*indices,*flags,expected=expected)
                assert metadata==tuple((project/n).read_bytes() for n in ('project.json','rights-ledger.json','project.lock.json'))
                assert not (project/'validation'/(name+'.json')).exists()
            record['variants']=variants
        record.update(status='passed_native_scan',source_kind=original_kind,source_sha256=sha(source),project=str(project),source_asset_id=source_asset)
    except BaseException as error:
        record.update(status='failed',error=str(error),traceback=traceback.format_exc())
        raise
    finally:
        after=frozen();record.update(frozen_after=after,frozen_equal=before==after)
        save(output/'verification.json',record)
        print(json.dumps({k:record[k] for k in ('status','kind','frozen_equal','source_asset_id') if k in record},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--kind',choices=('english','chinese'),required=True);p.add_argument('--installed-root',type=Path)
    args=p.parse_args();run(args.work.resolve(),args.output.resolve(),args.kind,args.installed_root.resolve() if args.installed_root else None)
