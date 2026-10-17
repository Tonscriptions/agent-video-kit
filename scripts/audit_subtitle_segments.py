"""Re-decode published subtitle media and check authored text/tick evidence."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile


def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def run(folder,report):
    import numpy as np
    from PIL import Image
    def load(path):return json.loads(path.read_text(encoding='utf-8'))
    verification=load(folder/'verification.json')
    for name,record in verification['files'].items():
        path=folder/name
        assert path.stat().st_size==record['bytes'] and sha(path)==record['sha256'],name
    video,audio={},{}
    rgb_cache,pcm_cache={},{}
    for path in sorted(folder.iterdir()):
        if path.suffix not in {'.mp4','.wav'}:continue
        meta=json.loads(subprocess.run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)],capture_output=True,check=True).stdout)
        streams=meta['streams']
        v=next((s for s in streams if s['codec_type']=='video'),None)
        a=next((s for s in streams if s['codec_type']=='audio'),None)
        if v:
            raw=subprocess.run(['ffmpeg','-v','error','-i',str(path),'-an','-pix_fmt','rgb24','-f','rawvideo','pipe:1'],capture_output=True,check=True).stdout
            pixels=int(v['width'])*int(v['height'])*3
            assert len(raw)%pixels==0 and len(raw)//pixels==48,path
            video[path.name]={'width':v['width'],'height':v['height'],'frames':len(raw)//pixels,'fps':v['avg_frame_rate'],
                              'rgb_sha256':'sha256:'+hashlib.sha256(raw).hexdigest(),'sha256':sha(path)}
            rgb_cache[path.name]=video[path.name]['rgb_sha256']
        if a:
            raw=subprocess.run(['ffmpeg','-v','error','-i',str(path),'-vn','-ac','2','-ar','48000','-f','f32le','pipe:1'],capture_output=True,check=True).stdout
            values=np.frombuffer(raw,dtype='<f4')
            assert len(raw)%8==0 and np.isfinite(values).all()
            audio[path.name]={'sample_rate':48000,'channels':2,'sample_frames':len(raw)//8,
                              'pcm_sha256':'sha256:'+hashlib.sha256(raw).hexdigest(),'peak':float(np.abs(values).max())}
            pcm_cache[path.name]=audio[path.name]['pcm_sha256']
    assert len(video)==14 and len(audio)==14
    assert 'comparison.mp4' not in audio
    cue_checks=[]
    for n in range(1,5):
        cid=f'S{n:02}'
        assert rgb_cache[f'{cid}-segmented.mp4']==rgb_cache[f'{cid}-reference.mp4']
        assert pcm_cache[f'{cid}-segmented.mp4']==pcm_cache[f'{cid}-whole-line.mp4']
        expected=load(folder/f'{cid}-expected.json')
        raw=(folder/f'{cid}-actual.srt').read_text(encoding='utf-8')
        actual=[]
        for block in re.split(r'\n\s*\n',raw.strip()):
            lines=block.splitlines()
            match=re.fullmatch(r'(\d+):(\d+):(\d+),(\d+) --> (\d+):(\d+):(\d+),(\d+)',lines[1])
            assert match,block
            parts=list(map(int,match.groups()))
            clocks=[((parts[i]*60+parts[i+1])*60+parts[i+2])*1000+parts[i+3] for i in (0,4)]
            actual.append({'text':'\n'.join(lines[2:]),'milliseconds':clocks})
        predicted=[{'text':text,'milliseconds':[(a*2000+90000)//180000,(b*2000+90000)//180000]} for text,(a,b) in zip(expected['texts'],expected['intervals'])]
        assert actual==predicted,(cid,actual,predicted)
        plan=load(folder/f'{cid}-actual-plan.json')
        assert {p['timing_basis'] for p in plan['pieces']}=={'provided-onsets-with-weighted-interiors'}
        for line in plan['source']['lines']:
            at=0
            for p in [p for p in plan['pieces'] if p['line_id']==line['id']]:
                assert not line['text'][at:p['from']].strip()
                assert line['text'][p['from']:p['to']]==p['text']
                at=p['to']
            assert not line['text'][at:].strip()
        cue_checks.append({'case':cid,'cue_count':len(actual),'literal_srt_matches_authored_text_ticks':True})
    calls=load(folder/'cli-calls.json')
    with zipfile.ZipFile(folder/'cli-logs.zip') as archive:
        assert len(archive.namelist())==2*len(calls)
        for call in calls:
            for suffix,key in [('stdout.json','stdout_sha256'),('stderr.log','stderr_sha256')]:
                data=archive.read(f'{call["index"]:03}.{suffix}')
                assert 'sha256:'+hashlib.sha256(data).hexdigest()==call[key]
            response=json.loads(archive.read(f'{call["index"]:03}.stdout.json'))
            assert response['ok']==(call['exit_code']==0)
    gif=Image.open(folder/'comparison.gif');durations=[]
    for i in range(gif.n_frames):
        gif.seek(i);durations.append(gif.info.get('duration',0))
    assert gif.n_frames==48 and sum(durations)==24000 and gif.size==(960,302)
    inventory={p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(folder.iterdir()) if p.is_file()}
    assert not any(Path(name).suffix.lower() in {'.ttf','.otf','.ttc'} for name in inventory)
    record={'checked_at_utc':datetime.now(timezone.utc).isoformat(),'status':'passed','video_files':len(video),'audio_streams':len(audio),
            'all_decoded_video_frames':sum(v['frames'] for v in video.values()),'all_decoded_audio_sample_frames':sum(v['sample_frames'] for v in audio.values()),
            'video':video,'audio':audio,'cue_checks':cue_checks,'cli_calls':len(calls),'cli_logs_verified':2*len(calls),
            'gif':{'frames':gif.n_frames,'duration_ms':sum(durations),'width':gif.width,'height':gif.height,'audio':False},
            'public_files':len(inventory),'public_bytes':sum(v['bytes'] for v in inventory.values()),'public_sha256':inventory,
            'limits':['manual reference uses same renderer','synthetic manual onsets, no speech','AAC decode includes encoder padding','continuous playback and listening not performed']}
    report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in record.items() if k not in {'video','audio','public_sha256','cue_checks'}},ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder',type=Path,required=True);parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args();run(args.folder.resolve(),args.report.resolve())
