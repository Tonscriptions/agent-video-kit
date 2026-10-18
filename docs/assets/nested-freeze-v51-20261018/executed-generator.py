"""Real CLI media, independent clocks/samples and portable compound holds."""
from __future__ import annotations
import argparse,copy,hashlib,json,math,os,shutil,subprocess,sys,time
from datetime import datetime,timezone
from fractions import Fraction
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from run_frozen_regression import frozen

TPS,FPS,W,H,SR=90000,10,240,136,48000
BASE='79deb231fe92f61ed4e7644b2ccd1361129ae2bd'


def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def digest(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()
def save(p,data):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


def run(output,work):
    import numpy as np
    from PIL import Image
    output.mkdir(parents=True,exist_ok=False);work.mkdir(parents=True,exist_ok=False)
    (output/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    before=frozen();calls=[];cases=[];graph_probes=[]
    env=dict(os.environ);env.update(TEMP=str(ROOT/'product/.runtime/temp'),TMP=str(ROOT/'product/.runtime/temp'),
        TMPDIR=str(ROOT/'product/.runtime/temp'),PYTHONDONTWRITEBYTECODE='1')
    bootstrap='import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();from ai_ad_editor.cli import main;raise SystemExit(main())'
    def cli(*args,expected=0,baseline=False):
        src=ROOT/('product/.runtime/nested-freeze-baseline-20261018/product/src' if baseline else 'product/src')
        command=[sys.executable,'-E','-B','-X','utf8','-c',bootstrap,str(src),*map(str,args)]
        start=time.monotonic();p=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,timeout=360)
        n=len(calls)+1
        for name,raw in [('stdout',p.stdout),('stderr',p.stderr)]:
            (work/f'{n:03}.{name}.log').write_bytes(raw)
        value=json.loads(p.stdout.decode('utf-8-sig')) if p.stdout.strip() else {'stderr':p.stderr.decode('utf-8','replace')}
        calls.append({'index':n,'args':list(map(str,args)),'baseline':baseline,'exit_code':p.returncode,
            'expected_exit_code':expected,'seconds':time.monotonic()-start,
            'stdout_sha256':digest(p.stdout),'stderr_sha256':digest(p.stderr)})
        save(work/'calls.json',calls)
        print(json.dumps({'call':n,'command':list(map(str,args[:2])),'code':p.returncode}),flush=True)
        assert p.returncode==expected,(n,value)
        return value
    def rgb(path,alpha=False):
        raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-map','0:v:0','-an','-pix_fmt','rgba' if alpha else 'rgb24','-f','rawvideo','pipe:1'])
        return np.frombuffer(raw,dtype='uint8').reshape(-1,H,W,4 if alpha else 3)
    def pcm(path):
        raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-map','0:a:0','-vn','-ar',str(SR),'-ac','2','-f','f32le','pipe:1'])
        return np.frombuffer(raw,dtype='<f4').reshape(-1,2)
    def held(values,at,count):
        return np.concatenate([values[:at],np.repeat(values[max(0,at-1):max(0,at-1)+1],count,axis=0),values[at:]])
    def silent(values,at,count,continue_audio=False):
        return np.concatenate([values,np.zeros((count,2))]) if continue_audio else np.concatenate([values[:at],np.zeros((count,2)),values[at:]])
    def encode(project,name,*,alpha=False,baseline=False,sequence_id=None):
        path=project/'renders'/(name+'.mkv')
        args=['render','--project',project,'--output',path,'--container','mkv','--audio-codec','pcm_f32le','--publish']
        args+=['--video-codec','ffv1','--pixel-format','yuva420p'] if alpha else ['--pixel-format','yuv444p','--crf','0']
        if sequence_id:args+=['--sequence-id',sequence_id]
        result=cli(*args,baseline=baseline)
        return path,result
    def graph_probe(project,name,*,sequence_id=None):
        # A precision reference, explicitly separate from supported CLI delivery
        # encoders. Avoid an extra RGB -> limited YUV -> RGB round trip in the
        # child oracle, and preserve alpha without a lossy delivery codec.
        sys.path.insert(0,str(ROOT/'product/src'))
        from ai_ad_editor.runtime import configure_local_runtime
        from ai_ad_editor.render import build_filter_graph
        configure_local_runtime()
        p=json.loads((project/'project.json').read_bytes())
        p['settings'].setdefault('output',{}).setdefault('video',{})['pixel_format']='yuva420p'
        sequence=next(s for s in p['sequences'] if s['id']==sequence_id) if sequence_id else p['sequences'][0]
        inputs,graph,metadata,warnings=build_filter_graph(project,p,sequence)
        path=project/'renders'/(name+'.nut');path.parent.mkdir(parents=True,exist_ok=True)
        graph_path=work/(name+'.ffgraph');graph_path.write_text(graph,encoding='utf-8')
        command=['ffmpeg','-v','error','-y',*inputs,'-filter_complex_script',str(graph_path),
            '-map','[vout]','-map','[aout]','-c:v','ffv1','-pix_fmt','bgra','-c:a','pcm_f32le',str(path)]
        done=subprocess.run(command,cwd=project,env=env,capture_output=True,timeout=120)
        (work/(name+'.stderr.log')).write_bytes(done.stderr)
        assert done.returncode==0,done.stderr.decode('utf-8','replace')
        manifest=work/(name+'.graph.json');save(manifest,{'inputs':inputs,'graph':graph,'metadata':metadata,'warnings':warnings,
            'execution':'native graph precision probe; not a supported CLI delivery codec'})
        graph_probes.append({'name':name,'manifest_sha256':sha(manifest),'command':command,'exit_code':done.returncode})
        return path,{'data':{'manifest':str(manifest)}}
    def verify(path,project,result,expected_rgb,expected_pcm,*,name,alpha=False,scope='independent-source-frame-and-sample-list',audio_content=True):
        actual=rgb(path,alpha);audio=pcm(path)
        assert actual.shape==expected_rgb.shape,(name,actual.shape,expected_rgb.shape)
        delta=np.abs(actual.astype(float)-expected_rgb.astype(float))
        alpha_equal=None
        if alpha:
            alpha_equal=bool(np.array_equal(actual[:,:,:,3],expected_rgb[:,:,:,3]));assert alpha_equal
            # RGB under zero alpha has no visible meaning; YUV 4:2:0 chroma
            # reconstruction is not an independent RGB acceptance claim here.
            rgb_error=None
        else:
            rgb_error=float(delta.max());assert rgb_error<=3,(name,rgb_error)
        assert audio.shape==expected_pcm.shape,(name,audio.shape,expected_pcm.shape)
        assert np.isfinite(audio).all()
        pcm_error=float(np.max(np.abs(audio-expected_pcm))) if audio_content else None
        if audio_content:assert pcm_error<=2e-6,(name,pcm_error)
        manifest=json.loads(Path(result['data']['manifest']).read_bytes())
        author=json.loads((project/'project.json').read_bytes())
        assert not any(a['id'].startswith('__freeze_') for a in author['assets'])
        assert not any(s['id'].startswith('__freeze_') for s in author['sequences'])
        probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_frames','-show_entries','frame=best_effort_timestamp_time','-of','json',str(path)]))
        pts=[float(v['best_effort_timestamp_time']) for v in probe['frames']]
        assert len(pts)==len(actual)
        pts_error=max(abs(t-i/FPS) for i,t in enumerate(pts));assert pts_error<=.000501
        saved=output/(name+path.suffix);shutil.copyfile(path,saved)
        if not alpha:
            subprocess.run(['ffmpeg','-v','error','-y','-i',str(path),'-c:v','libx264','-crf','16','-pix_fmt','yuv420p','-c:a','aac',str(output/(name+'.mp4'))],check=True,capture_output=True)
            images=[Image.fromarray(frame).resize((W*2,H*2),Image.Resampling.NEAREST) for frame in actual]
            images[0].save(output/(name+'.gif'),save_all=True,append_images=images[1:],duration=100,loop=0,disposal=2)
            for k in (0,len(actual)//2,len(actual)-1):Image.fromarray(actual[k]).save(output/f'{name}-frame-{k:03}.png')
        record={'name':name,'scope':scope,'frames':len(actual),'stereo_sample_frames':len(audio),'max_rgb_error':rgb_error,
            'alpha_equal':alpha_equal,'max_pcm_error':pcm_error,'audio_content_accepted':audio_content,
            'all_pts_checked':True,'max_pts_error_seconds':pts_error,'rgb_sha256':digest(actual.tobytes()),
            'pcm_sha256':digest(audio.tobytes()),'manifest_sha256':sha(Path(result['data']['manifest'])),
            'author_no_runtime_ids':True,'new_model_forwards':0}
        save(output/(name+'-verification.json'),record);cases.append(record)
        shutil.copyfile(Path(result['data']['manifest']),work/(name+'-manifest.json'))
        return actual,audio
    try:
        old=ROOT/'docs/assets/source-transitions-20261017'
        original=json.loads((old/'verification.json').read_bytes())
        for sid in ('a','b'):
            for filename in (f'source-{sid}.mp4',f'sound-{sid}.wav'):
                assert sha(old/filename)==original['files'][filename]['sha256']
                shutil.copyfile(old/filename,output/filename)
        font=ROOT/'docs/assets/boundary-readable-font-20261018/DejaVuSans.ttf'
        license_path=ROOT/'docs/assets/boundary-readable-font-20261018/LICENSE_DEJAVU'
        shutil.copyfile(font,output/'DejaVuSans.ttf');shutil.copyfile(license_path,output/'LICENSE_DEJAVU')
        provenance={'source':'byte-verified existing self-authored CC0 moving counters/boxes and synthetic stereo tones',
            'original':'docs/assets/source-transitions-20261017/fixture-provenance.json','original_sha256':sha(old/'fixture-provenance.json'),
            'font':'unmodified DejaVu Sans, existing locally, original Bitstream Vera / DejaVu notices included',
            'font_source':'docs/assets/boundary-readable-font-20261018/source.json','font_sha256':sha(font),
            'generator_sha256':sha(Path(__file__)),'baseline_commit':BASE,'models':0,'browser_invocations':0}
        save(output/'fixture-provenance.json',provenance)
        base=work/'base-project';cli('project','init',base)
        for sid in ('a','b'):
            for kind,filename in (('video',f'source-{sid}.mp4'),('audio',f'sound-{sid}.wav')):
                cli('media','ingest','--project',base,'--input',output/filename,'--asset-id',kind+'_'+sid,
                    '--verification-status','verified','--permitted-use','commercial_ad','--license-spdx','CC0-1.0',
                    '--creator','project procedural fixture authors','--source','self-authored-procedural-fixture','--evidence',output/'fixture-provenance.json')
        cli('media','ingest','--project',base,'--input',output/'DejaVuSans.ttf','--asset-id','font',
            '--verification-status','verified','--permitted-use','commercial_ad','--license-spdx','Bitstream-Vera',
            '--creator','DejaVu and Bitstream font authors','--source','existing unmodified DejaVu Sans', '--evidence',output/'LICENSE_DEJAVU')
        author=json.loads((base/'project.json').read_bytes());main=author['sequences'][0]['id']
        author['settings']['canvas'].update(width=W,height=H);author['settings']['timebase']['display_fps']={'num':FPS,'den':1}
        source_rgb={sid:rgb(output/f'source-{sid}.mp4') for sid in ('a','b')}
        source_pcm={sid:pcm(output/f'sound-{sid}.wav') for sid in ('a','b')}
        def make(name,*,at=TPS,duration=4*TPS,source_in=0,source_out=3*TPS,reverse=False,curve=None,caption=False):
            project=work/name;shutil.copytree(base,project)
            p=copy.deepcopy(author)
            child={'id':'child','name':'authored child','canvas':{'width':W,'height':H},'duration_tick':3*TPS,'tracks':[]}
            for kind in ('video','audio'):
                child['tracks'].append({'id':kind+'_track','kind':kind,'order':0,'clips':[
                    {'id':kind+'_leaf','asset_id':kind+'_a','timeline_start_tick':0,'duration_tick':3*TPS,
                     'source_in_tick':TPS,'source_out_tick':4*TPS}]})
            container={'id':'container','sequence_id':'child','timeline_start_tick':0,'duration_tick':duration,
                'source_in_tick':source_in,'source_out_tick':source_out,'reverse':reverse,
                'freeze':{'at_tick':at,'duration_tick':TPS,'audio_mode':'silence'}}
            if curve:container['speed_curve']=curve
            parent={'id':main,'name':name,'duration_tick':duration,'tracks':[
                {'id':'parent','kind':'video','order':0,'clips':[container]}]}
            p['sequences']=[parent,child]
            save(project/'project.json',p)
            return project,p,parent,child,container
        # NF01 applies the existing public CLI edit, including dry-run and replay.
        project,p,parent,child,c=make('NF01')
        c.pop('freeze');c['duration_tick']=3*TPS;parent['duration_tick']=3*TPS;save(project/'project.json',p)
        req=work/'freeze-request.json';save(req,{'operations':[{'op':'freeze_frame','clip_id':'container',
            'at_tick':TPS,'duration_tick':TPS,'audio_mode':'silence'}]})
        bytes_before=(project/'project.json').read_bytes();cli('timeline','compose','--project',project,'--input',req,'--dry-run')
        assert bytes_before==(project/'project.json').read_bytes()
        applied=cli('timeline','compose','--project',project,'--input',req,'--idempotency-key','nf01-freeze')
        bytes_after=(project/'project.json').read_bytes();replay=cli('timeline','compose','--project',project,'--input',req,'--idempotency-key','nf01-freeze')
        assert applied['operation_id']==replay['operation_id'] and bytes_after==(project/'project.json').read_bytes()
        cli('validate','--project',project,'--strict-rights');cli('policy','audit','--project',project)
        path,result=encode(project,'NF01')
        expected=held(source_rgb['a'][10:40],10,10)
        expected_audio=silent(source_pcm['a'][SR:4*SR],SR,SR)
        verify(path,project,result,expected,expected_audio,name='NF01')
        # NF02 reverses a selected child interval before the hold.
        project,p,_,_,_=make('NF02',source_in=TPS//2,source_out=5*TPS//2,duration=3*TPS,at=TPS//2,reverse=True)
        path,result=encode(project,'NF02')
        verify(path,project,result,held(source_rgb['a'][15:35][::-1],5,10),
            silent(source_pcm['a'][int(1.5*SR):int(3.5*SR)][::-1],SR//2,SR),name='NF02')
        # NF03 uses an independently integrated smooth ramp, not product maps.
        content=round(1.5*math.log(3)*TPS)
        curve={'keyframes':[{'at_tick':0,'speed':1,'interpolation':'linear'},{'at_tick':3*TPS,'speed':3,'interpolation':'linear'}]}
        project,p,_,_,_=make('NF03',duration=content+TPS,at=7*TPS//10,curve=curve)
        count=math.ceil(Fraction(content,TPS)*FPS)
        indexes=np.floor(1.5*np.expm1(np.arange(count)/FPS/1.5)*FPS+1e-8).astype(int).clip(0,29)
        path,result=encode(project,'NF03')
        verify(path,project,result,held(source_rgb['a'][10+indexes],7,10),
            np.zeros((math.ceil(Fraction((content+TPS)*SR,TPS)),2)),name='NF03',audio_content=False,
            scope='independent-inverse-integral-frame-clock; audio-length-and-finite-only')
        # NF04's source-handle dissolve is composed before freezing its midpoint.
        project,p,parent,child,c=make('NF04',duration=5*TPS,at=2*TPS,source_out=4*TPS)
        child['duration_tick']=4*TPS
        for track in child['tracks']:
            kind=track['kind'];track['clips']=[]
            for i,sid in enumerate(('a','b')):
                track['clips'].append({'id':kind+'_'+sid+'_clip','asset_id':kind+'_'+sid,'link_id':'group_'+sid,
                    'timeline_start_tick':i*2*TPS,'duration_tick':2*TPS,'source_in_tick':2*TPS,'source_out_tick':4*TPS})
        save(project/'project.json',p)
        req=work/'transition-request.json';save(req,{'action':'add','id':'source_transition',
            'from_clip_id':'video_a_clip','to_clip_id':'video_b_clip','duration_tick':TPS,'type':'dissolve','audio':'linked'})
        cli('timeline','transition','--project',project,'--sequence-id','child','--input',req)
        reference=np.concatenate([source_rgb['a'][20:40],source_rgb['b'][20:40]]).astype(float)
        reference_audio=np.concatenate([source_pcm['a'][2*SR:4*SR],source_pcm['b'][2*SR:4*SR]]).astype(float)
        for k in range(15,25):reference[k]=(1-(k-15)/10)*source_rgb['a'][20+k]+((k-15)/10)*source_rgb['b'][k]
        n=np.arange(SR);w=n/SR
        reference_audio[int(1.5*SR):int(2.5*SR)]=(1-w[:,None])*source_pcm['a'][int(3.5*SR):int(4.5*SR)]+w[:,None]*source_pcm['b'][int(1.5*SR):int(2.5*SR)]
        path,result=encode(project,'NF04')
        verify(path,project,result,held(reference,20,10),silent(reference_audio,2*SR,SR),name='NF04')
        # NF05: a complete first hold is paused again by the outer container.
        project,p,parent,child,c=make('NF05');parent['id']='middle'
        p['sequences'].insert(0,{'id':main,'name':'double hold','duration_tick':5*TPS,'tracks':[
            {'id':'outer','kind':'video','order':0,'clips':[{'id':'outer_container','sequence_id':'middle',
             'timeline_start_tick':0,'duration_tick':5*TPS,'source_in_tick':0,'source_out_tick':4*TPS,
             'freeze':{'at_tick':int(2.5*TPS),'duration_tick':TPS,'audio_mode':'silence'}}]}]})
        save(project/'project.json',p);path,result=encode(project,'NF05')
        verify(path,project,result,held(expected,25,10),silent(expected_audio,int(2.5*SR),SR),name='NF05')
        # NF06 checks complete animated captions with a separately evaluated
        # parent opacity clock; glyph layout itself uses a same-renderer reference.
        project,p,parent,child,c=make('NF06')
        child['tracks'][0]['clips'][0]['keyframes']=[{'property':'transform.position.x','keyframes':[
            {'at_tick':0,'value':.5,'interpolation':'linear'},{'at_tick':3*TPS,'value':.65,'interpolation':'linear'}]}]
        child['tracks'].append({'id':'captions','kind':'subtitle','order':2,'clips':[{'id':'caption',
            'generator':{'type':'text'},'timeline_start_tick':0,'duration_tick':3*TPS,'source_in_tick':0,'source_out_tick':3*TPS,
            'subtitle':{'text':'LOCAL CUT','style':{'font_asset_id':'font','fontsize':18,'x':'12','y':'12','box':False,
                                                 'fontcolor':'white','active_color':'yellow'},
                        'word_timing':[{'text':'LOCAL','start':0,'end':1.5},{'text':'CUT','start':1.5,'end':3}]}}]})
        c['keyframes']=[{'property':'transform.opacity','keyframes':[
            {'at_tick':0,'value':.35,'interpolation':'linear'},{'at_tick':4*TPS,'value':1,'interpolation':'linear'}]}]
        save(project/'project.json',p)
        child_path,child_result=encode(project,'NF06-child',sequence_id='child')
        shutil.copyfile(child_path,output/'NF06-child.mkv')
        child_raw,_=graph_probe(project,'NF06-child-precision',sequence_id='child')
        shutil.copyfile(child_raw,output/'NF06-child-precision.nut')
        child_picture=held(rgb(child_raw,True),10,10)
        gain=(.35+np.arange(40)/FPS*.65/4)[:,None,None]
        reference=child_picture[:,:,:,:3].astype(float)*(np.floor(child_picture[:,:,:,3]*gain)/255)[:,:,:,None]
        path,result=encode(project,'NF06')
        verify(path,project,result,reference,expected_audio,name='NF06',scope='same-renderer-lossless-RGBA-child; independent-hold-index-and-8-bit-parent-opacity-clock')
        # NF07 publishes a procedural soft-alpha source and checks every output alpha.
        values=np.zeros((30,H,W,4),dtype='uint8');values[:,:,:,:3]=source_rgb['a'][10:40]
        values[:,:,:,3]=np.array([0,64,128,255],dtype='uint8')[np.arange(W)//(W//4)][None,None,:]
        alpha_source=output/'source-alpha.mkv'
        subprocess.run(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgba','-s',f'{W}x{H}','-r',str(FPS),
            '-i','pipe:0','-an','-c:v','ffv1','-pix_fmt','bgra',str(alpha_source)],input=values.tobytes(),check=True,capture_output=True)
        project,p,parent,child,c=make('NF07')
        cli('media','ingest','--project',project,'--input',alpha_source,'--asset-id','alpha',
            '--verification-status','verified','--permitted-use','commercial_ad','--license-spdx','CC0-1.0',
            '--creator','project procedural fixture authors','--source','self-authored alpha stripes over own CC0 video','--evidence',output/'fixture-provenance.json')
        current=json.loads((project/'project.json').read_bytes());p['assets']=current['assets']
        child['tracks'][0]['clips'][0].update(asset_id='alpha',source_in_tick=0,source_out_tick=3*TPS)
        p['settings'].setdefault('output',{}).setdefault('video',{})['pixel_format']='yuva420p';save(project/'project.json',p)
        path,result=graph_probe(project,'NF07')
        verify(path,project,result,held(values,10,10),expected_audio,name='NF07',alpha=True,scope='native-graph-lossless-precision-probe; independent-all-alpha-pixels; rgb-color-under-alpha-not-accepted')
        webm=project/'renders/NF07.webm'
        cli('render','--project',project,'--output',webm,'--container','webm','--video-codec','libvpx-vp9',
            '--audio-codec','libopus','--pixel-format','yuva420p','--crf','0','--publish')
        webm_rgba=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-c:v','libvpx-vp9','-i',str(webm),
            '-an','-pix_fmt','rgba','-f','rawvideo','pipe:1']),dtype='uint8').reshape(-1,H,W,4)
        alpha_expected=held(values,10,10)[:,:,:,3]
        alpha_delta=np.abs(webm_rgba[:,:,:,3].astype(int)-alpha_expected.astype(int))
        alpha_exact=bool(np.array_equal(webm_rgba[:,:,:,3],alpha_expected))
        shutil.copyfile(webm,output/'NF07.webm')
        delivery={'status':'passed' if alpha_exact else 'failed_exact_alpha_gate','frames':len(webm_rgba),
            'all_alpha_pixels_equal':alpha_exact,'max_alpha_error':int(alpha_delta.max()),
            'mismatched_alpha_pixels':int(np.count_nonzero(alpha_delta)),'threshold_unchanged':0,
            'decoder':'explicit native libvpx-vp9; default FFmpeg VP9 decoder does not expose alpha',
            'opus_samples_accepted':False,'rgb_color_accepted':False,'webm_sha256':sha(webm)}
        save(output/'NF07-delivery-verification.json',delivery)
        # NF08 exercises output-window edits inside the hold and after resuming.
        project,p,_,_,_=make('NF08')
        req=work/'trim-request.json';save(req,{'operations':[{'op':'trim_clip','clip_id':'container',
            'start_tick':int(1.5*TPS),'end_tick':int(3.5*TPS),'timeline_start_tick':0}]})
        cli('timeline','compose','--project',project,'--input',req)
        current=json.loads((project/'project.json').read_bytes());current['sequences'][0]['duration_tick']=2*TPS;save(project/'project.json',current)
        path,result=encode(project,'NF08')
        verify(path,project,result,expected[15:35],expected_audio[int(1.5*SR):int(3.5*SR)],name='NF08')
        # NF09 is a no-freeze same-source compatibility control against V50.
        project,p,parent,child,c=make('NF09');c.pop('freeze');c['duration_tick']=3*TPS;parent['duration_tick']=3*TPS
        save(project/'project.json',p)
        path,result=encode(project,'NF09')
        actual,audio=verify(path,project,result,source_rgb['a'][10:40],source_pcm['a'][SR:4*SR],name='NF09')
        baseline_path,_=encode(project,'NF09-baseline',baseline=True)
        assert np.array_equal(actual,rgb(baseline_path)) and np.array_equal(audio,pcm(baseline_path))
        shutil.copyfile(baseline_path,output/'NF09-baseline.mkv')
        # A package restores the authored frozen graph, not private runtime IDs.
        chosen=work/'NF06';archive=output/'NF06-project.zip'
        cli('convert','export','--project',chosen,'--target-format','package','--output',archive)
        restored=work/'restored';cli('convert','import','--input',archive,'--output',restored)
        restored_path,restored_result=encode(restored,'restored')
        assert np.array_equal(rgb(restored_path),rgb(output/'NF06.mkv'))
        assert np.array_equal(pcm(restored_path),pcm(output/'NF06.mkv'))
        cli('validate','--project',restored,'--strict-rights');cli('policy','audit','--project',restored)
        after=frozen();assert before==after
        record={'status':'core_passed_delivery_alpha_failed' if not alpha_exact else 'passed','at_utc':datetime.now(timezone.utc).isoformat(),'cases':cases,
            'delivery_alpha':delivery,'all_delivery_gates_passed':alpha_exact,
            'cli_calls':len(calls),'calls':calls,'native_graph_probes':graph_probes,'frozen_before':before,'frozen_after':after,'frozen_equal':True,
            'baseline_commit':BASE,'no_freeze_control_rgb_pcm_equal':True,'package_restored_rgb_pcm_equal':True,
            'final_main_frames':sum(c['frames'] for c in cases),'final_stereo_sample_frames':sum(c['stereo_sample_frames'] for c in cases),
            'glyph_reference':'same-renderer child; other numeric clocks/alpha/source windows independent',
            'continuous_playback_review':False,'listening_review':False,'static_review':False,
            'new_model_forwards':0,'browser_invocations':0,'virtualization':False,
            'generator_sha256':sha(Path(__file__)),
            'files':{p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(output.iterdir()) if p.is_file()}}
        save(output/'verification.json',record);save(work/'verification.json',record)
        print(json.dumps({'status':record['status'],'cases':len(cases),'cli_calls':len(calls),
            'frames':record['final_main_frames'],'sample_frames':record['final_stereo_sample_frames']}))
    except BaseException as exc:
        save(work/'failure.json',{'error':repr(exc),'calls':calls,'frozen_before':before,'frozen_after':frozen(),'partials_preserved':True,
            'generator_sha256':sha(Path(__file__))});raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--work',type=Path,required=True)
    a=p.parse_args();run(a.output.resolve(),a.work.resolve())
