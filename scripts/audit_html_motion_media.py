"""Re-decode public HTML motion media, archives, hashes and cleanup receipts."""
from __future__ import annotations
import argparse, hashlib, json, subprocess, sys, zipfile
from datetime import datetime,timezone
from pathlib import Path
from fractions import Fraction

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'product/src'))
from ai_ad_editor.media import ffmpeg_path,ffprobe_path
from smoke_fragments import save,sha


def run(public,output):
    import numpy as np
    from PIL import Image
    assert not output.exists()
    verification=json.loads((public/'verification.json').read_text(encoding='utf-8'))
    assert verification['status']=='passed' and verification['source_frozen_equal']
    for name,item in verification['files'].items():
        path=public/name
        assert sha(path)==item['sha256'] and path.stat().st_size==item['bytes'],name
    media=[];archives=[];receipts=[]
    for path in sorted(public.rglob('*')):
        if path.suffix.lower() in {'.mp4','.mkv','.nut'}:
            probe=subprocess.run([ffprobe_path(),'-v','error','-count_frames','-show_streams','-show_format','-of','json',str(path)],capture_output=True,check=True)
            value=json.loads(probe.stdout);streams=[]
            for stream in value['streams']:
                kind=stream['codec_type'];index=stream['index'];entry={'kind':kind,'codec':stream['codec_name']}
                if kind=='video':
                    width,height=stream['width'],stream['height']
                    raw=subprocess.check_output([ffmpeg_path(),'-v','error','-i',str(path),'-map',f'0:{index}','-pix_fmt','rgba','-f','rawvideo','pipe:1'])
                    count=len(raw)//(width*height*4)
                    assert count==int(stream['nb_read_frames'])==24,(path,count)
                    assert Fraction(stream['avg_frame_rate'])==12
                    entry.update(width=width,height=height,frames=count,fps=stream['avg_frame_rate'],
                                 rgba_sha256='sha256:'+hashlib.sha256(raw).hexdigest(),pix_fmt=stream['pix_fmt'])
                elif kind=='audio':
                    raw=subprocess.check_output([ffmpeg_path(),'-v','error','-i',str(path),'-map',f'0:{index}','-f','f32le','pipe:1'])
                    samples=np.frombuffer(raw,'<f4');assert np.isfinite(samples).all() and not np.any(samples)
                    entry.update(sample_rate=int(stream['sample_rate']),channels=stream['channels'],
                                 sample_frames=len(samples)//stream['channels'],exact_silence=True)
                streams.append(entry)
            media.append({'path':path.relative_to(public).as_posix(),'sha256':sha(path),'bytes':path.stat().st_size,'streams':streams})
        if path.suffix.lower()=='.zip':
            with zipfile.ZipFile(path) as archive:
                assert archive.testzip() is None,path
                archives.append({'path':path.relative_to(public).as_posix(),'sha256':sha(path),'members':len(archive.infolist())})
    for path in sorted(public.glob('*-browser.json'))+sorted(public.glob('F*-failure.json')):
        value=json.loads(path.read_text(encoding='utf-8'))
        assert value['cleanup']['all_children_reaped'] and value['cleanup']['active_after_cleanup']==[],path
        if value['status']=='succeeded':
            assert value['worker']['cleanup']['browser_closed'] and value['worker']['cleanup']['pages_opened']==value['worker']['cleanup']['pages_closed']==3
            assert value['worker']['all_frame_orders_equal'] and value['encoded_clock']['all_frames_exact']
            assert len(value['worker']['frame_hashes'])==24
            assert [len(v['frames']) for v in value['worker']['verification']]==[24,24]
        receipts.append({'path':path.name,'status':value['status'],'cleanup':value['cleanup']})
    with Image.open(public/'comparison.gif') as image:
        durations=[]
        for i in range(image.n_frames):image.seek(i);image.load();durations.append(image.info['duration'])
        gif={'width':image.width,'height':image.height,'frames':image.n_frames,'duration_ms':sum(durations),'durations':durations}
        assert image.size==(960,180) and image.n_frames==12 and sum(durations)==1920,gif
    files={p.relative_to(public).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(public.rglob('*')) if p.is_file()}
    native_gif=None
    if (public/'native-comparison.gif').exists():
        with Image.open(public/'native-comparison.gif') as image:
            durations=[]
            for i in range(image.n_frames):image.seek(i);image.load();durations.append(image.info['duration'])
            native_gif={'width':image.width,'height':image.height,'frames':image.n_frames,'duration_ms':sum(durations)}
            assert image.size==(960,270) and image.n_frames==12 and sum(durations)==2000,native_gif
    record={'status':'passed','checked_at':datetime.now(timezone.utc).isoformat(),'generator_sha256':sha(Path(__file__)),
        'public_files':files,'file_count':len(files),'bytes':sum(i['bytes'] for i in files.values()),'media':media,
        'video_streams':sum(s['kind']=='video' for m in media for s in m['streams']),
        'audio_streams':sum(s['kind']=='audio' for m in media for s in m['streams']),
        'archives':archives,'browser_receipts':receipts,'gif':gif,'native_gif':native_gif,'continuous_playback':False,'listening':False}
    save(output,record);print(json.dumps({k:record[k] for k in ('file_count','bytes','video_streams','audio_streams','gif')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--public',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.public.resolve(),args.output.resolve())
