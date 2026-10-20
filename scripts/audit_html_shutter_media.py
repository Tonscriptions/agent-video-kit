"""Probe every public native/installed shutter movie and retain actual media facts."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import subprocess

from PIL import Image
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]


def digest(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets',action='append',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--expected-video-probes',type=int,required=True)
    args=parser.parse_args();output=args.output.resolve()
    assert output.is_relative_to(ROOT/'docs') and not output.exists()
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),'script_sha256':digest(Path(__file__)),
            'frozen_before':frozen(),'files':[],'actual_video_probes':0,'quality_accepted':False,
            'continuous_playback_reviewed':False,'audio_listening_reviewed':False,'virtualization':False}
    try:
        for asset in args.assets:
            folder=asset.resolve(strict=True);assert folder.is_relative_to(ROOT/'docs/assets')
            for path in sorted(folder.rglob('*')):
                if not path.is_file():continue
                row={'path':path.relative_to(ROOT).as_posix(),'bytes':path.stat().st_size,'sha256':digest(path)}
                if path.suffix in {'.nut','.mp4'}:
                    result=subprocess.run(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-show_frames',
                                           '-of','json',str(path)],check=True,capture_output=True,timeout=120)
                    probe=json.loads(result.stdout)
                    videos=[s for s in probe['streams'] if s['codec_type']=='video'];assert len(videos)==1
                    video=videos[0];frames=[f for f in probe['frames'] if f['media_type']=='video']
                    assert len(frames)==16 and int(video['nb_read_frames'])==16 and Fraction(video['avg_frame_rate'])==8
                    assert video['height']==180 and video['width']==(960 if path.name=='comparison.mp4' else 320)
                    timebase=Fraction(video['time_base']);assert all(int(f['pts'])*timebase==Fraction(i,8) for i,f in enumerate(frames))
                    assert not any(s['codec_type']=='audio' for s in probe['streams'])
                    receipt=output.parent/(output.stem+'-'+path.parent.name+'-'+path.stem+'-ffprobe.json')
                    assert not receipt.exists();receipt.write_bytes(result.stdout)
                    row.update(video={'width':video['width'],'height':video['height'],'fps':video['avg_frame_rate'],
                              'decoded_frames':len(frames),'frame_grid_coverage_seconds':'2','time_base':video['time_base'],
                              'codec':video['codec_name'],'pixel_format':video['pix_fmt'],
                              'reported_container_duration':probe['format'].get('duration'),
                              'all_pts_exact':True,'audio_streams':0},probe_path=receipt.relative_to(ROOT).as_posix(),probe_sha256=digest(receipt))
                    record['actual_video_probes']+=1
                elif path.suffix in {'.png','.gif'}:
                    with Image.open(path) as image:
                        row.update(image={'width':image.width,'height':image.height,'frames':getattr(image,'n_frames',1)})
                        if path.suffix=='.gif':
                            durations=[]
                            for index in range(image.n_frames):image.seek(index);durations.append(image.info['duration'])
                            assert len(durations)==16 and sum(durations)==2000
                            row['image']['duration_ms']=durations
                        else:assert image.size==(960,540)
                record['files'].append(row)
        assert record['actual_video_probes']==args.expected_video_probes
        record.update(status='passed',public_file_count=len(record['files']))
    except BaseException as exc:
        record.update(status='failed',error={'type':type(exc).__name__,'message':str(exc)})
        raise
    finally:
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),frozen_after=frozen())
        record['frozen_equal']=record['frozen_before']==record['frozen_after']
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    assert record['frozen_equal']
    print(json.dumps({key:record[key] for key in ('status','public_file_count','actual_video_probes','frozen_equal')}))


if __name__=='__main__':main()
