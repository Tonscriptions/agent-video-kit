"""Bind V78 frozen bytes, isolated media, failure history and published references."""
from __future__ import annotations
import argparse
import ast
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.parse
from PIL import Image
from run_frozen_regression import frozen
from sync_timeline_preview_documents import BASE,CONTRACT,DOCUMENTS,FOLLOWUPS,INSTALLED,NATIVE,REPORT,ROOT,SKILLS,SCRIPTS

def read(path):return json.loads(Path(path).read_bytes())
def sha(path):return 'sha256:'+hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--candidate',action='store_true');args=parser.parse_args();out=args.output.resolve()
    assert out.is_relative_to(BASE) and not out.exists()
    current=frozen();assert len(current)==235
    focus=read(BASE/'targeted-r7.json');dev=read(BASE/'native-r6/verification.json')
    install=read(BASE/'installed-r3/verification.json');media=read(BASE/'installed-r3/media/verification.json')
    context=read(BASE/'contexts-native-r3/verification.json');isolated_context=read(BASE/'contexts-installed-r2/verification.json')
    lut=read(BASE/'lut-native-r1/verification.json');isolated_lut=read(BASE/'lut-installed-r1/verification.json')
    assert focus['terminal_ok'] and focus['methods']==22 and focus['skipped']==0
    for value in (focus,dev,install,media,context,isolated_context):assert value['frozen_equal'] and value['frozen_before']==value['frozen_after']==current
    for value in (dev,install,media,context,isolated_context):assert value['status']=='passed' and all(x['ok'] for x in value['checks'])
    for name,value in [('lut-native-r1',lut),('lut-installed-r1',isolated_lut)]:
        assert value['status']=='passed' and value['frozen_equal'] and value['frozen_before']==value['frozen_after']==current
        assert value['cli_calls']==12 and [c['alias'] for c in value['cases']]==['path','file','lut']
        assert all(c['same_size_and_mtime'] and c['old_cache_rejected'] and c['new_content_hits'] and c['old_rgba_sha256']!=c['new_rgba_sha256'] for c in value['cases'])
        assert sha(BASE/name/'executed-lut.py.txt')==value['generator_sha256']==sha(ROOT/'scripts/probe_timeline_preview_lut.py')
    assert lut['cases']==isolated_lut['cases'] or [{k:v for k,v in c.items() if k not in ('original_cache_key','changed_cache_key')} for c in lut['cases']]==[{k:v for k,v in c.items() if k not in ('original_cache_key','changed_cache_key')} for c in isolated_lut['cases']]
    assert len(install['resource_hashes'])==154 and install['bundle']['wheels']==7
    assert install['isolated_cli_calls']==35 and install['module_origin_probes']==1
    assert dev['cli_calls']==media['cli_calls']==32 and len(dev['checks'])==len(media['checks'])==24
    keys=('name','frames','width','height','fps','pixels_sha256','pcm_sha256','pcm_samples','alpha_levels','verified_clock')
    assert [{k:c[k] for k in keys} for c in dev['cases']]==[{k:c[k] for k in keys} for c in media['cases']]
    assert [{k:c[k] for k in keys} for c in context['cases']]==[{k:c[k] for k in keys} for c in isolated_context['cases']]
    assert context['cli_calls']==isolated_context['cli_calls']==22 and len(context['checks'])==len(isolated_context['checks'])==15
    for name,value in [('contexts-native-r3',context),('contexts-installed-r2',isolated_context)]:
        assert sha(BASE/name/'executed-smoke.py.txt')==value['generator_sha256']==sha(ROOT/'scripts/probe_timeline_preview_contexts.py')
    assert [c['frames'] for c in dev['cases']]==[12,12,12,1]
    assert [c['pcm_samples'] for c in dev['cases']]==[48000,48000,48000,1554]
    assert dev['cases'][2]['alpha_levels']>2
    for value in (dev,media,context,isolated_context):
        assert not any(value[k] for k in ('network','virtualization','continuous_playback_reviewed','audio_reviewed','natural_quality_accepted','full_capcut_parity'))
        assert value['new_model_inference']==0
    for name,directory in [('native-r6',BASE/'native-r6'),('installed-r3',BASE/'installed-r3'),('installed-r3/media',BASE/'installed-r3/media'),
            ('contexts-native-r3',BASE/'contexts-native-r3'),('contexts-installed-r2',BASE/'contexts-installed-r2')]:
        value=read(directory/'verification.json')
        for call in value['calls']:
            assert call['exit_code']==0
            for stream in ('stdout','stderr'):
                p=directory/(call['label']+'.'+stream+'.log')
                if p.exists():assert sha(p)==call[stream+'_sha256'],p
    for name,value in [('lut-native-r1',lut),('lut-installed-r1',isolated_lut)]:
        for call in value['calls']:
            assert call['exit_code']==0
            for stream in ('stdout','stderr'):assert sha(BASE/name/(call['label']+'.'+stream+'.log'))==call[stream+'_sha256']
    for name,value in [('native-r6',dev),('installed-r3/media',media)]:
        assert sha(BASE/name/'executed-smoke.py.txt')==value['generator_sha256']==sha(ROOT/'scripts/smoke_timeline_preview.py')
    assert sha(BASE/'installed-r3/executed-install.py.txt')==install['generator_sha256']==sha(ROOT/'scripts/verify_timeline_preview_install.py')
    failures=[]
    for name in ('targeted-r1','targeted-r2','targeted-r6'):
        value=read(BASE/(name+'.json'));assert value['exit_code']!=0 and not value['terminal_ok'];failures.append(name)
    for name,methods in [('targeted-r3',17),('targeted-r4',20),('targeted-r5',21)]:
        value=read(BASE/(name+'.json'));assert value['terminal_ok'] and value['methods']==methods and value['skipped']==0
    for name in ('native-r1','native-r2','native-r3','native-r4','installed-r1','installed-r1/media','contexts-native-r1'):
        value=read(BASE/name/'verification.json');assert value['status']=='failed' and value['frozen_equal'];failures.append(name)
    static=read(BASE/'static-review-r2.json');assert static['review_mode']=='static-PNG-only'
    assert not any(static[k] for k in ('continuous_playback_reviewed','audio_reviewed','natural_quality_accepted','full_capcut_parity'))
    for row in static['files']:assert sha(ROOT/row['path'])==row['sha256']
    full=read(BASE/'full-r2.json')
    stopped=read(BASE/'full-r1.json');stop=read(BASE/'full-r1-stop.json')
    assert stopped['status']=='failed' and not stopped['terminal_ok'] and stopped['frozen_equal'] and stop['owner_pid']==37012
    preserved=read(BASE/'pre-lut-fix-source-r1/verification.json')
    for row in preserved['files']:assert sha(ROOT/row['retained'])==row['sha256']==stopped['frozen_after'][row['source']]
    failures.append('full-r1-stopped-for-confirmed-LUT-gap')
    if not args.candidate:
        assert full['status']=='passed' and full['terminal_ok'] and full['methods']==1768 and full['skipped']==0
        assert full['frozen_equal'] and full['frozen_before']==full['frozen_after']==current
        assert full['external_fixtures_equal'] and full['external_fixture_count']==8 and full['external_fixture_manifest_unchanged'] and full['verification_scripts_equal']
        skill_audit=read(BASE/'skills-r1.json');assert skill_audit['skill_count']==17 and skill_audit['local_links_checked']==318
    syntax=[]
    for name in [*('scripts/'+s+'.py' for s in SCRIPTS),'product/src/ai_ad_editor/preview.py','product/tests/test_timeline_preview.py']:
        path=ROOT/name;ast.parse(path.read_text(encoding='utf8'));syntax.append({'path':name,'sha256':sha(path)})
    local_links=0
    for path in [*(ROOT/n for n in DOCUMENTS+FOLLOWUPS),CONTRACT,REPORT,*(ROOT/'skills'/s/'SKILL.md' for s in SKILLS)]:
        text=path.read_text(encoding='utf8')
        if path not in (CONTRACT,REPORT):
            marker='V78-TIMELINE-PREVIEW' if path.name=='SKILL.md' else ('V78-FOLLOWUP' if path.relative_to(ROOT).as_posix() in FOLLOWUPS else 'V78-CURRENT')
            match=re.search(r'<!-- '+marker+r' -->(.*?)<!-- /'+marker+r' -->',text,re.S);assert match,path;text=match[1]
        for raw in re.findall(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^\"]*")?\)',text):
            target=raw.strip('<>').split('#',1)[0]
            if not target or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',target):continue
            assert (path.parent/urllib.parse.unquote(target)).resolve().exists(),(path,target);local_links+=1
    files=[];probes=[];invalid=[];pngs=[];probe=shutil.which('ffprobe');assert probe
    directories=[(ROOT/'docs/assets'/('timeline-preview-20261020-v78-'+suffix),BASE/receipt/'verification.json') for suffix,receipt in
        [('r1','native-r1'),('r2','native-r2'),('r3','native-r3'),('r4','native-r4'),('r5','native-r5'),('installed-r1','installed-r1/media'),('installed-r2','installed-r2/media'),
            ('contexts-r1','contexts-native-r1'),('contexts-r2','contexts-native-r2'),('contexts-installed-r1','contexts-installed-r1'),('r6','native-r6'),('installed-r3','installed-r3/media'),('contexts-r3','contexts-native-r3'),('contexts-installed-r2','contexts-installed-r2')]]
    assert {p.name for p,_ in directories}=={p.name for p in (ROOT/'docs/assets').glob('timeline-preview-20261020-v78-*') if p.is_dir()}
    for directory,receipt_path in directories:
        receipt=read(receipt_path);passed=receipt['status']=='passed'
        actual={p.name for p in directory.iterdir() if p.is_file()}
        if passed:assert actual==set(receipt['public_files'])
        for p in sorted(directory.iterdir()):
            assert p.is_file() and not p.is_symlink()
            row={'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p),'origin_status':receipt['status']};files.append(row)
            if passed:assert {k:row[k] for k in ('bytes','sha256')}==receipt['public_files'][p.name]
            if p.suffix.lower() in {'.nut','.mp4','.gif'}:
                result=subprocess.run([probe,'-v','error','-count_frames','-show_streams','-show_format','-of','json',str(p)],capture_output=True,timeout=120)
                details={'path':row['path'],'exit_code':result.returncode,'stdout_sha256':'sha256:'+hashlib.sha256(result.stdout).hexdigest(),
                    'stderr':result.stderr.decode('utf8','replace')}
                if result.returncode:
                    assert not passed and p.name=='ntsc-preview.gif' and p.stat().st_size==0;invalid.append(details)
                else:
                    details['probe']=json.loads(result.stdout);probes.append(details)
                    if passed and p.name.endswith('-reference.nut'):
                        case=next(c for c in receipt['cases'] if p.name==c['name']+'-reference.nut')
                        video=next(s for s in details['probe']['streams'] if s['codec_type']=='video')
                        assert int(video['nb_read_frames'])==case['frames'] and video['width']==case['width'] and video['height']==case['height']
            if p.suffix.lower()=='.png':
                with Image.open(p) as im:pngs.append({'path':row['path'],'size':list(im.size),'mode':im.mode,'alpha_levels':len(set(im.convert('RGBA').tobytes()[3::4]))})
    assert len(invalid)==2
    record={'status':'passed-candidate-audit' if args.candidate else 'passed-release-audit','checked_at_utc':datetime.now(timezone.utc).isoformat(),
        'generator_sha256':sha(__file__),'source_frozen_equal':current==frozen(),'frozen_inputs':current,'full_terminal':full.get('terminal_ok',False),
        'native_cli_calls':dev['cli_calls'],'isolated_cli_calls':install['isolated_cli_calls'],'resource_count':len(install['resource_hashes']),
        'context_native_cli_calls':context['cli_calls'],'context_isolated_cli_calls':isolated_context['cli_calls'],
        'lut_native_cli_calls':lut['cli_calls'],'lut_isolated_cli_calls':isolated_lut['cli_calls'],
        'local_links_checked':local_links,'retained_failed_runs':failures,'public_files':files,'encoded_media_probes':probes,
        'retained_invalid_failed_gifs':invalid,'png_probes':pngs,'syntax_parsed':syntax,'virtualization':False,'new_model_inference':0,
        'continuous_playback_reviewed':False,'audio_reviewed':False,'natural_quality_accepted':False,'full_capcut_parity':False}
    out.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({k:record[k] for k in ('status','source_frozen_equal','native_cli_calls','isolated_cli_calls','resource_count','local_links_checked')}))

if __name__=='__main__':main()
