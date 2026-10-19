"""Inventory public actual media and probe the selected V69 final examples."""
from __future__ import annotations
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import wave

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/local-face-beauty-20261020-v69'


def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    target=BASE/'media-inventory-r1.json'
    assert not target.exists()
    rows=[];probes=[]
    for folder in sorted((ROOT/'docs/assets').glob('local-face-beauty-20261020-v69-*')):
        for path in sorted(folder.rglob('*')):
            if path.is_file():rows.append({'path':path.relative_to(ROOT).as_posix(),'bytes':path.stat().st_size,'sha256':sha(path)})
    for folder in (ROOT/'docs/assets/local-face-beauty-20261020-v69-native-r5',
                   ROOT/'docs/assets/local-face-beauty-20261020-v69-installed-r1/media'):
        for name in ('source.mov','source.mp4','neutral.mkv','neutral.mp4','retouched.mkv','retouched.mp4','recipe-replay.mkv','recipe-replay.mp4','comparison.gif'):
            path=folder/name
            command=['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(path)]
            result=subprocess.run(command,capture_output=True,check=True,timeout=120)
            data=json.loads(result.stdout);video=next(s for s in data['streams'] if s['codec_type']=='video')
            expected=(960,420) if name.endswith('.gif') else (512,512)
            assert (video['width'],video['height'])==expected and int(video['nb_read_frames'])==24
            assert video['avg_frame_rate']=='8/1' and abs(float(data['format']['duration'])-3)<.02
            if name.endswith('.mkv'):
                assert video['pix_fmt']=='bgra' and video['color_transfer']=='iec61966-2-1' and video['color_space']=='gbr' and video['color_range']=='pc'
            if not name.endswith('.gif'):
                audio=[s for s in data['streams'] if s['codec_type']=='audio']
                assert len(audio)==1 and audio[0]['channels']==2 and audio[0]['sample_rate']=='48000'
            probes.append({'path':path.relative_to(ROOT).as_posix(),'sha256':sha(path),'command':command,
                           'exit_code':result.returncode,'stderr':result.stderr.decode('utf8',errors='replace'),'probe':data})
        with wave.open(str(folder/'source.wav'),'rb') as stream:
            assert (stream.getframerate(),stream.getnchannels(),stream.getnframes(),stream.getsampwidth())==(48000,2,144000,2)
    value={'status':'passed','checked_at_utc':datetime.now(timezone.utc).isoformat(),'generator_sha256':sha(Path(__file__)),
           'public_files':rows,'final_media_probes':probes,'quality_accepted':False,'continuous_playback_reviewed':False,'audio_listening_reviewed':False}
    target.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'status':'passed','public_files':len(rows),'ffprobe_calls':len(probes)}))


if __name__=='__main__':main()
