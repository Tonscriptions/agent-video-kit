"""Public, reproducible subtitle segmentation fixtures using native local CLI.

The video/tone/text fixtures are authored here and dedicated to CC0-1.0.
Manual onsets are synthetic, never ASR. The reference has independently
authored text/ticks but uses the same product renderer. No font binaries are
published. No browser, model, network request or package installation.
"""
from __future__ import annotations
import argparse
import array
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import wave
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'product/src'))
from ai_ad_editor.media import probe_media
from ai_ad_editor.runtime import configure_local_runtime

TPS, FPS, W, H, SR, SECONDS = 90000, 8, 640, 360, 48000, 6


def sha(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def frozen():
    files = [*(ROOT/'product/src').rglob('*.py'), *(ROOT/'product/tests').rglob('*.py'),
             *(ROOT/'product/src').rglob('*.mjs'), ROOT/'product/pyproject.toml',
             ROOT/'docs/specs/agent-project.schema.json', ROOT/'product/src/ai_ad_editor/OPENFILM_LICENSE.txt']
    return {p.relative_to(ROOT).as_posix():sha(p) for p in sorted(files)}


def decode(path, *, fps=None, audio=False):
    cmd=['ffmpeg','-v','error','-i',str(path)]
    cmd += ['-vn','-ac','2','-ar',str(SR),'-f','f32le','pipe:1'] if audio else ['-an',*(['-vf',f'fps={fps}'] if fps else []),'-pix_fmt','rgb24','-f','rawvideo','pipe:1']
    return subprocess.run(cmd,capture_output=True,check=True).stdout


def run(output, work, font, font_license, latin_font, latin_license):
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    from fontTools.ttLib import TTFont
    configure_local_runtime()
    output.mkdir(parents=True,exist_ok=False)
    work.mkdir(parents=True,exist_ok=False)
    logs=work/'cli-logs';logs.mkdir()
    before=frozen()
    env=dict(os.environ);env['PYTHONPATH']=str(ROOT/'product/src');env['PYTHONDONTWRITEBYTECODE']='1'
    calls=[]
    def cli(*args, expected=0):
        p=subprocess.run([sys.executable,'-B','-X','utf8','-m','ai_ad_editor',*map(str,args)],env=env,cwd=ROOT,capture_output=True)
        n=len(calls)+1;stem=f'{n:03}'
        (logs/f'{stem}.stdout.json').write_bytes(p.stdout);(logs/f'{stem}.stderr.log').write_bytes(p.stderr)
        try:d=json.loads(p.stdout)
        except ValueError:raise RuntimeError(p.stderr.decode('utf-8',errors='replace'))
        calls.append({'index':n,'arguments':list(map(str,args)),'command':d.get('command'),'exit_code':p.returncode,'expected':expected,
                      'stdout_sha256':sha(logs/f'{stem}.stdout.json'),'stderr_sha256':sha(logs/f'{stem}.stderr.log')})
        save(work/'calls.json',calls)
        if p.returncode != expected:raise RuntimeError(f'Unexpected CLI result {calls[-1]}\n{p.stdout.decode("utf-8")}')
        return d
    evidence=work/'fixture-rights.json'
    save(evidence,{'license_spdx':'CC0-1.0','creator':'Agent Video Kit fixture authors','purpose':'authored synthetic test video, tones, source/translated/corrected text',
                   'no_speech':True,'manual_onsets_not_asr':True,'generator':str(Path(__file__).resolve())})
    shutil.copyfile(font_license,output/'cjk-font-license.txt');shutil.copyfile(latin_license,output/'font-license.txt')
    # Assert actual font coverage rather than accepting visible replacement boxes.
    cjk_text='本地剪輯，免費開源，字幕清楚。 本地字幕，數字保護，字幕清楚。'
    cmap=TTFont(str(font)).getBestCmap()
    assert not {c for c in cjk_text if not c.isspace() and ord(c) not in cmap}
    label_font=ImageFont.truetype(str(latin_font),20)
    values=np.arange(SR*SECONDS,dtype=np.float64)/SR
    stereo=np.stack([.03*np.sin(2*math.pi*220*values),.02*np.sin(2*math.pi*330*values)],axis=1)
    pcm=np.rint(stereo*32767).astype('<i2')
    tone=output/'tone.wav'
    with wave.open(str(tone),'wb') as wav:
        wav.setnchannels(2);wav.setsampwidth(2);wav.setframerate(SR);wav.writeframes(pcm.tobytes())
    source=output/'source.mp4'
    frames=[]
    for n in range(FPS*SECONDS):
        im=Image.new('RGB',(W,H),(16,25,43));draw=ImageDraw.Draw(im)
        draw.rectangle((0,0,W,55),fill=(30,45,71))
        draw.text((22,17),f'LOCAL SOURCE   {n:02} / {FPS*SECONDS-1:02}   NO SPEECH',font=label_font,fill=(220,231,244))
        x=65+round(330*n/(FPS*SECONDS-1))
        draw.rounded_rectangle((x,90,x+150,220),radius=22,fill=(237,169,73),outline=(255,231,188),width=3)
        draw.ellipse((x+50,112,x+100,162),fill=(51,75,105))
        draw.rectangle((0,250,W,H),fill=(7,12,20))
        frames.append(im.tobytes())
    subprocess.run(['ffmpeg','-v','error','-n','-f','rawvideo','-pixel_format','rgb24','-video_size',f'{W}x{H}','-framerate',str(FPS),'-i','pipe:0',
                    '-i',str(tone),'-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','128k','-shortest',str(source)],input=b''.join(frames),capture_output=True,check=True)
    del frames
    base_text='本地剪輯，免費開源，字幕清楚。'
    chinese=['本地剪輯','免費開源','字幕清楚']
    english=['Local editing.','Free and open source.','Clear captions.']
    ranges=[(45000,142200),(180000,277200),(337500,495000)]
    cases=[]
    preview_frames=[]
    def render(root, published, *, publish=False):
        local=root/'renders'/published.name
        result=cli('render','--project',root,'--output',local,'--profile','custom','--width',str(W),'--height',str(H),*(['--publish'] if publish else []))
        shutil.copyfile(local,published)
        manifest=local.with_name(local.name+'.manifest.json')
        if manifest.exists():shutil.copyfile(manifest,published.with_name(published.name+'.manifest.json'))
        return result
    for number in range(1,5):
        cid=f'S{number:02}'
        text=base_text if number<4 else 'Render in 3.5 s, keep 60 fps, and export the whole clip.'
        second=text.index('免費') if number<4 else text.index('keep')
        third=text.index('字幕') if number<4 else text.index('and')
        line={'id':'ad','text':text,'start_tick':45000,'end_tick':495000,
              'marks':[{'index':0,'start_tick':45000},{'index':second,'start_tick':180000},{'index':third,'start_tick':337500}]}
        if number in (2,3):line['translation']=' '.join(english)
        input_path=output/f'{cid}-source.json'
        save(input_path,{'format':'agent-subtitle-source-v1','ticks_per_second':TPS,'lines':[line]})
        mode='bilingual' if number in (2,3) else 'original'
        expected_texts=chinese[:] if number<4 else ['Render in 3.5 s,','keep 60 fps,','and export the whole clip.']
        intervals=ranges[:] if number<4 else [(45000,180000),(180000,337500),(337500,495000)]
        extra=[]
        if number==3:
            changes=output/f'{cid}-corrections.json'
            save(changes,{'expected_input_sha256':sha(input_path),'edits':[
                {'line_id':'ad','part':0,'text':'本地字幕'}, {'line_id':'ad','part':1,'text':'數字保護'},
                {'line_id':'ad','part':0,'target':'translation','text':'Local captions.'},
                {'line_id':'ad','part':1,'target':'translation','text':'Numbers stay together.'}]})
            extra += ['--corrections',str(changes)]
            expected_texts=['本地字幕','數字保護','字幕清楚']
            translated=['Local captions.','Numbers stay together.','Clear captions.']
        else:translated=english[:]
        if number in (2,3):expected_texts=[a+'\n'+b for a,b in zip(expected_texts,translated)]
        if number==4:
            rules=output/f'{cid}-rules.json';save(rules,{'maxChars':32,'holdMs':2000,'closeGapMs':2000})
            extra += ['--rules',str(rules)]
        def create_project(name):
            root=work/name
            cli('project','init',root)
            p=json.loads((root/'project.json').read_text(encoding='utf-8'))
            p['settings']['timebase']['display_fps']={'num':FPS,'den':1}
            save(root/'project.json',p)  # explicit authored fixture settings
            def ingest(path, license_id):
                return cli('media','ingest','--project',root,'--input',path,'--license-spdx',license_id,
                    '--creator','Agent Video Kit fixture authors' if license_id=='CC0-1.0' else 'Kosugi Maru contributors',
                    '--evidence',evidence if license_id=='CC0-1.0' else font_license,'--verification-status','verified',
                    '--permitted-use','internal','--permitted-use','commercial_ad')['data']['asset']
            v=ingest(source,'CC0-1.0');a=ingest(tone,'CC0-1.0');f=ingest(font,'Apache-2.0')
            p=json.loads((root/'project.json').read_text(encoding='utf-8'))
            vid=next(t['id'] for t in p['sequences'][0]['tracks'] if t['kind']=='video')
            aud=next(t['id'] for t in p['sequences'][0]['tracks'] if t['kind']=='audio')
            ops=[{'op':'add_track','track_id':'captions','kind':'subtitle','order':10},
                 {'op':'append_clip','track_id':vid,'clip_id':'video','asset_id':v['id'],'timeline_start_tick':0,'source_in_tick':0,'source_out_tick':SECONDS*TPS},
                 {'op':'append_clip','track_id':aud,'clip_id':'audio','asset_id':a['id'],'timeline_start_tick':0,'source_in_tick':0,'source_out_tick':SECONDS*TPS}]
            plan=root/'cache/setup.json';save(plan,{'operations':ops});cli('timeline','compose','--project',root,'--input',plan)
            return root,f
        root, font_asset=create_project(cid)
        style={'fontsize':22,'fontcolor':'white','borderw':2,'bordercolor':'black','x':'(w-text_w)/2','y':'h-text_h-32','font_asset_id':font_asset['id']}
        whole=text if number!=2 else text+'\n'+' '.join(english)
        plan=root/'cache/whole.json'
        save(plan,{'operations':[{'op':'append_clip','track_id':'captions','clip_id':'whole','timeline_start_tick':45000,'duration_tick':450000,'source_in_tick':0,'source_out_tick':450000,
                                 'generator':{'type':'text'},'subtitle':{'text':whole,'style':style}}]})
        cli('timeline','compose','--project',root,'--input',plan)
        before_video=output/f'{cid}-whole-line.mp4'
        render(root,before_video)
        options=['subtitle','segment','--project',root,'--input',input_path,'--output','assets/subtitles/segmented.json','--mode',mode,
                 '--apply','--track-id','captions','--replace-track','--font-asset-id',font_asset['id'],*extra]
        meta_before={p.name:sha(p) for p in [root/'project.json',root/'project.lock.json',root/'rights-ledger.json']}
        preview=cli(*options,'--dry-run')
        assert meta_before=={p.name:sha(p) for p in [root/'project.json',root/'project.lock.json',root/'rights-ledger.json']}
        actual=cli(*options,'--idempotency-key',cid)
        replay=cli(*options,'--idempotency-key',cid)
        assert replay['operation_id']==actual['operation_id']
        cues=actual['data']['plan']['display_cues']
        assert [c['text'] for c in cues]==expected_texts, (cid,cues,expected_texts)
        assert [(c['start_tick'],c['end_tick']) for c in cues]==intervals,(cid,cues,intervals)
        save(output/f'{cid}-expected.json',{'texts':expected_texts,'intervals':intervals,'independent_authorship':True,'same_renderer':True})
        save(output/f'{cid}-actual-plan.json',actual['data']['plan'])
        shutil.copyfile(root/'assets/subtitles/segmented.srt',output/f'{cid}-actual.srt')
        # A stale correction/dry-run hash must reject before any output.
        rejected=cli(*options,'--output','assets/subtitles/stale.json','--expected-input-sha256','sha256:'+'0'*64,expected=2)
        assert rejected['errors'][0]['code']=='SUBTITLE_SEGMENT_STALE_INPUT'
        patch_ops=[]
        for c in actual['data']['generated_clips']:
            sub=copy.deepcopy(c['subtitle']);sub['style']=style
            patch_ops.append({'op':'update_clip','clip_id':c['id'],'track_id':'captions','patch':{'subtitle':sub}})
        plan=root/'cache/style.json';save(plan,{'operations':patch_ops});cli('timeline','compose','--project',root,'--input',plan)
        cli('rights','check','--project',root,expected=7)
        for asset in actual['data']['registered_assets']:
            cli('rights','update','--project',root,'--asset-id',asset['id'],'--status','verified',
                '--license-spdx','CC0-1.0','--creator','Agent Video Kit fixture authors','--evidence',evidence,
                '--permitted-use','internal','--permitted-use','commercial_ad','--reason','Explicit authored synthetic transcript/translation fixture')
        cli('rights','check','--project',root)
        after_video=output/f'{cid}-segmented.mp4'
        render(root,after_video,publish=True)
        cli('quality','check','--project',root,'--input',root/'renders'/after_video.name,'--width',str(W),'--height',str(H),'--require-audio')
        cli('validate','--project',root);cli('policy','audit','--project',root)
        reference_root, reference_font=create_project(cid+'-reference')
        ref_style={**style,'font_asset_id':reference_font['id']}
        ref_ops=[]
        for i,((a,b),text_value) in enumerate(zip(intervals,expected_texts)):
            ref_ops.append({'op':'append_clip','track_id':'captions','clip_id':f'reference_{i}',
                            'timeline_start_tick':a,'duration_tick':b-a,'source_in_tick':0,'source_out_tick':b-a,
                            'generator':{'type':'text'},'subtitle':{'text':text_value,'style':ref_style}})
        ref_plan=reference_root/'cache/manual-reference.json';save(ref_plan,{'operations':ref_ops})
        cli('timeline','compose','--project',reference_root,'--input',ref_plan)
        reference_video=output/f'{cid}-reference.mp4'
        render(reference_root,reference_video)
        video_actual,video_reference=decode(after_video),decode(reference_video)
        assert len(video_actual)==FPS*SECONDS*W*H*3
        assert video_actual==video_reference, f'{cid} actual differs from hand-authored same-renderer reference'
        audio_before,audio_actual=decode(before_video,audio=True),decode(after_video,audio=True)
        assert audio_before==audio_actual, f'{cid} subtitle edit changed audio'
        case={'id':cid,'mode':mode,'input_sha256':sha(input_path),'actual_sha256':sha(after_video),'reference_sha256':sha(reference_video),
              'frames':FPS*SECONDS,'video_rgb_exact_to_manual_same_renderer_reference':True,
              'audio_unchanged_to_whole_line_render':True,'audio_decoded_sample_frames':len(audio_actual)//8,
              'manual_marks_not_asr':True,'expected':{'texts':expected_texts,'intervals':intervals},'versions':actual['data']['plan']['algorithm']['versions']}
        cases.append(case)
        # Montage samples all six seconds at 2 fps; display copy has no audio.
        a=np.frombuffer(decode(before_video,fps=2),dtype=np.uint8).reshape(-1,H,W,3)
        b=np.frombuffer(decode(after_video,fps=2),dtype=np.uint8).reshape(-1,H,W,3)
        for left,right in zip(a,b):
            im=Image.new('RGB',(960,302),(13,20,32));draw=ImageDraw.Draw(im)
            im.paste(Image.fromarray(left).resize((480,270)),(0,32));im.paste(Image.fromarray(right).resize((480,270)),(480,32))
            draw.text((12,6),cid+'  WHOLE SOURCE LINE',font=label_font,fill=(230,236,245))
            draw.text((492,6),cid+'  ACTUAL SEGMENTED',font=label_font,fill=(133,225,171))
            preview_frames.append(im)
        print(json.dumps(case,ensure_ascii=False),flush=True)
    preview=output/'comparison.mp4'
    subprocess.run(['ffmpeg','-v','error','-n','-f','rawvideo','-pixel_format','rgb24','-video_size','960x302','-framerate','2','-i','pipe:0',
                    '-an','-c:v','libx264','-crf','20','-pix_fmt','yuv420p',str(preview)],input=b''.join(im.tobytes() for im in preview_frames),capture_output=True,check=True)
    preview_frames[0].save(output/'comparison.gif',save_all=True,append_images=preview_frames[1:],duration=500,loop=0,optimize=False)
    for label,index in [('first',2),('middle',len(preview_frames)//2+2),('last',len(preview_frames)-3)]:
        preview_frames[index].save(output/f'comparison-{label}.png')
    assert frozen()==before
    with zipfile.ZipFile(output/'cli-logs.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(logs.iterdir()):archive.write(path,path.name)
    save(output/'cli-calls.json',calls)
    provenance={'created_at_utc':datetime.now(timezone.utc).isoformat(),'generator':Path(__file__).relative_to(ROOT).as_posix(),
        'generator_sha256':sha(Path(__file__)),'media_license_spdx':'CC0-1.0','source':'authored procedural raster/stereo tones and manual text/onsets',
        'models':0,'browsers':0,'speech':False,'continuous_playback_reviewed':False,'audio_listened':False,
        'fonts':[{'name':font.name,'sha256':sha(font),'license_spdx':'Apache-2.0','license_sha256':sha(font_license),'binary_distributed':False},
                 {'name':latin_font.name,'sha256':sha(latin_font),'license_spdx':'LicenseRef-DejaVu-Fonts','license_sha256':sha(latin_license),'binary_distributed':False}],
        'cjk_cmap_checked_text':cjk_text,'source_video':{'width':W,'height':H,'fps':FPS,'frames':FPS*SECONDS,'seconds':SECONDS},
        'montage':{'width':960,'height':302,'fps':2,'frames':len(preview_frames),'seconds':len(preview_frames)/2,'audio':False}}
    save(output/'fixture-provenance.json',provenance)
    report={'checked_at_utc':datetime.now(timezone.utc).isoformat(),'status':'passed','cases':cases,'cli_calls':len(calls),
            'expected_rejections':sum(c['expected']!=0 for c in calls),'new_video_frames':sum(c['frames'] for c in cases),
            'new_audio_sample_frames':sum(c['audio_decoded_sample_frames'] for c in cases),
            'frozen_before':before,'frozen_after':frozen(),'limits':['same renderer for manual video reference','synthetic onsets, no speech/ASR','audio equality is unchanged path, not independent acoustic quality','no continuous playback or listening'],
            'files':{p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(output.iterdir()) if p.is_file()}}
    save(output/'verification.json',report)
    print(json.dumps({'status':'passed','cases':len(cases),'cli_calls':len(calls),'new_video_frames':report['new_video_frames']},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('output','work','font','font-license','latin-font','latin-license'):parser.add_argument('--'+name,type=Path,required=True)
    a=parser.parse_args()
    run(a.output.resolve(),a.work.resolve(),a.font.resolve(),a.font_license.resolve(),a.latin_font.resolve(),a.latin_license.resolve())
