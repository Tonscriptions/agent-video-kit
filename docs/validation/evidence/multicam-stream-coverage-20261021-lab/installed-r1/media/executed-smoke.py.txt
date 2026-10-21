"""Actual local CLI camera coverage, complete lossless frames/PCM, MP4 and GIF."""
from __future__ import annotations
import argparse
from array import array
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time
from PIL import Image, ImageDraw
from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
W, H, TPS = 320, 180, 90000


def sha(path):
    with Path(path).open('rb') as stream:
        return 'sha256:' + hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')


def draw_counter(draw, number, x, y, scale=4):
    # Original seven-segment rectangle drawings; no font or external image.
    active = ('abcdef', 'bc', 'abdeg', 'abcdg', 'bcfg', 'acdfg', 'acdefg', 'abc', 'abcdefg', 'abcdfg')
    shapes = {'a': (1,0,5,1), 'b': (5,1,6,5), 'c': (5,6,6,10), 'd': (1,10,5,11),
        'e': (0,6,1,10), 'f': (0,1,1,5), 'g': (1,5,5,6)}
    for place, digit in enumerate(f'{number:02d}'):
        for segment in active[int(digit)]:
            left, top, right, bottom = shapes[segment]
            dx = x + place * 8 * scale
            draw.rectangle((dx + left*scale, y + top*scale, dx + right*scale-1, y + bottom*scale-1), fill=(235,245,255,255))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('work', 'evidence', 'assets'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--installed', type=Path)
    args = parser.parse_args()
    work, evidence, assets = (getattr(args, name).resolve() for name in ('work', 'evidence', 'assets'))
    assert work.is_relative_to(ROOT / 'product/.runtime')
    assert evidence.is_relative_to(ROOT / 'docs/validation') and assets.is_relative_to(ROOT / 'docs/assets')
    assert not any(path.exists() for path in (work, evidence, assets))
    for path in (work, evidence, assets):
        path.mkdir(parents=True)
    (evidence / 'executed-smoke.py.txt').write_bytes(Path(__file__).read_bytes())
    record = {'status': 'running', 'started_at_utc': datetime.now(timezone.utc).isoformat(),
        'native_windows': sys.platform == 'win32', 'virtualization': False, 'network': False,
        'frozen_before': frozen(), 'calls': [], 'checks': [], 'media': {},
        'continuous_playback_reviewed': False, 'audio_listened': False, 'full_capcut_parity': False}
    def save(): write(evidence / 'verification.json', record)
    def check(name, condition, **details):
        record['checks'].append({'name': name, 'ok': bool(condition), **details})
        save()
        assert condition, name
    temp = ROOT / 'product/.runtime/temp'
    temp.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, TEMP=str(temp), TMP=str(temp), TMPDIR=str(temp), PYTHONDONTWRITEBYTECODE='1')
    bootstrap = ('import sys;sys.path.insert(0,sys.argv.pop(1));'
        'from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();'
        'from ai_ad_editor.cli import main;raise SystemExit(main())')
    prefix = ([sys.executable, '-I', '-S', '-B', '-X', 'utf8', args.installed.resolve() / 'run.py'] if args.installed else
              [sys.executable, '-E', '-B', '-X', 'utf8', '-c', bootstrap, ROOT / 'product/src'])
    prefix = list(map(str, prefix))
    def run(label, command, data=None, expected=0, binary=False, cli=False):
        command = list(map(str, command))
        started = time.monotonic()
        result = subprocess.run(command, input=data, capture_output=True, cwd=ROOT, env=env, timeout=600)
        (evidence / (label + '.stderr.log')).write_bytes(result.stderr)
        digest = 'sha256:' + hashlib.sha256(result.stdout).hexdigest()
        if binary:
            write(evidence / (label + '.stdout-summary.json'), {'bytes': len(result.stdout), 'sha256': digest})
        else:
            (evidence / (label + '.stdout.log')).write_bytes(result.stdout)
        record['calls'].append({'label': label, 'command': command, 'exit_code': result.returncode,
            'expected_exit_code': expected, 'wall_seconds': time.monotonic() - started,
            'stdout_sha256': digest, 'cli': cli})
        save()
        assert result.returncode == expected, label + ': ' + (result.stderr + result.stdout)[-1600:].decode('utf8', 'replace')
        return result.stdout
    def cli(label, *argv, expected=0):
        return json.loads(run(label, [*prefix, *argv], expected=expected, cli=True))
    exe, probe = shutil.which('ffmpeg'), shutil.which('ffprobe')
    assert exe and probe
    record.update(ffmpeg={'path': exe, 'sha256': sha(exe)}, ffprobe={'path': probe, 'sha256': sha(probe)})
    def video(label, path):
        return run(label, [exe, '-v', 'error', '-i', path, '-map', '0:v:0', '-an', '-fps_mode', 'passthrough',
            '-f', 'rawvideo', '-pix_fmt', 'rgba', 'pipe:1'], binary=True)
    def audio(label, path):
        return run(label, [exe, '-v', 'error', '-i', path, '-map', '0:a:0', '-vn', '-ar', '48000', '-ac', '2',
            '-f', 'f32le', '-c:a', 'pcm_f32le', 'pipe:1'], binary=True)
    def gif(path, raw):
        size = W * H * 4
        assert len(raw) % size == 0
        frames = [Image.frombytes('RGBA', (W, H), raw[index:index + size]).convert('RGB') for index in range(0, len(raw), size)]
        frames[0].save(path, save_all=True, append_images=frames[1:], duration=40, loop=0, disposal=2, optimize=False)
        with Image.open(path) as image:
            total = 0
            for index in range(image.n_frames):
                image.seek(index)
                total += image.info.get('duration', 0)
            return {'frames': image.n_frames, 'duration_ms': total, 'actual_mp4_decode': path.stem.endswith(('-trim', '-stretch'))}
    try:
        audited = json.loads((ROOT/'docs/validation/evidence/multicam-stream-coverage-20261021-lab/development-audit-r1.json').read_bytes())
        assert record['frozen_before'] == audited['frozen_inputs'] and len(record['frozen_before']) == 258
        own_sha = sha(__file__)
        record.update(script_sha256=own_sha, expected_cases=['tail', 'leading'], source_resources=161)
        cards = []
        for index in range(50):
            image = Image.new('RGBA', (W,H), (30+index*3,50+index*2,220-index*3,255))
            draw = ImageDraw.Draw(image)
            draw.rectangle((14,24,306,151),fill=(12,18,29,255))
            draw_counter(draw,index,100,47,scale=7)
            draw.rectangle((22,137,22+index*5,143),fill=(70,220,160,255))
            for bit in range(6):
                draw.rectangle((22+bit*12,32,29+bit*12,39),fill=(240,195,70,255) if index&(1<<bit) else (35,48,65,255))
            cards.append(image)
        size = W*H*4
        raw = b''.join(image.tobytes() for image in cards)
        rng = random.Random(62731)
        gains = [.1+.75*rng.random() for _ in range(100)]
        pcm = array('f')
        for sample in range(96000):
            gain = gains[sample//960]
            pcm.extend((gain*math.sin(2*math.pi*433*sample/48000),gain*math.sin(2*math.pi*739*sample/48000)))
        raw_audio = work/'original.f32le'
        raw_audio.write_bytes(pcm.tobytes())
        reference = assets/'source-reference.mkv'
        run('generate-reference',[exe,'-v','error','-filter_threads','1','-f','rawvideo','-pixel_format','rgba',
            '-video_size',f'{W}x{H}','-framerate','25','-i','pipe:0','-f','f32le','-ar','48000','-ac','2','-i',raw_audio,
            '-map','0:v','-map','1:a','-c:v','ffv1','-pix_fmt','bgra','-c:a','pcm_f32le',reference],raw)
        check('generated-reference-full-RGBA',video('decode-reference',reference)==raw,frames=50,bytes=len(raw))
        check('generated-reference-full-PCM',audio('decode-reference-PCM',reference)==pcm.tobytes(),bytes=len(pcm.tobytes()))
        discovery = cli('capabilities','capabilities')['data']['capabilities']['media']['multicam_source_coverage']
        check('native-coverage-and-audio-only-contract-discoverable',discovery['version']=='0.3.0'
            and discovery['coverage_clock']=='native-video-first-last-intervals-v1'
            and discovery['source_shortfall_default']=='reject'
            and discovery['unknown_video_coverage_contract']=='return_audio_only_sync_with_diagnostics_but_refuse_camera_switch_authoring')
        record['cases'] = {}
        record['GIF'] = {'source-reference':gif(assets/'source-reference.gif',raw)}
        source_descriptions = []
        for case,first,last,first_seconds,end_seconds in (('tail',0,8,0.,.32),('leading',25,33,1.,1.32)):
            camera = assets/('source-'+case+'.mkv')
            run(case+'-generate-camera',[exe,'-v','error','-filter_complex_threads','1','-i',reference,'-filter_complex',
                f'[0:v]trim=start_frame={first}:end_frame={last},setpts=PTS[v]',
                '-map','[v]','-map','0:a','-c:v','ffv1','-pix_fmt','bgra','-c:a','copy',camera])
            selected = b''.join(image.tobytes() for image in cards[first:last])
            check(case+'-generated-video-eight-native-frames',video(case+'-decode-source',camera)==selected,frames=8)
            check(case+'-generated-audio-keeps-two-seconds',audio(case+'-decode-source-PCM',camera)==pcm.tobytes(),samples_per_channel=96000)
            measured = json.loads(run(case+'-probe-source-PTS',[probe,'-v','error','-select_streams','v:0','-show_frames','-show_streams','-show_format',
                '-show_entries','frame=pts,duration:stream=time_base:format=start_time,duration','-of','json',camera]))
            tb = Fraction(measured['streams'][0]['time_base'])
            frames = measured['frames']
            native_first = int(frames[0]['pts'])*tb
            native_end = (int(frames[-1]['pts'])+int(frames[-1]['duration']))*tb
            check(case+'-independent-native-PTS-and-long-container',native_first==Fraction(first,25)
                and native_end==Fraction(last,25) and Fraction(measured['format']['duration'])==2,
                first=str(native_first),end=str(native_end),container=measured['format']['duration'])
            record['GIF']['source-'+case] = gif(assets/('source-'+case+'.gif'),selected)
            project = work/('project-'+case)
            cli(case+'-project-init','project','init',project)
            for asset_id,path in (('reference',reference),('camera',camera)):
                cli(case+'-ingest-'+asset_id,'media','ingest','--project',project,'--input',path,'--asset-id',asset_id,
                    '--source-url','local://multicam-native-coverage/original','--license-spdx','CC0-1.0',
                    '--license-url','local://multicam-native-coverage/CC0-1.0','--verification-status','verified',
                    '--permitted-use','commercial_ad','--creator','agent-video-kit',
                    '--evidence','Original seven-segment rectangle cards and deterministic synthesized stereo; no font, stock, model or remote source')
            p = json.loads((project/'project.json').read_bytes())
            p['settings']['canvas'] = {'width':W,'height':H,'background':'#000000'}
            p['settings']['timebase'] = {'ticks_per_second':TPS,'display_fps':{'num':25,'den':1}}
            write(project/'project.json',p)
            request = project/'master-audio.json'
            write(request,{'operations':[{'op':'append_clip','track_id':'track_audio_1','id':'master_audio',
                'asset_id':'reference','timeline_start_tick':0,'duration_tick':180000,'source_in_tick':0,'source_out_tick':180000},
                {'op':'set_sequence_duration','sequence_id':'seq_main','duration_tick':180000,'trim':False}]})
            cli(case+'-compose-master-audio','timeline','compose','--project',project,'--input',request)
            plan = project/'switch-plan.json'
            write(plan,[{'start_seconds':0.,'end_seconds':2.,'camera_asset_id':'camera'}])
            common = ('media','multicam','--project',project,'--source-asset-id','reference','--source-asset-id','camera',
                '--reference-asset-id','reference','--sample-rate','8000','--analysis-seconds','2','--max-offset-seconds','.4',
                '--switch-plan',plan,'--start-seconds','0','--end-seconds','2','--track-id','track_video_1','--output',project/'validation/coverage.json')
            def files():
                return {path.relative_to(project).as_posix():sha(path) for path in project.rglob('*') if path.is_file()}
            before = files()
            for label,options in (('default-dry',('--dry-run',)),('default-apply',('--apply','--replace-track'))):
                value = cli(case+'-'+label,*common,*options,expected=2)
                check(case+'-'+label+'-refuses-real-video-shortfall',value['errors'][0]['code']=='MULTICAM_SOURCE_SHORTFALL')
                check(case+'-'+label+'-no-author-report-cache-or-snapshot-write',files()==before)
            dry = cli(case+'-trim-dry',*common,'--source-shortfall','trim','--dry-run')['data']['plan']
            row = dry['segments'][0]
            check(case+'-trim-native-window-at-unity',
                (row['source_in_seconds'],row['source_out_seconds'],row['timeline_start_seconds'],row['duration_seconds'],row['speed'])
                ==(first_seconds,end_seconds,first_seconds,.32,1.))
            check(case+'-trim-dry-no-writes',files()==before)
            camera_offset = next(item for item in dry['sync']['offsets'] if item['asset_id']=='camera')
            coverage = camera_offset['evidence']['video_coverage']
            check(case+'-audio-offset-and-native-coverage-evidence',camera_offset['relative_delay_seconds']==0.
                and coverage['status']=='known' and coverage['start_seconds_rational']==str(Fraction(first,25))
                and coverage['end_seconds_rational']==str(Fraction(last,25))
                and camera_offset['evidence']['duration_seconds']==2.,coverage=coverage)
            analysis = list(common)
            position = analysis.index('--switch-plan')
            del analysis[position:position+2]
            only = cli(case+'-audio-only-dry',*analysis,'--dry-run')['data']['plan']
            check(case+'-audio-only-sync-without-authoring',only['segments']==[] and not only['changed'] and files()==before)
            applied = cli(case+'-trim-apply',*common,'--source-shortfall','trim','--apply','--replace-track')['data']['plan']
            p = json.loads((project/'project.json').read_bytes())
            check(case+'-two-second-author-window-preserved',p['sequences'][0]['duration_tick']==180000)
            preview = cli(case+'-lossless-preview','preview','range','--project',project,'--start-frame','0','--end-frame','50','--height',H)['data']
            master = Path(preview['master'])
            shutil.copy2(master,assets/(case+'-trim-lossless.nut'))
            expected = bytes((0,0,0,255))*(W*H*first)+selected+bytes((0,0,0,255))*(W*H*(50-last))
            check(case+'-all-lossless-RGBA-and-both-gaps',video(case+'-decode-lossless',master)==expected,
                frames=50,bytes=len(expected),max_RGBA_error=0)
            check(case+'-complete-explicit-master-PCM',audio(case+'-decode-lossless-PCM',master)==pcm.tobytes(),
                bytes=len(pcm.tobytes()),samples_per_channel=96000)
            encoded_errors = {}
            for mode in ('trim','stretch'):
                if mode=='stretch':
                    stretched = cli(case+'-stretch-apply',*common,'--source-shortfall','stretch','--apply','--replace-track')['data']['plan']
                    check(case+'-explicit-stretch-changes-clock-with-warning',stretched['segments'][0]['speed']==.16
                        and any(item['code']=='MULTICAM_SOURCE_CLOCK_CHANGED' for item in stretched['warnings']))
                output = project/'renders'/(mode+'.mp4')
                rendered = cli(case+'-'+mode+'-render','render','--project',project,'--output',output,'--profile','custom',
                    '--width',W,'--height',H,'--crf','0','--pixel-format','yuv444p')['data']
                shutil.copy2(Path(rendered['manifest']),evidence/(case+'-'+mode+'-render-manifest.json'))
                shutil.copy2(output,assets/(case+'-'+mode+'.mp4'))
                encoded = video(case+'-'+mode+'-decode-encoded',output)
                check(case+'-'+mode+'-encoded-frame-count',len(encoded)==size*50,frames=50)
                measured = json.loads(run(case+'-'+mode+'-encoded-PTS',[probe,'-v','error','-select_streams','v:0',
                    '-show_frames','-show_streams','-show_entries','frame=pts,duration:stream=time_base','-of','json',output]))
                base = Fraction(measured['streams'][0]['time_base'])
                check(case+'-'+mode+'-all-encoded-PTS',[int(frame['pts'])*base for frame in measured['frames']]==[Fraction(i,25) for i in range(50)])
                if mode=='trim':
                    wanted = [(0,0,0) if index<first or index>=last else (30+index*3,50+index*2,220-index*3) for index in range(50)]
                    observed = [tuple(encoded[index*size:index*size+3]) for index in range(50)]
                    maximum = max(abs(a-b) for actual,target in zip(observed,wanted) for a,b in zip(actual,target))
                    check(case+'-trim-encoded-event-identity-patches',maximum<=2,observed_max_rgb_error=maximum,whole_encoded_RGBA_equality_claimed=False)
                    encoded_errors[mode] = maximum
                    sheet = Image.new('RGBA',(W*4,(H+20)*2),(12,18,29,255))
                    indices = (0,3,7,8,15,25,40,49) if case=='tail' else (0,24,25,28,32,33,45,49)
                    for cell,index in enumerate(indices):
                        x,y = (cell%4)*W,(cell//4)*(H+20)
                        draw_counter(ImageDraw.Draw(sheet),index,x+4,y+4,scale=1)
                        sheet.paste(Image.frombytes('RGBA',(W,H),encoded[index*size:(index+1)*size]),(x,y+20))
                    sheet.convert('RGB').save(assets/(case+'-boundaries.png'))
                else:
                    first_color = (30+first*3,50+first*2,220-first*3)
                    check(case+'-stretch-starts-source-immediately',max(abs(a-b) for a,b in zip(encoded[:3],first_color))<=2)
                record['GIF'][case+'-'+mode] = gif(assets/(case+'-'+mode+'.gif'),encoded)
            helper = ('import sys,json;from pathlib import Path;sys.path.insert(0,sys.argv[1]);'
                'from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();'
                'from ai_ad_editor.project import load_project;from ai_ad_editor.native_video_index import IndexContext;'
                'from ai_ad_editor.reverse_video_clock import probe_frames;root,p=load_project(sys.argv[2]);'
                'context=IndexContext(root,persist=True);rows=[];'
                '\nfor a in p["assets"]:\n if a["kind"]=="video":\n  path=Path(a["uri"]);path=path if path.is_absolute() else root/path;rows.append(context.acquire(path,a["sha256"],probe_frames)[-1])\n'
                'print(json.dumps(rows))')
            helper_flags = ['-I','-S','-B','-X','utf8'] if args.installed else ['-E','-B','-X','utf8']
            site = args.installed.resolve()/'site' if args.installed else ROOT/'product/src'
            indexes = json.loads(run(case+'-explicit-index-materialization',[sys.executable,*helper_flags,'-c',helper,site,project]))
            check(case+'-two-owned-source-indexes-materialized',len(indexes)==2)
            before_hit = files()
            hit = cli(case+'-cache-hit-dry',*common,'--source-shortfall','trim','--dry-run')['data']['plan']
            check(case+'-read-only-cache-hits-skip-source-frame-probes',all(
                (item['evidence']['video_coverage']['native_index']['status'],item['evidence']['video_coverage']['native_index']['source_index_decode_calls'])
                ==('cache-hit',0) for item in hit['sync']['offsets']) and files()==before_hit)
            pts_path = (Path(indexes[0]['path'])/'pts.i64le').resolve()
            assert pts_path.is_relative_to(project/'cache/native-video-index')
            original = pts_path.read_bytes()
            damaged = bytearray(original)
            damaged[0] ^= 1
            pts_path.write_bytes(damaged)
            before_bad = files()
            rejected = cli(case+'-corrupt-index-refusal',*common,'--source-shortfall','trim','--dry-run',expected=6)
            check(case+'-corrupt-index-refuses-and-preserves-author-and-evidence',rejected['errors'][0]['code']=='NATIVE_INDEX_CORRUPT' and files()==before_bad)
            pts_path.write_bytes(original)
            check(case+'-only-explicit-owner-restores-test-corruption',files()==before_hit)
            cli(case+'-restored-index-dry',*common,'--source-shortfall','trim','--dry-run')
            record['cases'][case] = {'container_seconds':2,'native_video_range_seconds':[first_seconds,end_seconds],
                'reference_frame_ids':list(range(first,last)),'audio_delay_seconds':0,'trim_speed':1,
                'leading_gap_frames':first,'trailing_gap_frames':50-last,'lossless_frames':50,
                'lossless_RGBA_bytes':len(expected),'lossless_PCM_bytes':len(pcm.tobytes()),'samples_per_channel':96000,
                'stretch_speed':.16,'stretch_event_sync_preserved':False,'encoded_trim_patch_max_error':encoded_errors['trim']}
            source_descriptions.append({'case':case,'video_frames':8,'video_native_range_seconds':[first_seconds,end_seconds],
                'container_and_audio_seconds':2,'raw_decoded_source_GIF_ms':320,'source_file':camera.name,'source_sha256':sha(camera)})
        write(assets/'source-origin.json',{'license':'CC0-1.0','creator':'agent-video-kit','original_generated_media':True,
            'font_or_external_image_used':False,'reference_frames':50,'fps':25,'stereo_sample_rate':48000,
            'generator_sha256':own_sha,'sources':source_descriptions,'continuous_playback_reviewed':False,'audio_listened':False,
            'note':'Raw source GIFs show only the eight decoded video frames; actual native PTS and the two-second audio remain in original MKVs.'})
        record['media'] = {path.relative_to(ROOT).as_posix():{'sha256':sha(path),'bytes':path.stat().st_size}
            for path in sorted(assets.iterdir()) if path.is_file()}
        check('smoke-script-unchanged',sha(__file__)==own_sha)
        record.update(status='passed',installed=bool(args.installed),unknown_EOF_media_case_claimed=False)
    except BaseException as error:
        record.update(status='failed',error={'type':type(error).__name__,'message':str(error)})
        raise
    finally:
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),frozen_after=frozen())
        record['frozen_equal'] = record['frozen_before']==record['frozen_after']
        record['cli_calls'] = sum(bool(row['cli']) for row in record['calls'])
        record['native_commands'] = sum(not row['cli'] for row in record['calls'])
        save()
        print(json.dumps({k:record.get(k) for k in ('status','cli_calls','native_commands','frozen_equal','error')},ensure_ascii=False),flush=True)
    assert record['frozen_equal']


if __name__=='__main__':
    main()
