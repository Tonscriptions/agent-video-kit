"""Observe four static-only effect paths in a pinned released source tree."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def digest(raw): return 'sha256:'+hashlib.sha256(raw).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); root=args.source.resolve(); output=args.output.resolve()
    assert not output.exists()
    sys.path.insert(0,str(root/'product/src'));sys.path.insert(0,str(root/'scripts'))
    from run_frozen_regression import frozen
    from ai_ad_editor.render import _effect_filters
    from ai_ad_editor.effect_automation import EffectAutomation, runtime_options
    from ai_ad_editor.effects import effect_catalog
    from ai_ad_editor.media import ffmpeg_path
    from ai_ad_editor.text_highlight import file_fingerprint
    before=frozen(); output.parent.mkdir(parents=True,exist_ok=True)
    record={'started_at_utc':datetime.now(timezone.utc).isoformat(),'status':'running',
        'source':str(root),'module_origin':__import__('ai_ad_editor.render',fromlist=['x']).__file__,
        'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        'catalog_version':effect_catalog()['catalog_version'],'frozen_before':before,
        'generator_sha256':digest(Path(__file__).read_bytes()),'network':False,'virtualization':False,'cases':[]}
    def save(): output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    save()
    exe=ffmpeg_path(); fp=file_fingerprint(Path(exe)); size=64*36*4
    frame=bytes(c for y in range(36) for x in range(64) for c in (
        25+(x//4%2)*190, 225-(y//4%2)*175, 35+(x*3+y*5)%190, 255))
    specs=[('blur','radius',.2,7,'gblur'),('color_contrast','red',-.5,.5,'colorcontrast'),
           ('lens_correction','k1',-.5,.5,'lenscorrection'),('chroma_key','similarity',.01,.5,'colorkey')]
    try:
        for kind,prop,left,right,backend in specs:
            effect={'type':kind,'keyframes':[{'property':prop,'keyframes':[
                {'at_tick':0,'value':left,'interpolation':'linear'},
                {'at_tick':90000,'value':right,'interpolation':'linear'}]}]}
            warnings=[]; compiler=EffectAutomation(output.parent/'cache-root','10',90000)
            chain=_effect_filters([effect],warnings,'baseline',root=output.parent,
                clip={'id':'baseline','duration_tick':90000},automation=compiler)
            command=[exe,'-v','error','-filter_threads','1','-f','rawvideo','-pixel_format','rgba',
                '-video_size','64x36','-framerate','10','-i','pipe:0','-vf',','.join(chain),
                '-f','rawvideo','-pix_fmt','rgba','pipe:1']
            result=subprocess.run(command,input=frame*10,capture_output=True,cwd=root,timeout=90)
            output.with_name(kind+'.stderr.log').write_bytes(result.stderr)
            assert result.returncode==0,result.stderr.decode('utf8','replace')
            assert len(result.stdout)==size*10
            hashes=[digest(result.stdout[i*size:(i+1)*size]) for i in range(10)]
            record['cases'].append({'effect':effect,'filters':chain,'warnings':warnings,
                'runtime_options':sorted(runtime_options(exe,fp,backend)),'compiler':compiler.summary(),
                'command':command,'exit_code':result.returncode,'decoded_sha256':digest(result.stdout),
                'frame_sha256':hashes,'unique_frames':len(set(hashes))})
            assert compiler.targets==0 and len(set(hashes))==1
            save()
        record['status']='observed-static-only'
    except BaseException as exc:
        record.update(status='failed',error={'type':type(exc).__name__,'message':str(exc)});raise
    finally:
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),frozen_after=frozen())
        record['frozen_equal']=record['frozen_before']==record['frozen_after'];save()
    assert record['frozen_equal']
    print(json.dumps({'status':record['status'],'cases':len(record['cases']),'frozen_equal':record['frozen_equal']}))


if __name__=='__main__':main()
