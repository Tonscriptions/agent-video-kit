"""Render archived/current CLI geometry and text, with independent encoded pixel gates."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASELINE = 'adb45d00ede5cfa9f57713df1c56f4e7812723a9'


def sha(path):
    return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')


def run(output, work, font, license_file, license_id):
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont, ImageSequence

    if output.exists() or work.exists():
        raise ValueError('Use fresh work/output directories; existing evidence is never overwritten')
    if not font.is_file() or not license_file.is_file():
        raise ValueError('Supply an existing local font and its actual license')
    output.mkdir(parents=True)
    work.mkdir(parents=True)
    baseline = work/'baseline'
    archive = subprocess.run(['git', '-c', 'core.autocrlf=false', 'archive', '--format=zip', BASELINE, 'product/src'], cwd=ROOT, capture_output=True, check=True).stdout
    with zipfile.ZipFile(io.BytesIO(archive)) as package:
        for name in package.namelist():
            if name in {'product/', 'product/src/'}:
                continue
            if not name.startswith('product/src/') or not (baseline/name).resolve().is_relative_to(baseline.resolve()):
                raise ValueError('Unexpected archive path')
        package.extractall(baseline)
    project = work/'project'
    calls = []
    source_before = sha(ROOT/'product/src/ai_ad_editor/render.py')
    bootstrap = 'import sys; sys.path.insert(0,sys.argv.pop(1)); from ai_ad_editor.runtime import configure_local_runtime; configure_local_runtime(); from ai_ad_editor.cli import main; raise SystemExit(main())'

    def cli(*args, old=False):
        began = time.monotonic()
        src = baseline/'product/src' if old else ROOT/'product/src'
        result = subprocess.run([sys.executable, '-I', '-B', '-X', 'utf8', '-c', bootstrap, str(src), *map(str, args)], cwd=ROOT, capture_output=True, timeout=240)
        value = json.loads(result.stdout.decode('utf-8-sig'))
        calls.append({'argv': list(map(str, args)), 'baseline': old, 'exit_code': result.returncode, 'seconds': time.monotonic()-began, 'result': value})
        save(work/'partial-calls.json', calls)
        if result.returncode:
            raise RuntimeError(value)
        return value

    def compose(ops):
        change = work/'changes.json'
        save(change, {'operations': ops})
        cli('timeline', 'compose', '--project', project, '--input', change)

    def ffmpeg(args, data=None):
        result = subprocess.run(['ffmpeg', '-v', 'error', *args], input=data, capture_output=True, timeout=240)
        if result.returncode:
            raise RuntimeError(result.stderr.decode('utf-8', 'replace'))
        return result.stdout

    def encode(path, frames):
        ffmpeg(['-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '512x288', '-r', '8', '-i', 'pipe:0', '-an', '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p', str(path)], np.stack(frames).tobytes())

    def decode(path):
        return np.frombuffer(ffmpeg(['-i', str(path), '-map', '0:v:0', '-an', '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1']), np.uint8).reshape(-1, 288, 512, 3)

    backgrounds = []
    for index in range(32):
        image = Image.new('RGB', (512, 288), '#18364b')
        draw = ImageDraw.Draw(image)
        for x in range(-32, 544, 32):
            draw.line((x+index//2, 0, x+index//2, 287), fill='#294a5d')
        for y in range(0, 288, 32):
            draw.line((0, y, 511, y), fill='#294a5d')
        backgrounds.append(np.asarray(image).copy())
    encode(output/'source.mp4', backgrounds)
    encode(output/'white-background.mp4', [np.full((288,512,3),255,np.uint8)]*32)
    yy, xx = np.indices((96,96))
    radius = np.sqrt((xx-47.5)**2+(yy-47.5)**2)
    alpha = np.round(np.clip((40-radius)/2,0,1)*255).astype(np.uint8)
    marker = np.zeros((96,96,4),np.uint8)
    marker[:,:,3] = alpha
    marker[alpha>0,:3] = (255,255,255)
    marker[radius<31,:3] = (58,194,167)
    marker[(abs(xx-47.5)<3)&(radius<23),:3] = (255,255,255)
    marker[(abs(yy-47.5)<3)&(radius<23),:3] = (255,255,255)
    Image.fromarray(marker).save(output/'marker-black.png')
    green = marker.copy()
    green[alpha==0,:3] = (0,255,0)
    Image.fromarray(green).save(output/'marker-green.png')
    white = np.full((96,96,4),255,np.uint8)
    white[:,:,3] = alpha
    Image.fromarray(white).save(output/'white-marker.png')
    shutil.copy2(license_file, output/'font-license.txt')
    provenance = output/'fixture-provenance.json'
    save(provenance, {'generated_by':'scripts/smoke_alpha_geometry.py','synthetic_media_license_spdx':'CC0-1.0','third_party_natural_media':False,'model_inference':False,'font':{'path':str(font),'sha256':sha(font),'license_id':license_id,'license_sha256':sha(license_file),'binary_distributed':False},'inputs':{n:sha(output/n) for n in ['source.mp4','white-background.mp4','marker-black.png','marker-green.png','white-marker.png','font-license.txt']}})
    cli('project','init',project,'--name','Alpha affine crop and independent text')
    for asset,name in [('source','source.mp4'),('white_source','white-background.mp4'),('marker_black','marker-black.png'),('marker_green','marker-green.png'),('white_marker','white-marker.png')]:
        cli('media','ingest','--project',project,'--input',output/name,'--asset-id',asset,'--source-url','local://authored-alpha-geometry','--license-spdx','CC0-1.0','--evidence',provenance,'--verification-status','verified','--permitted-use','commercial_ad')
    cli('media','ingest','--project',project,'--input',font,'--asset-id','local_font','--source-url','local://explicit-open-font','--license-spdx',license_id,'--evidence',provenance,'--verification-status','verified','--permitted-use','commercial_ad')
    value = json.loads((project/'project.json').read_text(encoding='utf-8-sig'))
    value['settings']['canvas'].update(width=512,height=288)
    value['settings']['timebase']['display_fps']={'num':8,'den':1}
    save(project/'project.json',value)

    def keys(prop, values):
        return {'property':prop,'keyframes':[{'at_tick':tick,'value':v,'interpolation':'linear'} for tick,v in zip([0,180000,360000],values)]}

    subtitle = {'text':'OPEN AGENT','style':{'font_asset_id':'local_font','fontsize':36,'fontcolor':'#f5cf66','box':False,'borderw':0,'shadowx':0,'shadowy':0,'x':'(w-text_w)/2','y':'(h-text_h)/2'}}
    compose([{'op':'append_clip','track_id':'track_video_1','id':'source_clip','asset_id':'source','source_in_tick':0,'source_out_tick':360000},
        {'op':'add_track','track_id':'labels','kind':'video','order':3},
        {'op':'append_clip','track_id':'labels','id':'marker_clip','asset_id':'marker_black','source_in_tick':0,'source_out_tick':360000,'duration_tick':360000,
         'crop':{'unit':'normalized','x':.03,'y':.04,'width':.95,'height':.9,'fit':'fit'},
         'transform':{'scale':.7,'position':{'x':.5,'y':.55},'anchor':{'x':.4,'y':.6}},
         'keyframes':[keys('crop.width',[.95,.55,.8]),keys('crop.height',[.9,.65,.8]),keys('transform.rotation',[-20,35,-20]),keys('transform.scale',[.7,.55,.75])]},
        {'op':'add_track','track_id':'titles','kind':'subtitle','order':4},
        {'op':'append_clip','track_id':'titles','id':'title_clip','generator':{'type':'text'},'source_in_tick':0,'source_out_tick':360000,'duration_tick':360000,
         'transform':{'scale':.65,'position':{'x':.5,'y':.16}},'keyframes':[keys('transform.rotation',[-10,10,-10])],'subtitle':subtitle}])
    save(output/'authored-timeline.json',json.loads((project/'project.json').read_text(encoding='utf-8-sig'))['sequences'][0])

    def render_pair(name):
        for prefix in ['before','after']:
            target=project/f'renders/{prefix}-{name}.mp4'
            cli('render','--project',project,'--output',target,'--publish',old=(prefix=='before'))
            shutil.copy2(target,output/target.name)
            shutil.copy2(Path(str(target)+'.manifest.json'),output/(target.name+'.manifest.json'))

    render_pair('combined')
    compose([{'op':'update_clip','track_id':'track_video_1','clip_id':'source_clip','patch':{'asset_id':'white_source'}},
        {'op':'update_clip','track_id':'labels','clip_id':'marker_clip','patch':{'asset_id':'white_marker'}},
        {'op':'update_clip','track_id':'titles','clip_id':'title_clip','patch':{'subtitle':{**subtitle,'style':{**subtitle['style'],'fontcolor':'white'}}}}])
    render_pair('white')
    compose([{'op':'update_clip','track_id':'track_video_1','clip_id':'source_clip','patch':{'asset_id':'source'}},
        {'op':'update_clip','track_id':'labels','clip_id':'marker_clip','patch':{'asset_id':'marker_green'}},
        {'op':'update_clip','track_id':'titles','clip_id':'title_clip','patch':{'subtitle':subtitle}}])
    render_pair('green')
    decoded={name:decode(output/(name+'.mp4')) for name in ['source','before-combined','after-combined','before-white','after-white','before-green','after-green']}
    invariant={};white_checks={};positive={}
    for prefix in ['before','after']:
        diff=np.abs(decoded[prefix+'-combined'].astype(np.int16)-decoded[prefix+'-green'].astype(np.int16))
        invariant[prefix]={'max_rgb_difference':int(diff.max()),'changed_components':int(np.count_nonzero(diff)),'mean_absolute_rgb_difference':float(diff.mean())}
        pixels=decoded[prefix+'-white'];errors=255-pixels
        white_checks[prefix]={'minimum_rgb':int(pixels.min()),'max_white_error':int(errors.max()),'components_beyond_5':int(np.count_nonzero(errors>5)),'per_frame_minimum_rgb':[int(frame.min()) for frame in pixels]}
    assert invariant['before']['max_rgb_difference']>0 and invariant['after']['max_rgb_difference']==0
    assert white_checks['before']['max_white_error']>5 and white_checks['after']['max_white_error']<=5,white_checks
    for i,frame in enumerate(decoded['after-combined']):
        teal=(frame[:,:,1]>120)&(frame[:,:,2]>90)&(frame[:,:,0]<100)
        gold=(frame[:,:,0]>160)&(frame[:,:,1]>140)&(frame[:,:,2]<135)
        assert int(teal.sum())>100 and int(gold.sum())>30
        positive[str(i)]={'teal_foreground_pixels':int(teal.sum()),'gold_text_pixels':int(gold.sum())}
    preview=[];caption_font=ImageFont.truetype(str(font),14)
    checker=Image.new('RGB',(96,96),'#e1e1e1');cd=ImageDraw.Draw(checker)
    for y in range(0,96,12):
        for x in range(0,96,12):
            if (x//12+y//12)%2:cd.rectangle((x,y,x+11,y+11),fill='#a8a8a8')
    checker.paste(Image.fromarray(marker),mask=Image.fromarray(alpha))
    for i in range(32):
        sheet=Image.new('RGB',(960,432),'#142131');draw=ImageDraw.Draw(sheet)
        for col,(name,title) in enumerate([('source','ORIGINAL VIDEO'),('before-combined','BEFORE / CROP + ROTATE + TEXT'),('after-combined','AFTER / SAME TIMELINE')]):
            draw.text((col*320+6,4),title,fill='white',font=caption_font)
            sheet.paste(Image.fromarray(decoded[name][i]).resize((320,180),Image.Resampling.LANCZOS),(col*320,26))
        draw.text((6,218),'ORIGINAL RGBA INPUT / CHECKER',fill='white',font=caption_font)
        sheet.paste(checker.resize((180,180),Image.Resampling.NEAREST),(70,246))
        for col,(name,title) in enumerate([('before-white','BEFORE / WHITE-ON-WHITE'),('after-white','AFTER / WHITE-ON-WHITE')],start=1):
            draw.text((col*320+6,218),title,fill='white',font=caption_font)
            sheet.paste(Image.fromarray(decoded[name][i]).resize((320,180),Image.Resampling.LANCZOS),(col*320,246))
        preview.append(sheet)
    ffmpeg(['-y','-f','rawvideo','-pix_fmt','rgb24','-s','960x432','-r','8','-i','pipe:0','-an','-c:v','libx264','-crf','18','-pix_fmt','yuv420p',str(output/'alpha-geometry-comparison.mp4')],np.stack([np.asarray(f) for f in preview]).tobytes())
    preview[0].save(output/'alpha-geometry-comparison.gif',save_all=True,append_images=preview[1:],duration=[120,130]*16,loop=0,disposal=2,optimize=False)
    for i in [0,16,31]:preview[i].save(output/f'contact-frame-{i:02}.png')
    probes={}
    for path in sorted(output.glob('*.mp4')):
        probe=json.loads(subprocess.run(['ffprobe','-v','error','-count_frames','-show_entries','stream=codec_type,codec_name,width,height,avg_frame_rate,nb_read_frames,duration','-of','json',str(path)],capture_output=True,check=True).stdout)
        video=next(s for s in probe['streams'] if s['codec_type']=='video')
        assert int(video['nb_read_frames'])==32 and video['avg_frame_rate']=='8/1' and float(video['duration'])==4.
        probes[path.name]=probe
    with Image.open(output/'alpha-geometry-comparison.gif') as gif:
        durations=[f.info['duration'] for f in ImageSequence.Iterator(gif)]
    assert len(durations)==32 and sum(durations)==4000
    assert sha(ROOT/'product/src/ai_ad_editor/render.py')==source_before
    save(output/'evidence.json',{'checked_at_utc':datetime.now(timezone.utc).isoformat(),'baseline_ref':BASELINE,'baseline_render_sha256':sha(baseline/'product/src/ai_ad_editor/render.py'),'current_render_sha256':source_before,'script_sha256':sha(Path(__file__)),
        'fixture':{'frames':32,'fps':8,'seconds':4,'canvas':[512,288]},'cli_calls':calls,'hidden_rgb_invariance':invariant,'white_on_white':white_checks,'visible_positive_controls':positive,'probes':probes,
        'gif':{'frames':32,'duration_ms':sum(durations),'durations_ms':durations},'file_sha256':{p.name:sha(p) for p in sorted(output.iterdir()) if p.is_file()},
        'new_model_inferences':0,'natural_media_published':False,'continuous_playback_reviewed':False,'audio_reviewed':False,'font_binary_distributed':False,'full_jianying_parity_accepted':False})
    print(json.dumps({'calls':len(calls),'hidden_rgb_invariance':invariant,'white_on_white':white_checks},ensure_ascii=False),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--work-dir',type=Path,required=True)
    parser.add_argument('--font-file',type=Path,required=True)
    parser.add_argument('--font-license-file',type=Path,required=True)
    parser.add_argument('--font-license-id',required=True)
    args=parser.parse_args()
    run(args.output_dir.resolve(),args.work_dir.resolve(),args.font_file.resolve(),args.font_license_file.resolve(),args.font_license_id)
