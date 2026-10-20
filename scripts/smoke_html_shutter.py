"""Real native/installed HTML shutter CLI, independent pixels and portable recipes."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from PIL import Image
from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
WIDTH, HEIGHT, FPS, FRAMES, TPS = 320, 180, 8, 16, 90000
CUT = 89100


def sha(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')


def source_pixels(seconds):
    """Independent procedural raster; no product scheduler or compositor imported."""
    data = bytearray(WIDTH * HEIGHT * 4)
    position = 16 + math.floor(float(seconds) * 96)
    color = bytes((255, 0, 0, 255) if seconds < Fraction(CUT, TPS) else (0, 96, 255, 255))
    for y in range(60, 88):
        start = (y * WIDTH + position) * 4
        data[start:start + 20 * 4] = color * 20
    for y in range(120, 144):
        start = (y * WIDTH + 276) * 4
        data[start:start + 20 * 4] = bytes((0, 255, 0, 128)) * 20
    return bytes(data)


def reference(frame, *, samples=1, cuts=False):
    anchor = Fraction(frame, FPS)
    images = []
    times = []
    for k in range(samples):
        current = anchor if samples == 1 else (frame + (Fraction(2*k+1, 2*samples) - Fraction(1, 2))) / FPS
        low, high = Fraction(0), Fraction(2)
        if cuts:
            if anchor < Fraction(CUT, TPS):
                high = Fraction(CUT, TPS)
            else:
                low = Fraction(CUT, TPS)
        current = min(max(current, low), high - Fraction(1, 1000000))
        times.append(str(current))
        images.append(source_pixels(current))
    if samples == 1:
        return images[0], times
    output = bytearray(WIDTH * HEIGHT * 4)
    # Independent Python integer implementation, deliberately not Pillow ImageMath.
    for offset in range(0, len(output), 4):
        alpha = sum(image[offset+3] for image in images)
        for channel in range(3):
            total = sum(image[offset+channel] * image[offset+3] for image in images)
            output[offset+channel] = (2*total + alpha) // (2*alpha) if alpha else 0
        output[offset+3] = (2*alpha + samples) // (2*samples)
    return bytes(output), times


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('work', 'evidence', 'assets', 'runtime'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--installed', type=Path)
    args = parser.parse_args()
    work, evidence, assets = (p.resolve() for p in (args.work, args.evidence, args.assets))
    assert evidence.is_relative_to(ROOT/'docs') and assets.is_relative_to(ROOT/'docs/assets')
    assert not any(p.exists() for p in (work, evidence, assets))
    for path in (work, evidence, assets):
        path.mkdir(parents=True)
    env = dict(os.environ)
    env.update(TEMP=str(ROOT/'product/.runtime/temp'), TMP=str(ROOT/'product/.runtime/temp'),
               TMPDIR=str(ROOT/'product/.runtime/temp'), PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(ROOT/'product/src'))
    prefix = ([sys.executable, '-I', '-S', '-B', '-X', 'utf8', str(args.installed.resolve()/'run.py')] if args.installed else
              [sys.executable, '-E', '-B', '-X', 'utf8', '-c',
               'import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.cli import main;sys.exit(main())', str(ROOT/'product/src')])
    record = {'status':'running', 'started_at_utc':datetime.now(timezone.utc).isoformat(),
              'script_sha256':sha(Path(__file__).read_bytes()), 'native_windows':sys.platform=='win32',
              'virtualization':False, 'network_media':False, 'new_model_inference':0,
              'installed':str(args.installed) if args.installed else None, 'frozen_before':frozen(),
              'calls':[], 'checks':[], 'renders':{}, 'full_capcut_parity':False, 'quality_accepted':False}

    def save():
        write(evidence/'verification.json', record)

    def check(name, ok, **detail):
        record['checks'].append({'name':name, 'ok':bool(ok), **detail})
        save()
        if not ok:
            raise AssertionError(name)

    def run(label, command, *, expect=0, data=None, binary=False):
        started = time.monotonic()
        command = list(map(str, command))
        result = subprocess.run(command, input=data, cwd=ROOT, env=env, capture_output=True, timeout=600)
        (evidence/(label+'.stderr.log')).write_bytes(result.stderr)
        if not binary:
            (evidence/(label+'.stdout.log')).write_bytes(result.stdout)
        record['calls'].append({'label':label, 'command':command, 'exit_code':result.returncode,
                                'expected_exit':expect, 'seconds':time.monotonic()-started,
                                'stdout_sha256':sha(result.stdout), 'stderr_sha256':sha(result.stderr),
                                'stdout_bytes':len(result.stdout)})
        save()
        if result.returncode != expect:
            raise AssertionError(label+': '+result.stdout[-1800:].decode('utf8', 'replace')+result.stderr[-1000:].decode('utf8', 'replace'))
        return result.stdout

    def cli(label, *argv, expect=0):
        return json.loads(run('cli-'+label, [*prefix, *argv], expect=expect))

    def ff(label, *argv, data=None, binary=False):
        return run(label, ['ffmpeg', '-hide_banner', '-v', 'error', '-nostdin', *argv], data=data, binary=binary)

    def configure(project, label):
        cli('init-'+label, 'project', 'init', project, '--name', 'Native shutter evidence')
        cli('register-'+label, 'motion', 'html-register', '--project', project, '--input', args.runtime.resolve())

    def render(project, label, *argv):
        result = cli(label, 'motion', 'html-render', '--project', project, '--asset-id', label, *argv)
        report = json.loads(Path(result['data']['report']).read_bytes())
        write(evidence/(label+'-browser.json'), report)
        check(label+'-owned-processes-reaped', report['cleanup']['all_children_reaped'] and not report['cleanup']['active_after_cleanup']
              and report['worker']['cleanup']['browser_closed'])
        check(label+'-exact-output-clock', report['encoded_clock']['frame_count']==FRAMES and report['encoded_clock']['all_frames_exact'])
        path = project/result['data']['asset']['uri']
        raw = ff('decode-'+label, '-i', path, '-an', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-threads', '1', 'pipe:1', binary=True)
        check(label+'-whole-frame-count', len(raw)==FRAMES*WIDTH*HEIGHT*4)
        frames = [raw[i:i+WIDTH*HEIGHT*4] for i in range(0, len(raw), WIDTH*HEIGHT*4)]
        row = {'asset':result['data']['asset'], 'frame_rgba_sha256':[sha(frame) for frame in frames],
               'source_capture_count':report['shutter_evidence']['source_capture_count'],
               'encoded_clock':report['encoded_clock'], 'cleanup':report['cleanup'],
               'worker_cleanup':report['worker']['cleanup'], 'render_seconds':record['calls'][-2]['seconds']}
        quality = result['data'].get('layout_report')
        if quality:
            quality = json.loads(Path(quality).read_bytes())
            write(evidence/(label+'-layout.json'), quality)
            check(label+'-all-layout-samples', quality['frame_count']==row['source_capture_count']
                  and quality['cleanup']['all_children_reaped'] and not quality['cleanup']['active_after_cleanup'])
            row['layout_frame_count'] = quality['frame_count']
        record['renders'][label] = row
        save()
        return result, path, raw

    try:
        source = assets/'source'; source.mkdir()
        (source/'index.html').write_text('''<!doctype html><meta charset="utf-8"><style>
*{margin:0;box-sizing:border-box}html,body{width:320px;height:180px;overflow:hidden;background:transparent}
#moving{position:absolute;top:60px;width:20px;height:28px}#stationary{position:absolute;left:276px;top:120px;width:20px;height:24px;background:rgba(0,255,0,.5)}
</style><div id="moving"></div><div id="stationary"></div><script>
window.film={frame(t){moving.style.left=(16+Math.floor(t*96))+'px';moving.style.background=t<.99?'#ff0000':'#0060ff'}};
</script>''', encoding='utf8', newline='\n')
        write(source/'manifest.json', {'entry':'index.html','width':WIDTH,'height':HEIGHT,'fps':{'num':FPS,'den':1},
                                     'duration_tick':2*TPS,'files':['index.html'],'variables':[]})
        write(assets/'source-origin.json', {'license_spdx':'CC0-1.0', 'creator':'agent-video-kit procedural fixture',
             'source':'original CSS integer moving rectangle and half-alpha stationary rectangle; no external media or fonts',
             'generator_sha256':record['script_sha256'], 'width':WIDTH,'height':HEIGHT,'fps':FPS,'frames':FRAMES,
             'duration_seconds':2,'audio_streams':0,'fixture_only':True,'natural_motion_quality_accepted':False})
        project=work/'project'; configure(project, 'source')
        cli('source', 'motion','html-source','--project',project,'--input',source/'manifest.json',
            '--asset-id','source','--creator','agent-video-kit procedural fixture','--license-spdx','CC0-1.0')
        sharp, sharp_path, plain = render(project, 'sharp', '--source-asset-id','source','--layout-check','strict')
        blur, blur_path, blurred = render(project, 'blur', '--source-asset-id','source','--shutter-samples','4',
                                         '--shutter-fraction','1','--layout-check','strict','--apply','--track-id','track_video_1')
        cut, cut_path, bounded = render(project, 'cut', '--source-asset-id','source','--shutter-samples','4',
                                       '--shutter-fraction','1','--shutter-cut-tick',str(CUT),'--layout-check','strict')
        inherited, _, again = render(project, 'recipe', '--from-asset-id','cut')
        check('saved-cut-recipe-replays-all-rgba', again==bounded and inherited['data']['asset']['html_motion']['shutter']==cut['data']['asset']['html_motion']['shutter'])
        _, _, zero = render(project, 'zero', '--source-asset-id','source','--shutter-samples','16','--shutter-fraction','0')
        check('zero-exposure-default-pixel-identity', plain==zero)
        expected={};time_rows={}
        for name, samples, cuts, actual in [('sharp',1,False,plain),('blur',4,False,blurred),('cut',4,True,bounded)]:
            rows=[reference(frame,samples=samples,cuts=cuts) for frame in range(FRAMES)]
            expected[name]=[sha(row[0]) for row in rows];time_rows[name]=[row[1] for row in rows]
            check(name+'-all-rgba-independent-reference', actual==b''.join(row[0] for row in rows), pixels=FRAMES*WIDTH*HEIGHT)
        record['independent_reference_rgba_sha256']=expected
        write(evidence/'independent-reference-times.json',time_rows)
        check('explicit-cut-changes-actual-frames', bounded!=blurred)
        archive=work/'project.zip'; cli('package-export','convert','export','--project',project,'--output',archive,'--target-format','package')
        restored=work/'restored';cli('package-import','convert','import','--input',archive,'--output',restored)
        cli('register-restored','motion','html-register','--project',restored,'--input',args.runtime.resolve())
        rebuilt, _, reloaded=render(restored,'package-rebuilt','--from-asset-id','cut')
        check('package-recipe-and-all-rgba-preserved',reloaded==bounded and rebuilt['data']['asset']['html_motion']['shutter']==cut['data']['asset']['html_motion']['shutter'])
        library=work/'library';request=work/'fragment.json'
        write(request,{'id':'shutter-fixture','version':1,'sequence_id':'seq_main','clip_ids':[blur['data']['generated_clip']['id']]})
        cli('fragment-save','fragment','save','--project',project,'--library',library,'--input',request)
        recipient=work/'recipient';configure(recipient,'recipient')
        write(request,{'id':'shutter-fixture','version':1,'sequence_id':'seq_main','track_id':'track_video_1','at_tick':0,'instance_id':'motion-one'})
        cli('fragment-apply','fragment','apply','--project',recipient,'--library',library,'--input',request)
        imported=next(a for a in json.loads((recipient/'project.json').read_bytes())['assets'] if a.get('html_motion'))
        fragment, _, fragment_raw=render(recipient,'fragment-rebuilt','--from-asset-id',imported['id'])
        check('fragment-relinked-recipe-and-all-rgba-preserved',fragment_raw==blurred and fragment['data']['asset']['html_motion']['shutter']==blur['data']['asset']['html_motion']['shutter'])
        before=(project/'project.json').read_bytes()
        invalid=cli('invalid','motion','html-render','--project',project,'--source-asset-id','source','--asset-id','invalid',
                    '--shutter-fraction','nan',expect=2)
        check('invalid-no-author-write',invalid['errors'][0]['code']=='HTML_SHUTTER_INVALID' and before==(project/'project.json').read_bytes())
        cli('validate','validate','--project',project)
        for label,path in [('sharp',sharp_path),('blur',blur_path),('cut',cut_path)]:
            shutil.copyfile(path, assets/(label+'-alpha.nut'))
        stride=WIDTH*HEIGHT*4; rgb={}
        checker=Image.new('RGB',(WIDTH,HEIGHT));pixels=checker.load()
        for y in range(HEIGHT):
            for x in range(WIDTH):pixels[x,y]=((35,45,62) if (x//12+y//12)%2 else (55,65,82))
        for label,raw in [('sharp',plain),('blur',blurred),('cut',bounded)]:
            frames=[]
            for frame in range(FRAMES):
                image=Image.frombytes('RGBA',(WIDTH,HEIGHT),raw[frame*stride:(frame+1)*stride]);background=checker.copy();background.paste(image,(0,0),image.getchannel('A'));frames.append(background)
            rgb[label]=frames
            ff('preview-'+label,'-f','rawvideo','-pix_fmt','rgb24','-s',f'{WIDTH}x{HEIGHT}','-r',str(FPS),'-i','pipe:0',
               '-an','-c:v','libx264rgb','-crf','0','-preset','ultrafast',assets/(label+'.mp4'),data=b''.join(f.tobytes() for f in frames))
        comparison=[]
        for index in range(FRAMES):
            image=Image.new('RGB',(WIDTH*3,HEIGHT))
            for column,label in enumerate(('sharp','blur','cut')):image.paste(rgb[label][index],(column*WIDTH,0))
            comparison.append(image)
        ff('preview-comparison','-f','rawvideo','-pix_fmt','rgb24','-s',f'{WIDTH*3}x{HEIGHT}','-r',str(FPS),'-i','pipe:0',
           '-an','-c:v','libx264rgb','-crf','0','-preset','ultrafast',assets/'comparison.mp4',data=b''.join(f.tobytes() for f in comparison))
        comparison[0].save(assets/'comparison.gif',save_all=True,append_images=comparison[1:],duration=[120,130]*8,loop=0,disposal=2)
        contact=Image.new('RGB',(WIDTH*3,HEIGHT*3))
        for row,index in enumerate((1,8,12)):contact.paste(comparison[index],(0,row*HEIGHT))
        contact.save(assets/'contact.png')
        write(assets/'media-origin.json',{'original':'source/index.html','columns':['sharp samples=1','shutter samples=4 fraction=1 no internal cuts declared','shutter samples=4 fraction=1 cut_tick=89100'],
            'contact_frame_indexes':[1,8,12],'comparison_width':960,'height':180,'fps':FPS,'frames':FRAMES,'duration_seconds':2,
            'preview_background':'12px opaque checkerboard only for viewing; raw NUT preserves alpha',
            'gif_duration_ms':[120,130]*8,'gif_is_quantized_preview':True,'continuous_playback_reviewed':False,'audio_streams':0})
        record.update(status='passed',cli_calls=sum(c['label'].startswith('cli-') for c in record['calls']),
                      public_files={p.relative_to(assets).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())} for p in assets.rglob('*') if p.is_file()})
    except BaseException as exc:
        record.update(status='failed',error={'type':type(exc).__name__,'message':str(exc)})
        raise
    finally:
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),frozen_after=frozen())
        record['frozen_equal']=record['frozen_before']==record['frozen_after'];save()
    assert record['frozen_equal']
    print(json.dumps({k:record[k] for k in ('status','cli_calls','frozen_equal')}))


if __name__=='__main__':main()
