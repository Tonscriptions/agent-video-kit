"""Native CLI routing media with independent PCM math and declared DSP reuse.

All inputs/diagrams are authored CC0 fixtures. The cursor/waveform preview is
an evidence wrapper around actual decoded product audio, not an editor GUI.
"""
from __future__ import annotations
import argparse
import array
import contextlib
import copy
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import wave
import zipfile

from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
BASELINE = '7a4a803c520616fc3b727dada7e6a032d0937ab1'
TPS, SR, FPS, W, H = 90000, 48000, 12, 640, 360


def sha(path): return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


def decode(path):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-map', '0:a:0',
        '-f', 'f32le', '-c:a', 'pcm_f32le', 'pipe:1'], capture_output=True, check=True).stdout
    result = array.array('f'); result.frombytes(raw)
    return list(result)


def automation(left=0, right=1):
    return [{'property': 'audio.volume', 'keyframes': [
        {'at_tick': 0, 'value': left, 'interpolation': 'linear'},
        {'at_tick': 2*TPS, 'value': right, 'interpolation': 'linear'}]}]


def case_plan(code):
    rows = [{'op': 'append_clip', 'track_id': 'track_video_1', 'id': 'diagram', 'asset_id': 'diagram',
             'source_in_tick': 0, 'source_out_tick': (3 if code == 'AR06' else 2)*TPS,
             'duration_tick': (3 if code == 'AR06' else 2)*TPS}]
    def tone(seq='seq_main', track='track_audio_1', name='tone', **fields):
        rows.append({'op': 'append_clip', 'sequence_id': seq, 'track_id': track, 'id': 'clip_'+str(len(rows)),
            'asset_id': name, 'source_in_tick': 0, 'source_out_tick': 2*TPS, 'duration_tick': 2*TPS, **fields})
    def routing(seq='seq_main', **fields):
        rows.append({'op': 'update_sequence', 'sequence_id': seq,
                     'patch': {'audio_routing': {'version': 1, **fields}}})
    if code in {'AR01', 'AR04'}:
        tone(); rows.append({'op': 'add_track', 'id': 'music', 'kind': 'audio', 'order': 1})
        tone(track='music', name='music')
        if code == 'AR01':
            routing(tracks=[{'track_id': t, 'output': 'shared'} for t in ('track_audio_1', 'music')],
                    buses=[{'id': 'shared', 'audio': {'volume': .5}, 'output': 'sub'},
                           {'id': 'sub', 'audio': {'volume': .5}}])
        else:
            routing(tracks=[{'track_id': 'track_audio_1', 'output': 'detector'}, {'track_id': 'music', 'output': 'music_bus'}],
                buses=[{'id': 'detector', 'output': None}, {'id': 'music_bus', 'audio': {'solo': True},
                'sidechain': {'bus_id': 'detector', 'compressor': {'threshold': .05, 'ratio': 8, 'attack': 1, 'release': 50}}}])
    elif code == 'AR02':
        tone(); rows.append({'op': 'update_track', 'track_id': 'track_audio_1', 'patch': {'audio': {'volume': .5}}})
        routing(tracks=[{'track_id': 'track_audio_1', 'sends': [{'bus_id': 'return', 'tap': 'pre_fader', 'gain': .4},
                {'bus_id': 'return', 'tap': 'post_fader', 'gain': .6}]}], buses=[{'id': 'return', 'audio': {'volume': .25}}])
    elif code == 'AR03':
        tone(name='stereo')
        routing(tracks=[{'track_id': 'track_audio_1', 'output': 'fade', 'keyframes': automation(.25, 1)}],
            buses=[{'id': 'fade', 'audio': {'pan': .5}, 'keyframes': automation(.5, 1)}], master={'audio': {'volume': .75}})
    else:
        rows.append({'op': 'add_sequence', 'id': 'child', 'duration_tick': 2*TPS})
        tone(seq='child', track='child_audio_1', name='tone' if code == 'AR05' else 'dc')
        audio = {'compressor': {'threshold': .1, 'ratio': 4, 'attack': 1, 'release': 50}} if code == 'AR05' else {}
        routing(seq='child', tracks=[{'track_id': 'child_audio_1', 'output': 'local'}],
                buses=[{'id': 'local', 'audio': audio, 'keyframes': automation()}])
        rows.append({'op': 'append_sequence_clip', 'track_id': 'track_video_1', 'id': 'group',
            'nested_sequence_id': 'child', 'source_in_tick': 0, 'source_out_tick': 2*TPS,
            'duration_tick': (3 if code == 'AR06' else 2)*TPS,
            **({'reverse': True} if code == 'AR05' else {'freeze': {'at_tick': TPS, 'duration_tick': TPS, 'audio_mode': 'silence'}})})
        rows[0]['overlap_policy'] = 'allow'
        rows.insert(0, {'op': 'update_track', 'track_id': 'track_video_1', 'patch': {'overlap_policy': 'allow'}})
    return rows


TITLES = {
    'AR01': ('Shared multi-level buses', 'tone + music -> shared x .5 -> sub x .5 -> master'),
    'AR02': ('Pre/post-fader sends', 'dry .5 + (.4 pre + .6 post x .5) x .25 = .675'),
    'AR03': ('Sequence-clock automation', 'track .25..1 -> bus .5..1, balance +.5 -> master .75'),
    'AR04': ('Solo with unchanged detector', 'voice -> detector only | music -> sidechain -> solo bus'),
    'AR05': ('Complete child before reverse', 'child compressor -> child 0..1 gain -> outer reverse'),
    'AR06': ('Complete child before freeze', 'child 0..1 gain -> 1 s silence -> remaining child bus'),
}


def run(work, output):
    work.mkdir(parents=True, exist_ok=False); output.mkdir(parents=True, exist_ok=False)
    (output/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    os.environ.update(TEMP=str(work), TMP=str(work), TMPDIR=str(work), PYTHONDONTWRITEBYTECODE='1')
    sys.path.insert(0, str(ROOT/'product/src'))
    from ai_ad_editor.cli import main
    from ai_ad_editor.project import load_project, save_project
    from ai_ad_editor.runtime import configure_local_runtime
    from PIL import Image, ImageDraw, ImageFont
    configure_local_runtime()
    before = frozen(); started = time.monotonic(); calls=[]; records=[]
    font = ImageFont.load_default(size=17); small = ImageFont.load_default(size=13)

    def cli(*args):
        out = io.StringIO(); begin = time.monotonic()
        with contextlib.redirect_stdout(out): code = main(list(map(str, args)))
        value = json.loads(out.getvalue()); index = len(calls)+1
        relative = f'cli/{index:03}.json'; save(output/relative, value)
        calls.append({'arguments': list(map(str, args)), 'exit_code': code, 'seconds': time.monotonic()-begin,
                      'result': relative, 'result_sha256': sha(output/relative)})
        if code: raise RuntimeError(json.dumps(value, ensure_ascii=False))
        return value

    sources = {}
    for name in ('tone', 'music', 'stereo', 'dc'):
        values = array.array('h')
        for n in range(2*SR):
            left = round((11000 if name != 'music' else 4500)*math.sin(2*math.pi*(400 if name != 'music' else 1200)*n/SR))
            right = round(7500*math.sin(2*math.pi*800*n/SR)) if name == 'stereo' else left
            if name == 'dc': left=right=10000
            values.extend((left, right))
        path = output/(name+'.wav')
        with wave.open(str(path), 'wb') as stream:
            stream.setparams((2, 2, SR, 0, 'NONE', 'not compressed')); stream.writeframes(values.tobytes())
        sources[name] = [n/32768 for n in values]
    save(output/'fixture-provenance.json', {'license': 'CC0-1.0', 'source': 'original mathematical waveforms and authored diagrams',
        'contains_natural_voice_or_model_output': False, 'input_sample_rate': SR, 'input_channels': 2,
        'input_bit_depth': 16, 'font': 'Pillow bundled default rendered in diagrams; no font binary redistributed',
        'generator_sha256': sha(Path(__file__)), 'created_at_utc': datetime.now(timezone.utc).isoformat()})

    def dsp(values, filter_text, detector=None):
        command = ['ffmpeg', '-v', 'error']
        for i, signal in enumerate([values]+([detector] if detector is not None else [])):
            path = work/f'ref{i}.f32'; path.write_bytes(array.array('f', signal).tobytes())
            command += ['-f', 'f32le', '-ar', str(SR), '-ac', '2', '-i', str(path)]
        if detector is None: command += ['-af', filter_text]
        else: command += ['-filter_complex', '[0:a]aformat=sample_fmts=fltp,asetnsamples=n=1024:p=0[a];'
            '[1:a]aformat=sample_fmts=fltp,asetnsamples=n=1024:p=0[b];[a][b]'+filter_text+'[out]', '-map', '[out]']
        command += ['-f', 'f32le', '-c:a', 'pcm_f32le', 'pipe:1']
        raw = subprocess.run(command, capture_output=True, check=True).stdout
        result = array.array('f'); result.frombytes(raw); return list(result)

    panels=[]; previews=[]
    for code, (title, description) in TITLES.items():
        panel = Image.new('RGB', (W, H), '#121b2b'); draw=ImageDraw.Draw(panel)
        draw.text((26, 24), code+'  '+title, font=font, fill='#eef3ff')
        draw.text((26, 65), description, font=small, fill='#8fdfcf')
        draw.text((26, 106), 'REAL CLI OUTPUT AUDIO | 48 kHz float master', font=small, fill='#eef3ff')
        draw.text((26, 128), 'Controlled synthetic fixture. No listening/CapCut parity acceptance.', font=small, fill='#a8b8d1')
        diagram = output/(code+'-input.png'); panel.save(diagram)
        project = work/code; cli('project', 'init', project, '--name', code)
        _, p = load_project(project)
        p['settings']['canvas'].update(width=W, height=H)
        p['settings']['timebase']['display_fps'] = {'num': FPS, 'den': 1}
        p['settings']['output'] = {'container': 'mkv', 'video': {'codec': 'libx264', 'crf': 0, 'pixel_format': 'yuv444p', 'preset': 'ultrafast'},
            'audio': {'codec': 'pcm_f32le', 'bitrate': '192k'}}
        save_project(project, p)
        for aid, source in [('diagram', diagram)]+[(name, output/(name+'.wav')) for name in sources]:
            cli('media', 'ingest', '--project', project, '--input', source, '--asset-id', aid,
                '--source-url', 'local:original-audio-routing-v55-fixture', '--license-spdx', 'CC0-1.0',
                '--permitted-use', 'commercial_ad', '--verification-status', 'verified', '--evidence', 'original mathematical signal; no external media')
        operations = {'operations': case_plan(code)}
        plan_path=output/(code+'-operations.json'); save(plan_path, operations)
        cli('timeline', 'compose', '--project', project, '--input', plan_path)
        target = project/'renders/result.mkv'
        result = cli('render', '--project', project, '--output', target, '--publish')
        actual = decode(target)
        if code == 'AR01': expected=[(a+b)*.25 for a,b in zip(sources['tone'], sources['music'])]
        elif code == 'AR02': expected=[v*.675 for v in sources['tone']]
        elif code == 'AR03': expected=[v*(.25+.75*(n//2/(2*SR)))*(.5+.5*(n//2/(2*SR)))*.75*(.5 if n%2 == 0 else 1)
                                     for n,v in enumerate(sources['stereo'])]
        elif code == 'AR04': expected=dsp(sources['music'], 'sidechaincompress=threshold=0.05:ratio=8:attack=1:release=50', sources['tone'])
        elif code == 'AR05':
            signal=dsp(sources['tone'], 'acompressor=threshold=0.1:ratio=4:attack=1:release=50')
            expected=[v*(n/(2*SR)) for n in reversed(range(2*SR)) for v in signal[2*n:2*n+2]]
        else:
            signal=[v*(n//2/(2*SR)) for n,v in enumerate(sources['dc'])]
            expected=signal[:2*SR]+[0.]*(2*SR)+signal[2*SR:]
        assert len(actual) == len(expected)
        error=max(map(abs, (a-b for a,b in zip(actual, expected))))
        assert error <= 2e-6, (code, error)
        shutil.copyfile(target, output/(code+'.mkv'))
        save(output/(code+'-manifest.json'), json.loads(Path(result['data']['manifest']).read_bytes()))
        cli('convert', 'export', '--project', project, '--target-format', 'package', '--output', output/(code+'.aevpkg.zip'))
        # Preview waveform is measured from the actual decoded product output.
        draw.text((26, 170), 'Decoded output: left / right', font=small, fill='#a8b8d1')
        for channel, center, color in ((0, 225, '#7cddc6'), (1, 295, '#91afff')):
            draw.line((26, center, W-26, center), fill='#384964')
            values=actual[channel::2]
            for x in range(W-52):
                block=values[x*len(values)//(W-52):(x+1)*len(values)//(W-52)]
                peak=max(map(abs, block), default=0)
                draw.line((x+26, center-peak*75, x+26, center+peak*75), fill=color)
        panel.save(output/(code+'-waveform.png')); panels.append(panel)
        seconds=len(actual)//2/SR; frame_count=round(seconds*FPS)
        frames=work/(code+'.rgb')
        with frames.open('wb') as stream:
            for n in range(frame_count):
                image=panel.copy(); painter=ImageDraw.Draw(image); x=26+round((W-52)*n/max(1,frame_count-1))
                painter.line((x, 196, x, 330), fill='#ffffff', width=2)
                stream.write(image.tobytes())
        preview=output/(code+'.mp4')
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', str(frames),
            '-i', str(target), '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
            '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', '-t', str(seconds), str(preview)],
            capture_output=True, check=True)
        previews.append(preview)
        probe=json.loads(subprocess.run(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(preview)],
                                        capture_output=True,check=True).stdout)
        save(output/(code+'-preview-probe.json'),probe)
        records.append({'id': code, 'title': title, 'description': description, 'project': str(project), 'duration_seconds': seconds,
            'output_samples': len(actual)//2, 'max_absolute_error': error, 'tolerance': 2e-6,
            'reference': 'independent float sample math' if code not in {'AR04','AR05'} else 'independent wiring; same FFmpeg DSP, not independent algorithm',
            'source_plan': plan_path.name, 'lossless_output': code+'.mkv', 'preview': preview.name,
            'source_package': code+'.aevpkg.zip', 'decoded_pcm_sha256': 'sha256:'+hashlib.sha256(array.array('f',actual).tobytes()).hexdigest()})
    contact=Image.new('RGB',(W*2,H*3),'#121b2b')
    for i,panel in enumerate(panels): contact.paste(panel,((i%2)*W,(i//2)*H))
    contact.save(output/'contact-sheet.png')
    # Concat the actual public previews; this wrapper never changes project DSP.
    listing=work/'previews.txt'; listing.write_text(''.join("file '"+p.as_posix().replace("'", "'\\''")+"'\n" for p in previews),encoding='utf-8')
    combined=output/'audio-routing-showcase.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','concat','-safe','0','-i',str(listing),'-c:v','libx264','-preset','fast','-crf','18',
        '-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',str(combined)],capture_output=True,check=True)
    subprocess.run(['ffmpeg','-v','error','-i',str(combined),'-vf',
        'fps=6,scale=480:-1:flags=lanczos,split[s0][s1];[s0]palettegen=stats_mode=diff[p];[s1][p]paletteuse=dither=bayer',
        str(output/'audio-routing-showcase.gif')],capture_output=True,check=True)
    # One previous-release control: the old renderer ignores the new author
    # field and emits only the dry half-gain. Do not call this an old feature.
    archive=work/'baseline.zip'
    subprocess.run(['git','archive','--format=zip','--output',str(archive),BASELINE,'product/src'],cwd=ROOT,check=True)
    baseline=work/'baseline'
    with zipfile.ZipFile(archive) as z:z.extractall(baseline)
    oldproject=work/'baseline-project';shutil.copytree(work/'AR02',oldproject)
    env=dict(os.environ);env['PYTHONPATH']=str(baseline/'product/src')
    command=[sys.executable,'-B','-X','utf8','-m','ai_ad_editor','render','--project',str(oldproject),'--output',str(oldproject/'renders/old.mkv')]
    old=subprocess.run(command,cwd=work,env=env,capture_output=True,timeout=120)
    (output/'baseline-render.stdout.json').write_bytes(old.stdout);(output/'baseline-render.stderr.log').write_bytes(old.stderr)
    assert old.returncode == 0,old.stderr
    samples=decode(oldproject/'renders/old.mkv')
    expected=[v*.5 for v in sources['tone']]
    old_error=max(abs(a-b) for a,b in zip(samples,expected))
    assert len(samples)==len(expected) and old_error<=2e-6
    baseline_record={'commit':BASELINE,'source_zip_sha256':sha(archive),'exit_code':old.returncode,
                     'dry_only_max_error':old_error,'new_route_gain':.675,'old_ignored_field_gain':.5}
    assert frozen()==before
    files=[{'path':p.relative_to(output).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(output.rglob('*')) if p.is_file()]
    record={'status':'passed_scoped_audio_routing','checked_at_utc':datetime.now(timezone.utc).isoformat(),'native_windows':sys.platform=='win32',
            'virtualization':False,'network_used':False,'seconds':time.monotonic()-started,'frozen_before':before,'frozen_after':frozen(),
            'cases':records,'cli_calls':calls,'baseline_control':baseline_record,'files':files,
            'review':{'decoded_all_output_samples':True,'continuous_playback':False,'human_listening':False,
                      'preview_waveform_is_evidence_wrapper':True,'natural_voice_or_capcut_parity_accepted':False}}
    save(output/'verification.json',record)
    print(json.dumps({'status':record['status'],'cases':len(records),'cli_calls':len(calls),'max_error':max(r['max_absolute_error'] for r in records)},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--work',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:run(args.work.resolve(),args.output.resolve())
    except BaseException as exc:
        args.output.mkdir(parents=True,exist_ok=True)
        save(args.output/'failure.json',{'type':type(exc).__name__,'message':str(exc),'at_utc':datetime.now(timezone.utc).isoformat()})
        raise
