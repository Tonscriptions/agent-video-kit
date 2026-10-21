"""Pin actual original/failed/native/installed assets and decoded container/GIF structure."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'docs/assets/audio-discontinuity-20261021-lab'
REL=ROOT/'docs/validation/evidence/audio-discontinuity-20261021-lab'
def sha(path):
    with path.open('rb') as stream:return 'sha256:'+hashlib.file_digest(stream,'sha256').hexdigest()
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--revision',required=True)
    parser.add_argument('--installed-evidence',type=Path,default=REL/'installed-r1/verification.json');args=parser.parse_args()
    output=REL/('media-manifest-'+args.revision+'.json');assert not output.exists()
    development=json.loads((REL/'native-r1/verification.json').read_bytes());installed=json.loads(args.installed_evidence.read_bytes())
    assert development['status']==installed['status']=='passed'
    probe=shutil.which('ffprobe');assert probe
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),'assets':{},'commands':[],
        'script_sha256':sha(Path(__file__)),'probe':{'path':probe,'sha256':sha(Path(probe))},
        'native_windows':True,'virtualization':False,'network':False,
        'rights':'Original deterministic CC0 PCM and font-free geometric video; failed and diagnostic assets labelled separately.',
        'audio_listened':False,'continuous_playback_reviewed':False,'natural_quality_accepted':False,'full_capcut_parity':False}
    def save():output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    save();output.with_suffix('.script.py.txt').write_bytes(Path(__file__).read_bytes())
    for path in sorted(ASSETS.rglob('*')):
        if not path.is_file():continue
        relative=path.relative_to(ROOT).as_posix();parts=path.relative_to(ASSETS).parts
        role=('preserved-published-V90-failed-output' if path.name.startswith('before-') else 'diagnostic-derived-from-actual-PCM' if path.name.startswith('actual-PCM-comparison')
            else 'fresh-installed-output' if parts[0].startswith('installed-') else 'independent-author-reference' if 'author-placed' in path.name
            else 'actual-codec-decoding-reference' if 'actual-decoded' in path.name else 'original-or-original-browser-copy' if parts[0].startswith(('original','extra-original','quantized-original')) or path.name.startswith('original') else 'native-candidate-output')
        item={'bytes':path.stat().st_size,'sha256':sha(path),'role':role}
        if path.suffix.lower() in {'.nut','.mkv','.mp4','.m4a'}:
            command=[probe,'-v','error','-count_frames','-show_streams','-show_format','-show_entries',
                'format=format_name,start_time,duration:stream=codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,sample_rate,channels,nb_read_frames','-of','json',str(path)]
            result=subprocess.run(command,capture_output=True,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
            record['commands'].append({'command':command,'exit_code':result.returncode,'stdout_sha256':'sha256:'+hashlib.sha256(result.stdout).hexdigest(),'stderr':result.stderr.decode('utf8','replace')[-2000:]})
            assert result.returncode==0,(path,result.stderr);item['actual_probe']=json.loads(result.stdout)
        elif path.suffix.lower()=='.gif':
            with Image.open(path) as image:
                durations=[]
                for i in range(image.n_frames):image.seek(i);durations.append(image.info.get('duration',0))
                item['actual_GIF']={'frames':image.n_frames,'width':image.width,'height':image.height,'frame_durations_ms':durations,'total_duration_ms':sum(durations)}
                assert all(value==40 for value in durations)
        elif path.suffix.lower()=='.png':
            with Image.open(path) as image:item['actual_image']={'width':image.width,'height':image.height,'format':image.format}
        elif path.suffix.lower()!='.f32':raise AssertionError(('unexpected asset type',path))
        record['assets'][relative]=item;save()
    record.update(status='passed-actual-media-inventory',asset_count=len(record['assets']),GIF_count=sum('actual_GIF' in item for item in record['assets'].values()),
        native_probe_commands=len(record['commands']),finished_at_utc=datetime.now(timezone.utc).isoformat());save()
    print(json.dumps({k:record[k] for k in ('status','asset_count','GIF_count','native_probe_commands')}))
if __name__=='__main__':main()
