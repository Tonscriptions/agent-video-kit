"""Publish a short original, actual-frame contact sheet and SHA inventory, without rerendering edits."""
from datetime import datetime,timezone
from fractions import Fraction
import json
from pathlib import Path
import shutil
import subprocess
from PIL import Image,ImageDraw
from run_frozen_regression import frozen,sha
ROOT=Path(__file__).resolve().parents[1]
REL=ROOT/'docs/validation/evidence/multicam-affine-clock-20261021-lab'
ASSETS=ROOT/'docs/assets/multicam-affine-clock-20261021-lab'
OUT=ASSETS/'review-r1';assert not OUT.exists();OUT.mkdir()
OUTPUT=REL/'media-manifest-r1.json';assert not OUTPUT.exists()
read=lambda p:json.loads(Path(p).read_bytes())
before=frozen();assert len(before)==263
native=read(REL/'native-r3/verification.json');isolated=read(REL/'installed-r1/media/verification.json')
assert native['status']==isolated['status']=='passed'
assert native['frozen_before']==native['frozen_after']==isolated['frozen_before']==isolated['frozen_after']==before
record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),'calls':[],
    'script_sha256':sha(Path(__file__)),'frozen_before':before,'checks':[],
    'rights':'Original generated event clocks; CC0-1.0. No external media or fonts.',
    'source_native_receipt_sha256':sha(REL/'native-r3/verification.json'),
    'source_isolated_media_receipt_sha256':sha(REL/'installed-r1/media/verification.json'),
    'encoded_full_RGBA_equality_claimed':False,'AAC_exact_PCM_claimed':False,
    'continuous_playback_reviewed':False,'audio_listened':False,'full_capcut_parity':False}
def save():OUTPUT.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def check(name,ok,**details):record['checks'].append({'name':name,'ok':bool(ok),**details});save();assert ok,name
def run(label,args):
    command=list(map(str,args));r=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=300,
        creationflags=subprocess.CREATE_NO_WINDOW)
    (REL/(label+'.stderr.log')).write_bytes(r.stderr)
    record['calls'].append({'label':label,'command':command,'exit_code':r.returncode,
        'stdout_sha256':'sha256:'+__import__('hashlib').sha256(r.stdout).hexdigest(),
        'stderr_sha256':sha(REL/(label+'.stderr.log'))});save()
    assert r.returncode==0,r.stderr.decode('utf8','replace')[-1000:]
    return r.stdout
save()
try:
    ffmpeg=shutil.which('ffmpeg');ffprobe=shutil.which('ffprobe');assert ffmpeg and ffprobe
    graph='[0:v]split=3[v0][v1][v2];[0:a]aresample=48000:osf=flt:first_pts=0,'
    graph+='aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,asplit=3[a0][a1][a2];'
    for i,second in enumerate((0,295,586)):
        graph+=f'[v{i}]trim=start_frame={second*25}:end_frame={(second+4)*25},setpts=N/(25*TB)[p{i}];'
        graph+=f'[a{i}]atrim=start_sample={second*48000}:end_sample={(second+4)*48000},asetpts=N/SR/TB[s{i}];'
    graph+='[p0][s0][p1][s1][p2][s2]concat=n=3:v=1:a=1[v][a]'
    original=OUT/'source-selected-reference.mp4'
    run('short-original-reference',[ffmpeg,'-v','error','-filter_complex_threads','1','-i',
        ASSETS/'native-r2/source-reference.mkv','-filter_complex',graph,'-map','[v]','-map','[a]',
        '-c:v','libx264','-crf','0','-pix_fmt','yuv444p','-c:a','aac',original])
    pts=json.loads(run('short-original-reference-PTS',[ffprobe,'-v','error','-select_streams','v:0',
        '-show_frames','-show_streams','-show_entries','frame=pts:stream=time_base','-of','json',original]))
    tb=Fraction(pts['streams'][0]['time_base'])
    check('short-original-300-frames-exact-PTS',[int(r['pts'])*tb for r in pts['frames']]==[Fraction(i,25) for i in range(300)])
    original_gif=OUT/'source-selected-reference.gif'
    run('short-original-reference-GIF',[ffmpeg,'-v','error','-i',original,'-filter_complex',
        '[0:v]split[x][y];[x]palettegen=max_colors=128[p];[y][p]paletteuse=dither=none',original_gif])
    names=[('REFERENCE',original_gif),('POS OFFSET',ASSETS/'native-r3/positive-offset.gif'),
        ('POS AFFINE',ASSETS/'native-r3/positive-affine.gif'),('NEG OFFSET',ASSETS/'native-r3/small-negative-offset.gif'),
        ('NEG AFFINE',ASSETS/'native-r3/small-negative-affine.gif')]
    sheet=Image.new('RGB',(5*200,3*144),(245,245,245));draw=ImageDraw.Draw(sheet)
    for column,(label,path) in enumerate(names):
        with Image.open(path) as image:
            for row,frame in enumerate((0,100,200)):
                image.seek(frame);sheet.paste(image.convert('RGB'),(column*200+4,row*144+24))
                draw.text((column*200+4,row*144+4),label+' t='+str((0,295,586)[row]),fill=(10,10,10))
    contact=OUT/'actual-frame-contact-sheet.png';sheet.save(contact)
    files={};gif_count=0
    for path in sorted(ASSETS.rglob('*')):
        if not path.is_file():continue
        item={'sha256':sha(path),'bytes':path.stat().st_size}
        if path.suffix.lower()=='.gif':
            gif_count+=1
            with Image.open(path) as image:
                duration=0
                for i in range(image.n_frames):image.seek(i);duration+=image.info.get('duration',0)
                item.update(width=image.width,height=image.height,frames=image.n_frames,duration_ms=duration)
                check('GIF-'+path.parent.name+'-'+path.name,image.n_frames==300 and duration==12000)
        files[path.relative_to(ROOT).as_posix()]=item
    record.update(assets=files,asset_count=len(files),GIF_count=gif_count,
        original_short=original.relative_to(ROOT).as_posix(),contact_sheet=contact.relative_to(ROOT).as_posix(),
        contact_sheet_frames=[0,100,200],contact_sheet_manually_reviewed=False,
        retained_failed_inputs='native-r1 retains the original one-frame-short fixture; native-r2 retains pre-fix s16 master.',
        cases=native['cases'])
    check('all-eight-masters-have-expected-sample-and-frame-counts',all(row['lossless_frames']==300 and
        row['PCM_bytes']==4608000 and row['RGBA_bytes']==24883200 for media in (native,isolated)
        for case in media['cases'].values() for row in case.values()))
    check('frozen-core-unchanged',frozen()==before)
    record.update(status='passed-media-inventory',frozen_after=frozen(),finished_at_utc=datetime.now(timezone.utc).isoformat());save()
except BaseException as error:
    record.update(status='failed-preserved-for-review',error=repr(error),frozen_after=frozen());save();raise
(REL/'executed-media-finalizer.py.txt').write_bytes(Path(__file__).read_bytes())
print(json.dumps({k:record[k] for k in ('status','asset_count','GIF_count')},ensure_ascii=False))
