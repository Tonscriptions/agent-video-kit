"""Real local CLI text-color renders with opaque coverage controls and originals."""
from __future__ import annotations

import argparse, bisect, copy, hashlib, io, json, shutil, subprocess, sys, time, zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from smoke_speed_easing import integral, forward, inverse

BASELINE = 'da87598184b61310a7958a3d17fee4b210545f15'
W, H, FPS, TPS = 512, 288, 24, 90000
def sha(path): return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()
def save(path, value): path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8', newline='\n')
def frozen(): return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted([*(ROOT/'product/src').rglob('*.py'), *(ROOT/'product/tests').rglob('*.py'), ROOT/'docs/specs/agent-project.schema.json'])}


def run(output, work, font, license_file, cases=None):
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    if output.exists() or work.exists(): raise ValueError('Use fresh output/work paths; retain earlier evidence')
    for path in (font, license_file):
        if not path.is_file(): raise ValueError(f'Local font/license missing: {path}')
    output.mkdir(parents=True); work.mkdir(parents=True)
    started = datetime.now(timezone.utc).isoformat(); before_hashes = frozen()
    save(work/'started-source-freeze.json', before_hashes)
    archive = subprocess.run(['git', '-c', 'core.autocrlf=false', 'archive', '--format=zip', BASELINE,
        'product/src', 'docs/specs/agent-project.schema.json'], cwd=ROOT, capture_output=True, check=True).stdout
    baseline = work/'baseline'; baseline_hashes = {}
    with zipfile.ZipFile(io.BytesIO(archive)) as package:
        for item in package.infolist():
            if item.is_dir(): continue
            path = (baseline/item.filename).resolve(); assert path.is_relative_to(baseline.resolve())
            path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(package.read(item)); baseline_hashes[item.filename] = sha(path)
    for name in ('source.mp4', 'pulses.wav'): shutil.copyfile(ROOT/'docs/assets/subtitle-clock-20261016'/name, output/name)
    shutil.copyfile(license_file, output/'font-license.txt')
    provenance = {'media_license_spdx': 'CC0-1.0', 'original_generator': 'scripts/smoke_subtitle_clock.py',
        'original_generator_sha256': sha(ROOT/'scripts/smoke_subtitle_clock.py'),
        'inputs': {name: sha(output/name) for name in ('source.mp4', 'pulses.wav')},
        'font': {'family': ImageFont.truetype(str(font), 32).getname()[0], 'sha256': sha(font),
            'license_spdx': 'LicenseRef-DejaVu-Fonts', 'license_sha256': sha(license_file), 'binary_distributed': False},
        'third_party_natural_footage': False, 'new_model_inference': 0}
    save(output/'fixture-provenance.json', provenance)
    calls = []
    bootstrap = 'import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();from ai_ad_editor.cli import main;raise SystemExit(main())'
    def cli(*args, old=False):
        command = [sys.executable, '-I', '-B', '-X', 'utf8', '-c', bootstrap,
            str(baseline/'product/src' if old else ROOT/'product/src'), *map(str, args)]
        begin = time.monotonic(); result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=300)
        (work/f'call-{len(calls):03}.stdout.log').write_bytes(result.stdout)
        (work/f'call-{len(calls):03}.stderr.log').write_bytes(result.stderr)
        value = json.loads(result.stdout.decode('utf-8-sig'))
        calls.append({'args': list(map(str, args)), 'baseline': old, 'seconds': time.monotonic()-begin,
            'exit_code': result.returncode, 'result': value}); save(work/'partial-calls.json', calls)
        if result.returncode: raise RuntimeError(json.dumps(value, ensure_ascii=False)[:3000])
        return value
    def ff(args, data=None):
        result = subprocess.run(['ffmpeg', '-v', 'error', *map(str, args)], input=data, capture_output=True, timeout=300)
        if result.returncode: raise RuntimeError(result.stderr.decode('utf-8', 'replace'))
        return result.stdout
    def decode(path): return np.frombuffer(ff(['-i', path, '-map', '0:v:0', '-an', '-pix_fmt', 'rgb24', '-f', 'rawvideo', 'pipe:1']), np.uint8).reshape(-1, H, W, 3)
    def audio_hash(path): return 'sha256:' + hashlib.sha256(ff(['-i', path, '-map', '0:a:0', '-vn', '-acodec', 'pcm_f32le', '-f', 'f32le', 'pipe:1'])).hexdigest()
    scenarios = {
        'white-half': {'text': 'LOCAL HALF OPACITY', 'fill': [255,255,255,127], 'style': {'fontcolor': 'white@0.5'}},
        'rgb-half': {'text': 'COLOR 50%', 'fill': [64,128,192,127], 'style': {'fontcolor': '0x4080c0@0.5'}},
        'inline-quarter': {'text': 'INLINE 25%', 'fill': [255,128,32,63], 'independent': False, 'style': {'fontcolor': '0xff8020@0.25'}},
        'styled': {'text': 'STYLED TEXT', 'fill': [255,255,255,153], 'style': {'fontcolor': 'white@0.6',
            'box': True, 'boxcolor': '0x2040ff@0.35', 'box_padding': 10, 'borderw': 3, 'bordercolor': '0x20ff60@0.6',
            'shadowx': 8, 'shadowy': 7, 'shadowcolor': '0xff4020@0.5'},
            'components': [('boxcolor',[32,64,255,89]),('shadowcolor',[255,64,32,127]),('bordercolor',[32,255,96,153])]},
        'multiline': {'text': 'ALPHA 50%\nSECOND LINE', 'fill': [255,128,32,127], 'style': {'fontcolor': '0xff8020@0.5', 'y':'166', 'line_spacing': 8}},
        'fade': {'text': 'FADE 50%', 'fill': [255,255,255,127], 'style': {'fontcolor': 'white@0.5'}, 'animation': {'type':'fade_in','duration':2.4}},
        'layer-opacity': {'text': 'COLOR x LAYER', 'fill': [64,128,192,127], 'style': {'fontcolor':'0x4080c0@0.5'}, 'opacity': .5},
        'words': {'text': 'FEATURE BENEFIT', 'fill': [255,255,255,127], 'style': {'fontcolor':'white@0.5','active_color':'0x20ffff@0.25'},
            'active': [32,255,255,63], 'word_timing':[{'text':'FEATURE','start_char':0,'start':.15,'end':1.4},{'text':'BENEFIT','start_char':8,'start':1.4,'end':2.65}]},
        'nested-fade': {'text':'REVERSE FADE 50%', 'fill':[64,128,192,127], 'style': {'fontcolor':'0x4080c0@0.5'},
            'animation': {'type':'fade_in','duration':2.4}, 'nested': True},
    }
    if cases:
        selected = cases.split(','); assert set(selected) <= set(scenarios)
        scenarios = {name: scenarios[name] for name in selected}
    records = {}; preview = None
    for name, config in scenarios.items():
        project = work/name; cli('project','init',project)
        p = json.loads((project/'project.json').read_text(encoding='utf-8-sig'))
        p['settings']['canvas'].update(width=W,height=H); p['settings']['timebase']['display_fps']={'num':FPS,'den':1}
        p['sequences'][0]['duration_tick']=3*TPS; save(project/'project.json',p)
        for path, asset, label, evidence in [(output/'source.mp4','frames','CC0-1.0',output/'fixture-provenance.json'),
            (output/'pulses.wav','pulses','CC0-1.0',output/'fixture-provenance.json'),
            (font,'local_font','LicenseRef-DejaVu-Fonts',output/'font-license.txt')]:
            cli('media','ingest','--project',project,'--input',path,'--asset-id',asset,'--source-url','local://authored-text-paint',
                '--license-spdx',label,'--verification-status','verified','--permitted-use','commercial_ad','--evidence',evidence)
        subtitle={'text':config['text'],'style':{'font_asset_id':'local_font','fontsize':32,'x':'60','y':'212','box':False,'expansion':'none',**config['style']}}
        for key in ('animation','word_timing'):
            if key in config: subtitle[key]=copy.deepcopy(config[key])
        nested=config.get('nested',False); independent=config.get('independent',True)
        sequence='child' if nested else 'seq_main'; vt='child_video_1' if nested else 'track_video_1'; at='child_audio_1' if nested else 'track_audio_1'
        operations=[{'op':'add_sequence','id':'child','duration_tick':3*TPS}] if nested else []
        leaf={'op':'append_clip','sequence_id':sequence,'track_id':vt,'id':'leaf','asset_id':'frames','source_in_tick':0,'source_out_tick':3*TPS,'duration_tick':3*TPS}
        operations.append(leaf); target='leaf'
        if independent:
            target='title'; operations.extend([{'op':'add_track','sequence_id':sequence,'track_id':'titles','kind':'subtitle','order':2},
                {'op':'append_clip','sequence_id':sequence,'track_id':'titles','id':target,'generator':{'type':'text'},'source_in_tick':0,
                    'source_out_tick':3*TPS,'duration_tick':3*TPS,'subtitle':subtitle,'transform':{'opacity':config.get('opacity',1.)}}])
        else: leaf['subtitle']=subtitle
        operations.append({'op':'append_clip','sequence_id':sequence,'track_id':at,'id':'audio','asset_id':'pulses',
            'source_in_tick':0,'source_out_tick':3*TPS,'duration_tick':3*TPS})
        step=None
        if nested:
            pieces=[(0.,3.,.6,2.8,'bezier',(.15,.05,.85,.7))]; duration=round(integral(3.,pieces)*TPS)/TPS
            step={'in':0.,'out':3.,'start':0.,'duration':duration,'reverse':True,'pieces':pieces}
            operations.append({'op':'append_sequence_clip','track_id':'track_video_1','id':'container','nested_sequence_id':sequence,
                'source_in_tick':0,'source_out_tick':3*TPS,'duration_tick':round(duration*TPS),'reverse':True,
                'speed_curve':{'keyframes':[{'at_tick':0,'speed':.6,'interpolation':'bezier','control_points':[.15,.05,.85,.7]},
                    {'at_tick':3*TPS,'speed':2.8,'interpolation':'linear'}]}})
        change=work/f'{name}-changes.json'; save(change,{'operations':operations}); cli('timeline','compose','--project',project,'--input',change)
        if nested:
            p=json.loads((project/'project.json').read_text(encoding='utf-8-sig'));p['sequences'][0]['duration_tick']=round(step['duration']*TPS);save(project/'project.json',p)
        def authored_hash():
            p=json.loads((project/'project.json').read_text(encoding='utf-8-sig'))
            return 'sha256:'+hashlib.sha256(json.dumps({key:p[key] for key in ('assets','settings','sequences')},sort_keys=True).encode()).hexdigest()
        variants={}; images={}; unchanged=[]
        masks=[key for key,_ in config.get('components',[])] + ['fontcolor']
        for variant in ['before','after','blank',*masks]:
            if variant not in ('before','after'):
                control=copy.deepcopy(subtitle); control.pop('animation',None);control.pop('word_timing',None)
                for key in ('boxcolor','shadowcolor','bordercolor','fontcolor'):control['style'][key]='black@0'
                if variant!='blank':control['style'][variant]='white'
                patch={'subtitle':control}
                if independent:patch['transform']={'opacity':1.}
                change=work/f'{name}-{variant}.json';save(change,{'operations':[{'op':'update_clip','sequence_id':sequence,'clip_id':target,'patch':patch}]})
                cli('timeline','compose','--project',project,'--input',change)
            author,ledger=authored_hash(),sha(project/'rights-ledger.json');path=project/f'renders/{variant}.mp4'
            result=cli('render','--project',project,'--output',path,'--crf','0','--pixel-format','yuv444p','--publish',old=variant=='before')
            final=output/f'{variant}-{name}.mp4';shutil.copyfile(path,final);shutil.copyfile(Path(str(path)+'.manifest.json'),Path(str(final)+'.manifest.json'))
            assert author==authored_hash() and ledger==sha(project/'rights-ledger.json')
            unchanged.append({'variant':variant,'authored_sha256':author,'ledger_sha256':ledger,'unchanged':True})
            images[variant]=decode(final)
            probe=json.loads(subprocess.run(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(final)],capture_output=True,check=True).stdout)
            variants[variant]={'path':final.name,'sha256':sha(final),'manifest_sha256':sha(Path(str(final)+'.manifest.json')),
                'frames':len(images[variant]),'probe':probe,'audio_pcm_f32_sha256':audio_hash(final),'warnings':result['data'].get('warnings',[])}
            if variant=='after':
                quality=cli('quality','check','--project',project,'--input',path,'--require-audio','--expensive','--fail-on-black',
                    '--max-true-peak-dbfs','-1','--report',project/'validation/text-paint.json')['data']
        policy=cli('policy','audit','--project',project)['data']
        blank=images['blank'].astype(float)
        coverage={key:np.clip(np.mean((images[key].astype(float)-blank)/np.maximum(1,255-blank),axis=3),0,1) for key in masks}
        # Ignore encoded round-trip noise in regions in which every channel
        # of the opaque control is already within 3 of the blank control.
        for key in masks:coverage[key][np.max(np.abs(images[key].astype(float)-blank),axis=3)<=3]=0
        expected=np.empty_like(blank); rows=[]
        split=None
        if config.get('word_timing'):
            columns=np.flatnonzero((coverage['fontcolor'][0]>.7).any(axis=0));gaps=[];current=[]
            for x in range(columns[0],columns[-1]+1):
                if x not in columns:current.append(x)
                elif current:gaps.append(current);current=[]
            gap=max(gaps,key=len);split=gap[len(gap)//2]
        for i in range(len(blank)):
            author=inverse(step,i/FPS)-.5/TPS if step else i/FPS
            premultiplied=np.zeros((H,W,3));alpha=np.zeros((H,W))
            for key,color in [*config.get('components',[]),('fontcolor',config['fill'])]:
                rgb=np.broadcast_to(np.asarray(color[:3],float),(H,W,3)).copy();a=coverage[key][i]*(color[3]/255)
                if key=='fontcolor' and split is not None:
                    for word,entry in enumerate(config['word_timing']):
                        if entry['start']<=author<entry['end']:
                            region=slice(None,split) if word==0 else slice(split,None)
                            rgb[:,region]=config['active'][:3];a[:,region]=coverage[key][i,:,region]*config['active'][3]/255
                premultiplied=rgb*a[:,:,None]+premultiplied*(1-a[:,:,None]);alpha=a+alpha*(1-a)
            opacity=config.get('opacity',1.)
            if config.get('animation'):opacity*=min(1.,max(0.,author/config['animation']['duration']))
            expected[i]=premultiplied*opacity+blank[i]*(1-alpha[:,:,None]*opacity)
            row={'frame':i,'author_seconds':author,'opacity_multiplier':opacity}
            for variant in ('before','after'):
                delta=np.abs(images[variant][i].astype(float)-expected[i]);row[variant+'_max_rgb_error']=float(delta.max());row[variant+'_mean_rgb_error']=float(delta.mean())
            source=sum(1<<bit for bit in range(7) if images['after'][i,50,60+64*bit,0]>128)
            if step:
                candidates=sorted((forward(step,(j+1)/FPS),j) for j in range(72));pos=max(0,bisect.bisect_right([x[0] for x in candidates],i/FPS+2e-5)-1);wanted=candidates[pos][1]
            else:wanted=i
            row.update(source_frame=source,expected_source_frame=wanted,source_frame_error=abs(source-wanted));rows.append(row)
        before_error=max(row['before_max_rgb_error'] for row in rows);after_error=max(row['after_max_rgb_error'] for row in rows)
        audio_equal=len({v['audio_pcm_f32_sha256'] for v in variants.values()})==1
        records[name]={'config':config,'subtitle':subtitle,'operations':operations,'step':step,'variants':variants,'quality':quality,'policy':policy,
            'word_control_split_x':int(split) if split is not None else None,'rows':rows,'before_max_rgb_error':before_error,'after_max_rgb_error':after_error,
            'max_source_frame_error':max(row['source_frame_error'] for row in rows),'all_variant_audio_equal':audio_equal,'unchanged_after_renders':unchanged}
        save(work/'partial-records.json',records)
        if preview is None:preview=(images['before'].copy(),images['after'].copy(),np.rint(np.clip(expected,0,255)).astype(np.uint8))
        print(json.dumps({'case':name,'before_error':before_error,'after_error':after_error,'audio_equal':audio_equal,'frames':len(rows)}),flush=True)
        assert after_error<=6 and audio_equal and records[name]['max_source_frame_error']==0
    originals=decode(output/'source.mp4');small=ImageFont.truetype(str(font),18);strips=[]
    for i in range(len(preview[0])):
        image=Image.new('RGB',(W*4,H+44),(20,23,30));draw=ImageDraw.Draw(image)
        for column,(label,frame) in enumerate([('ORIGINAL INPUT',originals[i]),('ARCHIVED CLI',preview[0][i]),('CURRENT CLI',preview[1][i]),('COVERAGE / COLOR TRUTH',preview[2][i])]):
            image.paste(Image.fromarray(frame),(column*W,44));draw.text((column*W+12,12),label,font=small,fill='white')
        strips.append(image)
    ff(['-f','rawvideo','-pix_fmt','rgb24','-s',f'{W*4}x{H+44}','-r',FPS,'-i','pipe:0','-an','-c:v','libx264','-crf','16','-pix_fmt','yuv420p',output/'text-paint-comparison.mp4'],np.asarray([np.asarray(im) for im in strips],np.uint8).tobytes())
    durations=[round((i+1)*100/FPS)*10-round(i*100/FPS)*10 for i in range(len(strips))]
    gifs=[image.resize((1536,249)) for image in strips]
    gifs[0].save(output/'text-paint-comparison.gif',save_all=True,append_images=gifs[1:],duration=durations,loop=0,optimize=False,disposal=2)
    contact=Image.new('RGB',(W*4,(H+44)*3),(20,23,30))
    for row,index in enumerate((0,len(strips)//2,len(strips)-1)):contact.paste(strips[index],(0,row*(H+44)))
    contact.save(output/'contact-sheet.png')
    after_hashes=frozen();assert before_hashes==after_hashes
    media={p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(output.iterdir()) if p.is_file()}
    result={'started_at_utc':started,'finished_at_utc':datetime.now(timezone.utc).isoformat(),'baseline_ref':BASELINE,'baseline_source_sha256':baseline_hashes,
        'generator_sha256':sha(Path(__file__)),'clock_oracle_sha256':sha(ROOT/'scripts/smoke_speed_easing.py'),
        'frozen_before':before_hashes,'frozen_after':after_hashes,'provenance':provenance,'calls':calls,'records':records,'media':media,
        'gates':{'encoded_rgb_max_error':6,'source_frame_error':0,'audio_pcm_equal_across_variants':True},
        'preview':{'frames':len(strips),'fps':FPS,'mp4_seconds':len(strips)/FPS,'gif_durations_ms':durations,'gif_seconds':sum(durations)/1000,
            'audio':False,'manual_selected_frames':[0,len(strips)//2,len(strips)-1],'continuous_playback_reviewed':False,'audio_listened':False},
        'limits':['controlled encoded RGB 8-bit color/opacity, not linear-light/HDR', 'coverage derived from actual opaque CLI controls with encoded quantization allowance',
            'dynamic-raster inline color remains explicitly approximate','external ASS/libass colors not covered','word+animation joint behavior not accepted','general shaping/freezes/VFR/group spaces/natural quality not accepted'],
        'new_model_inference':0}
    save(output/'evidence.json',result)
    print(json.dumps({'cases':len(records),'cli_calls':len(calls),'renders':sum(c['args'][0]=='render' for c in calls),'files':len(media)+1}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);parser.add_argument('--work',required=True,type=Path)
    parser.add_argument('--font',required=True,type=Path);parser.add_argument('--font-license',required=True,type=Path);parser.add_argument('--cases')
    args=parser.parse_args();run(args.output.resolve(),args.work.resolve(),args.font.resolve(),args.font_license.resolve(),args.cases)
