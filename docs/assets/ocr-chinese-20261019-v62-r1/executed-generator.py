"""Real native OCR calls over original controlled media; no DOM/answer to worker."""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess, sys, traceback
from pathlib import Path
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
NATIVE=Path('D:/dev/comfyui/ComfyUI_windows_portable_nvidia_0_30_0/ComfyUI_windows_portable/python_embeded/python.exe')
MODEL=ROOT/'sources/models/rapidocr-1.3.25-20261019-v62/extracted/rapidocr_onnxruntime/models'


def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')


def run(work,output,kind):
    work.mkdir(parents=True,exist_ok=False);output.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(Path(__file__),output/'executed-generator.py')
    before=frozen();calls=[]
    record={'status':'running','frozen_before':before,'calls':calls,'kind':kind,'network_during_runtime':False,
            'model_source':'rapidocr-onnxruntime-1.3.25','generator_sha256':sha(Path(__file__)),
            'controlled_source':True,'natural_quality_accepted':False,'continuous_playback_or_listening':False}
    bootstrap='import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.cli import main;raise SystemExit(main())'
    env=dict(os.environ);env.update(TEMP=str(work),TMP=str(work),TMPDIR=str(work),PYTHONDONTWRITEBYTECODE='1',AI_AD_EDITOR_RUNTIME_DIR=str(work/'runtime'))
    def cli(*args,expected=0):
        name=f'{len(calls)+1:03d}'
        command=[sys.executable,'-I','-B','-X','utf8','-c',bootstrap,str(ROOT/'product/src'),*map(str,args)]
        result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,timeout=700)
        (output/(name+'.stdout.json')).write_bytes(result.stdout);(output/(name+'.stderr.log')).write_bytes(result.stderr)
        calls.append({'command':command,'exit_code':result.returncode,'stdout':name+'.stdout.json','stderr':name+'.stderr.log'})
        save(output/'verification.json',record)
        value=json.loads(result.stdout)
        if result.returncode!=expected:raise RuntimeError(json.dumps(value,ensure_ascii=False)[-5500:])
        return value
    try:
        project=work/'project';cli('project','init',project)
        if kind=='english':
            source=ROOT/'docs/assets/openfilm-workflow-screen-20261019-v61-r3/screen-input.mkv'
            original_kind='video';indices=['--start-frame','0','--end-frame','48','--step-frames','8']
        else:
            from PIL import Image,ImageDraw,ImageFont
            source=output/'original-chinese.png'
            font_source=ROOT/'sources/upstream/concat/src/crates/concat/fonts/NotoSansCJKsc-Concat.otf'
            image=Image.new('RGB',(960,540),(244,247,252));draw=ImageDraw.Draw(image);font=ImageFont.truetype(str(font_source),36)
            truths=[]
            for x,y,text in ((70,70,'本地视频剪辑'),(70,190,'预览广告效果'),(70,310,'保存当前方案'),(570,400,'价格 199 元')):
                draw.text((x,y),text,font=font,fill=(20,35,55));truths.append({'text':text,'glyph_bbox':list(draw.textbbox((x,y),text,font=font))})
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
        record.update(status='passed_native_scan',source_kind=original_kind,source_sha256=sha(source),project=str(project),source_asset_id=source_asset)
    except BaseException as error:
        record.update(status='failed',error=str(error),traceback=traceback.format_exc())
        raise
    finally:
        after=frozen();record.update(frozen_after=after,frozen_equal=before==after)
        save(output/'verification.json',record)
        print(json.dumps({k:record[k] for k in ('status','kind','frozen_equal','source_asset_id') if k in record},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--kind',choices=('english','chinese'),required=True)
    args=p.parse_args();run(args.work.resolve(),args.output.resolve(),args.kind)
