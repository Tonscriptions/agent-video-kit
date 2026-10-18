"""Real all-frame font/layout failures, strict gates and portable rebuilds."""
from __future__ import annotations
import argparse,contextlib,copy,io,json,shutil,subprocess,time
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'product/src'))
from ai_ad_editor.cli import main
from ai_ad_editor.project import load_project,save_project
from ai_ad_editor.media import ffmpeg_path,ffprobe_path
from ai_ad_editor.runtime import configure_local_runtime
from smoke_fragments import frozen,save,sha

W,H,N,FPS=384,216,12,6


def complete_font(source,dest):
    from fontTools.ttLib import TTFont
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    font=TTFont(source);pen=TTGlyphPen(None)
    rows=['01110','10001','10001','10001','10001','10001','01110']
    for y,line in enumerate(rows):
        for x,bit in enumerate(line):
            if bit=='1':
                left,bottom=40+x*100,(6-y)*100
                pen.moveTo((left,bottom));pen.lineTo((left+90,bottom));pen.lineTo((left+90,bottom+90));pen.lineTo((left,bottom+90));pen.closePath()
    font.setGlyphOrder([*font.getGlyphOrder(),'O']);font['glyf']['O']=pen.glyph();font['hmtx'].metrics['O']=(600,0)
    for table in font['cmap'].tables:
        if table.isUnicode():table.cmap[ord('O')]='O'
    for name,value in [(1,'Agent Grid CC0 Layout'),(4,'Agent Grid CC0 Layout Regular'),(6,'AgentGridCC0Layout-Regular')]:
        font['name'].setName(value,name,3,1,0x409)
    font['head'].created=font['head'].modified=2082844800;font.recalcTimestamp=False;font.save(dest)


def run(work,public,evidence,runtime):
    import numpy as np
    from PIL import Image
    from fontTools.ttLib import TTFont
    for path in (work,public,evidence):path.mkdir(parents=True,exist_ok=False)
    configure_local_runtime();before=frozen();calls=[];reports=[];rendered={};quality=[]
    save(evidence/'state.json',{'status':'started','frozen_before':before})
    def cli(*args,expected=0):
        out,err=io.StringIO(),io.StringIO();started=time.monotonic()
        with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
            try:code=main(list(map(str,args)))
            except SystemExit as exc:code=exc.code
        result=json.loads(out.getvalue()) if out.getvalue().strip() else {'argument_parser_exit':code}
        row={'number':len(calls)+1,'args':list(map(str,args)),'exit_code':code,'stdout':result,'stderr':err.getvalue(),'seconds':time.monotonic()-started}
        calls.append(row);save(evidence/'cli'/f'{len(calls):03}.json',row);assert code==expected,(len(calls),result)
        return result
    def browser(path,label):
        value=json.loads(Path(path).read_text(encoding='utf-8'))
        assert value['cleanup']['all_children_reaped'] and not value['cleanup']['active_after_cleanup']
        assert value['worker']['cleanup']['browser_closed'] and not value['worker']['cleanup']['denied_requests']
        save(evidence/(label+'.json'),value);reports.append({'label':label,'cleanup':value['cleanup'],'worker':value['worker']['cleanup']})
        return value
    def q(source,label,expected):
        state=(project/'project.json').read_bytes();ledger=(project/'rights-ledger.json').read_bytes()
        value=cli('motion','html-quality','--project',project,'--source-asset-id',source,expected=expected)
        assert state==(project/'project.json').read_bytes() and ledger==(project/'rights-ledger.json').read_bytes()
        report=browser(value['data']['report'] if expected==0 else value['errors'][0]['path'],label);quality.append(report)
        assert report['validation_complete'] and report['all_frame_orders_equal'] and report['frame_count']==N
        return report
    def ff(args,data=None):
        result=subprocess.run([ffmpeg_path(),'-hide_banner','-v','error','-y',*map(str,args)],input=data,capture_output=True)
        assert result.returncode==0,result.stderr.decode(errors='replace');return result.stdout
    def pixels(path):return np.frombuffer(ff(['-i',path,'-an','-f','rawvideo','-pix_fmt','rgba','-threads','1','pipe:1']),np.uint8).reshape(N,H,W,4)
    def render(source,asset,label,*,strict=False,from_asset=False,root=None,publish=True):
        root=root or project
        result=cli('motion','html-render','--project',root,'--from-asset-id' if from_asset else '--source-asset-id',source,'--asset-id',asset,*(['--layout-check','strict'] if strict else []))
        browser(result['data']['report'],label+'-render')
        if result['data']['layout_report']:quality.append(browser(result['data']['layout_report'],label+'-gate'))
        original=root/result['data']['asset']['uri'];array=pixels(original);rendered[label]={'frames':N,'rgba_sha256':'sha256:'+__import__('hashlib').sha256(array.tobytes()).hexdigest()}
        if publish:
            shutil.copyfile(original,public/(label+'-alpha.nut'))
            ff(['-i',original,'-an','-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-threads','1','-movflags','+faststart',public/(label+'.mp4')])
        return result,array
    legacy=ROOT/'docs/assets/html-template-20261018/template'
    assets=public/'inputs';assets.mkdir();shutil.copyfile(legacy/'font.ttf',assets/'legacy-font.ttf');complete_font(legacy/'font.ttf',assets/'complete-font.ttf')
    save(public/'provenance.json',{'source':'V45 original CC0 procedural HTML/product art; added original O drawing in complete_font',
        'license_spdx':'CC0-1.0','generator_sha256':sha(Path(__file__)),'width':W,'height':H,'fps':FPS,'frames':N,'seconds':2,
        'audio_streams':0,'model_inference_calls':0,'legacy_system_fallback_pixels_published':False,
        'scope':'license describes authored inputs and public geometry demos; system fallback diagnosis is metadata only'})
    project=work/'main';cli('project','init',project)
    p=load_project(project)[1];p['settings']['canvas'].update(width=W,height=H);p['settings']['timebase']['display_fps']={'num':FPS,'den':1};save_project(project,p)
    cli('motion','html-register','--project',project,'--input',runtime)
    for aid,path in [('font-legacy',assets/'legacy-font.ttf'),('font-complete',assets/'complete-font.ttf'),('product-original',legacy/'original-product.png')]:
        cli('media','ingest','--project',project,'--input',path,'--asset-id',aid,'--license-spdx','CC0-1.0','--verification-status','verified','--permitted-use','commercial_ad','--evidence',public/'provenance.json')
    for name in ('legacy','fixed','outside','clip'):
        folder=public/name;shutil.copytree(legacy,folder)
        if name!='legacy':shutil.copyfile(assets/'complete-font.ttf',folder/'font.ttf')
        spec=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
        spec['resources'][0]['asset_id']='font-legacy' if name=='legacy' else 'font-complete'
        if name=='outside':
            with (folder/'scene.mjs').open('a',encoding='utf-8',newline='\n') as stream:stream.write('\nconst draw=window.film.frame;window.film.frame=(t,p)=>{draw(t,p);title.style.left=(t<1.5?24:384)+"px"};\n')
        if name=='clip':
            page=(folder/'index.html').read_text(encoding='utf-8').replace('<p id="cta">CTA</p>','<div id="cta-wrap"><p id="cta">CTA</p></div>')
            (folder/'index.html').write_text(page,encoding='utf-8',newline='\n')
            with (folder/'style.css').open('a',encoding='utf-8',newline='\n') as stream:stream.write('\n#cta-wrap{position:absolute;left:24px;top:142px;width:15px;height:40px;overflow-x:clip;overflow-y:visible}#cta{left:0;top:0}\n')
        save(folder/'manifest.json',spec)
        cli('motion','html-source','--project',project,'--input',folder/'manifest.json','--asset-id','source-'+name,'--license-spdx','CC0-1.0')
    legacy_report=q('source-legacy','legacy-font-quality',2)
    missing=[x for x in legacy_report['issues'] if x['code']=='FONT_GLYPH_MISSING']
    assert {x['frame'] for x in missing}==set(range(6)) and all(x['codepoints']==['U+004F'] for x in missing)
    good=q('source-fixed','fixed-quality',0)
    outside=q('source-outside','outside-quality',2)
    assert {x['frame'] for x in outside['issues'] if x['code']=='TEXT_OUTSIDE_FRAME'}=={9,10,11}
    assert all(not any(x['sel']=='#title' for x in outside['frames'][i]['layout']['upstream_partial_clipping']) for i in (9,10,11))
    clipped=q('source-clip','clip-quality',2)
    assert {x['frame'] for x in clipped['issues']}==set(range(N))
    assert all(x['axes']==['x'] for x in clipped['issues'])
    old_map=TTFont(assets/'legacy-font.ttf').getBestCmap();new_map=TTFont(assets/'complete-font.ttf').getBestCmap()
    assert ord('O') not in old_map and ord('O') in new_map
    reference_checks=0
    for frame in good['frames']:
        for row in frame['layout']['rows']:
            for char in row['painted_text']:
                if not char.isspace():assert ord(char) in new_map;reference_checks+=1
    _,bad_out=render('source-outside','outside-output','outside')
    _,bad_clip=render('source-clip','clip-output','clip')
    fixed,fixed_pixels=render('source-fixed','fixed-output','fixed',strict=True)
    rebuilt,rebuild_pixels=render('fixed-output','rebuilt-output','rebuilt',from_asset=True,publish=False)
    assert np.array_equal(fixed_pixels,rebuild_pixels) and rebuilt['data']['asset']['html_motion']['layout_check']=='strict'
    for name in ('legacy','outside'):
        state=(project/'project.json').read_bytes();ledger=(project/'rights-ledger.json').read_bytes();nuts=sorted((project/'assets/html-motion').glob('*.nut'))
        result=cli('motion','html-render','--project',project,'--source-asset-id','source-'+name,'--asset-id','blocked-'+name,'--layout-check','strict',expected=2)
        quality.append(browser(result['errors'][0]['path'],'blocked-'+name+'-gate'))
        assert state==(project/'project.json').read_bytes() and ledger==(project/'rights-ledger.json').read_bytes() and nuts==sorted((project/'assets/html-motion').glob('*.nut'))
    archive=work/'project.zip';cli('convert','export','--project',project,'--target-format','package','--output',archive)
    imported=work/'imported';cli('convert','import','--input',archive,'--output',imported)
    cli('motion','html-register','--project',imported,'--input',runtime)
    restored,package_pixels=render('fixed-output','package-output','package',from_asset=True,root=imported,publish=False)
    assert np.array_equal(fixed_pixels,package_pixels) and restored['data']['asset']['html_motion']['layout_check']=='strict'
    cli('motion','html-quality','--project',project,'--source-asset-id','source-fixed','--dry-run')
    cli('policy','audit','--project',project)
    rights=cli('rights','check','--project',project,expected=7)
    comparison=np.concatenate((bad_out,bad_clip,fixed_pixels),axis=2)
    frames=[Image.fromarray(a[:,:,:3]).resize((768,144),Image.Resampling.LANCZOS) for a in comparison]
    frames[0].save(public/'comparison.gif',save_all=True,append_images=frames[1:],loop=0,duration=[170,160,170]*4,disposal=2)
    contact=Image.new('RGB',(W*3,H*3))
    for row,index in enumerate((0,8,11)):contact.paste(Image.fromarray(comparison[index,:,:,:3]),(0,row*H))
    contact.save(public/'contact.png')
    ff(['-f','rawvideo','-pix_fmt','rgb24','-s',f'{W*3}x{H}','-r',FPS,'-i','pipe:0','-an','-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-threads','1','-movflags','+faststart',public/'comparison.mp4'],comparison[:,:,:,:3].copy().tobytes())
    probes={}
    for path in sorted(public.glob('*.mp4')):
        result=subprocess.run([ffprobe_path(),'-v','error','-count_frames','-show_streams','-show_format','-of','json',str(path)],capture_output=True,check=True)
        probe=json.loads(result.stdout);videos=[s for s in probe['streams'] if s['codec_type']=='video']
        assert len(videos)==1 and int(videos[0]['nb_read_frames'])==N and videos[0]['r_frame_rate']=='6/1' and videos[0]['pix_fmt']=='yuv420p'
        assert not any(s['codec_type']=='audio' for s in probe['streams']);probes[path.name]=probe
    after=frozen();assert before==after
    media={p.relative_to(public).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(public.rglob('*')) if p.is_file()}
    record={'status':'passed','frozen_before':before,'frozen_after':after,'frozen_equal':True,'cli_calls':len(calls),
        'html_renders':len(rendered),'encoded_html_frames':N*len(rendered),'render_extra_order_redraws':N*len(rendered)*2,
        'quality_jobs':len(quality),'quality_frames':sum(x['frame_count'] for x in quality),'quality_reverse_redraws':sum(x['frame_count'] for x in quality),
        'rendered':rendered,'browser_reports':reports,'independent_fonttools_character_checks':reference_checks,
        'independent_late_outside_frames':[9,10,11],'legacy_missing_O_frames':list(range(6)),'legacy_pixels_published':False,
        'strict_rejections_preserve_project_ledger_assets':True,'strict_rebuild_inherited_and_new_gate':True,'package_rgba_exact':True,
        'input_font_mapping_oracle':'fontTools getBestCmap, separate from stdlib production parser','new_model_inference_calls':0,
        'rights_gate_status':rights['status'],'probes':probes,'media':media,'generator_sha256':sha(Path(__file__)),
        'manual_static_review':'pending','continuous_playback_accepted':False,'audio_fixture':False,'capcut_parity_accepted':False}
    save(evidence/'verification.json',record);save(evidence/'state.json',{'status':'complete','frozen_equal':True})
    print(json.dumps({k:record[k] for k in ('status','cli_calls','html_renders','encoded_html_frames','quality_jobs','quality_frames')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for key in ('work','public','evidence','runtime'):parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args();run(*(getattr(args,k).resolve() for k in ('work','public','evidence','runtime')))
