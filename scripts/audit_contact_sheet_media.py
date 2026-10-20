"""Inventory exact public V71 originals, contact sheets and install receipts."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from PIL import Image
from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/validation/evidence/contact-sheet-20261020-v71'


def read(path): return json.loads(path.read_bytes())
def sha(path): return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()
def save(path, data): path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); output = args.output.resolve()
    assert not output.exists(), 'retain earlier audit evidence'
    before = frozen(); assert len(before) == 217
    dev = read(BASE / 'native-r2/verification.json')
    install = read(BASE / 'installed-r2/verification.json')
    media = read(BASE / 'installed-r2/media/verification.json')
    for value in (dev, install, media):
        assert value['status'] == 'passed' and value['frozen_before'] == value['frozen_after'] == before
    record = {'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),
        'script_sha256':sha(Path(__file__)), 'native_windows':sys.platform=='win32',
        'virtualization':False,'browser':False,'model_forwards':0,'frozen_before':before,
        'videos':[],'files':[],'panels':[], 'continuous_playback_reviewed':False,
        'audio_listening_reviewed':False,'natural_quality_accepted':False,'full_capcut_parity':False}
    try:
        assets = ROOT / 'docs/assets/contact-sheet-20261020-v71-installed-r2'
        release = assets / 'release'; release.mkdir(exist_ok=True)
        copies = [(Path(install['bundle']['bundle'])/'manifest.json', release/'bundle-manifest.json'),
                  (Path(install['installation']['target'])/'receipt.json', release/'install-receipt.json')]
        for source, target in copies:
            if target.exists(): assert target.read_bytes() == source.read_bytes()
            else: shutil.copyfile(source, target)
        archive = Path(install['bundle']['archive'])
        archive_record = {'archive_name':archive.name, 'bytes':archive.stat().st_size, 'sha256':sha(archive),
            'manifest_sha256':install['bundle']['manifest_sha256'], 'wheels':7, 'product_resources':144,
            'archive_published':False, 'dependencies_not_bundled':['Python','FFmpeg','system DLLs']}
        assert archive_record['sha256'] == install['bundle']['archive_sha256']
        archive_path = release/'bundle-archive.json'
        if archive_path.exists(): assert read(archive_path) == archive_record
        else: save(archive_path, archive_record)
        assert sha(release/'bundle-manifest.json') == install['bundle']['manifest_sha256']
        binary = str(Path(shutil.which('ffprobe')).resolve()); record['ffprobe']={'path':binary,'sha256':sha(Path(binary))}
        for run in ('native-r2','installed-r2'):
            folder = ROOT / ('docs/assets/contact-sheet-20261020-v71-'+run)
            manifest = read(folder/'contact/manifest.json')
            assert manifest['contact']['width'] == 2560 and manifest['contact']['height'] == 444
            assert not manifest['quality_accepted'] and manifest['process_cleanup']['all_children_reaped']
            for rel in ('source.mkv','source-preview.mp4','source-alpha.webm'):
                path = folder/rel
                command = [binary,'-v','error','-protocol_whitelist','file,pipe','-count_frames',
                    '-show_entries','format=format_name,duration:stream=index,codec_type,codec_name,width,height,avg_frame_rate,nb_read_frames,channels,sample_rate:stream_tags=alpha_mode',
                    '-of','json',str(path)]
                result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
                assert result.returncode == 0, result.stderr.decode('utf8','replace')
                probe = json.loads(result.stdout); video = next(x for x in probe['streams'] if x['codec_type']=='video')
                assert (video['width'],video['height'],int(video['nb_read_frames'])) == (320,180,24)
                assert video['avg_frame_rate'] == '12/1'
                assert 1.99 <= float(probe['format']['duration']) <= 2.05
                assert any(s['codec_type']=='audio' and s.get('channels')==2 for s in probe['streams'])
                if rel.endswith('.webm'):
                    tags={k.lower():str(v) for k,v in video.get('tags',{}).items()}
                    assert tags.get('alpha_mode') == '1'
                record['videos'].append({'path':path.relative_to(ROOT).as_posix(), 'sha256':sha(path),
                    'command':command,'exit_code':result.returncode,'probe':probe})
            with Image.open(folder/'contact/contact.png') as image:
                sheet = image.convert('RGB')
                for row in manifest['frames']:
                    path = folder/'contact'/row['path']; assert sha(path) == row['png_sha256']
                    with Image.open(path) as image: frame = image.convert('RGBA')
                    assert 'sha256:'+hashlib.sha256(frame.tobytes()).hexdigest() == row['rgba_sha256']
                    alpha = frame.getchannel('A')
                    assert list(alpha.getextrema()) == row['alpha_extrema'] == [0,255]
                    assert 'sha256:'+hashlib.sha256(alpha.tobytes()).hexdigest() == row['alpha_sha256']
                    for panel in row['panels']:
                        x,y=panel['x'],panel['y']; crop=sheet.crop((x,y,x+panel['width'],y+panel['height']))
                        actual='sha256:'+hashlib.sha256(crop.tobytes()).hexdigest(); assert actual == panel['rgb_sha256']
                        record['panels'].append({'run':run,'frame_index':row['index'],'view':panel['view'],'rgb_sha256':actual})
            assert sha(folder/'contact/contact.png') == manifest['contact']['sha256']
            for path in sorted(folder.rglob('*')):
                if path.is_file(): record['files'].append({'path':path.relative_to(ROOT).as_posix(),'bytes':path.stat().st_size,'sha256':sha(path)})
        assert len(record['videos']) == 6 and len(record['files']) == 33 and len(record['panels']) == 32
        record.update(status='passed',public_file_count=33,actual_video_probes=6,panels_per_run=16)
    except BaseException as exc:
        record.update(status='failed',error={'type':type(exc).__name__,'message':str(exc)})
        raise
    finally:
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),frozen_after=frozen())
        record['frozen_equal']=record['frozen_after']==before; output.parent.mkdir(parents=True,exist_ok=True);save(output,record)
    assert record['frozen_equal']
    print(json.dumps({'status':record['status'],'files':len(record['files']),'video_probes':len(record['videos']),
        'panels_per_run':16,'frozen_equal':True}))


if __name__ == '__main__': main()
