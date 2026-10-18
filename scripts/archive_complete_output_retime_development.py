"""Preserve all pre-release retime media/receipts before moving duplicate trees to local runtime."""
from __future__ import annotations
from datetime import datetime,timezone
import hashlib,json,subprocess,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'docs/validation/evidence/retime-edits-20261019-v57'
NAMES=['retime-'+x+'-20261019-v57' for x in ('first','second','third','fourth','fifth','final')]
def digest(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()
def sha(path):return digest(path.read_bytes())

def run():
    import numpy as np
    destination=EVIDENCE/'development';destination.mkdir(exist_ok=False)
    target=ROOT/'product/.runtime/retime-preserved-development';target.mkdir(exist_ok=False)
    public=(ROOT/'docs/assets').resolve();root=ROOT.resolve();runtime=(ROOT/'product/.runtime').resolve()
    archive=destination/'pre-release-runs.zip';files=[];runs=[]
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name in NAMES:
            path=(public/name).resolve(strict=True)
            assert path.parent==public and path.is_relative_to(root)
            record=json.loads((path/('failure.json' if (path/'failure.json').exists() else 'verification.json')).read_bytes())
            runs.append({'path':path.relative_to(ROOT).as_posix(),'status':'failed' if 'error' in record else 'passed_timing_small_subtitle_preview',
                'error':record.get('error'),'completed_cases':len(record.get('completed_cases',record.get('cases',[])))})
            for p in sorted(path.rglob('*')):
                if not p.is_file():continue
                raw=p.read_bytes();member=p.relative_to(ROOT).as_posix();z.writestr(member,raw)
                files.append({'member':member,'bytes':len(raw),'sha256':digest(raw)})
        # The pre-fix renderer and clock are exact original bytes, verified
        # against the retained failing run's own source-freeze receipt.
        failed=json.loads((public/NAMES[1]/'failure.json').read_bytes())['source_freeze']
        for name in ('render.py','time_mapping.py'):
            path='product/src/ai_ad_editor/'+name
            raw=subprocess.check_output(['git','show','HEAD:'+path],cwd=ROOT)
            candidates=[raw,raw.replace(b'\r\n',b'\n'),raw.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')]
            raw=next(v for v in candidates if digest(v)==failed[path])
            member='source-before-native-tempo-fix/'+name;z.writestr(member,raw)
            files.append({'member':member,'bytes':len(raw),'sha256':digest(raw)})
        probe=ROOT/'product/.runtime/retime-smoke-fourth-20261019-v57/RT06/renders/author-probe.mkv'
        raw=probe.read_bytes();member='probes/author-probe.mkv';z.writestr(member,raw)
        files.append({'member':member,'bytes':len(raw),'sha256':digest(raw)})
    with zipfile.ZipFile(archive) as z:
        assert len(z.namelist())==len(files)
        for row in files:
            raw=z.read(row['member']);assert len(raw)==row['bytes'] and digest(raw)==row['sha256']
    def pcm(path):return np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-vn','-f','f32le','pipe:1']),dtype='<f4')
    probe_pcm=pcm(probe);before_pcm=pcm(public/NAMES[3]/'RT06-before.mkv')[:len(probe_pcm)]
    assert probe_pcm.tobytes()==before_pcm.tobytes()
    record={'status':'preserved_and_verified','checked_at_utc':datetime.now(timezone.utc).isoformat(),
        'generator_sha256':sha(Path(__file__)),'archive':archive.name,'archive_sha256':sha(archive),
        'runs':runs,'files':files,'author_probe':{'stereo_sample_frames':len(probe_pcm)//2,
            'decoded_pcm_sha256':digest(probe_pcm.tobytes()),'max_pcm_difference':0},
        'scope':'failed runs and first passed small-subtitle demonstration; not added to final acceptance counts'}
    (destination/'index.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    for name in NAMES:
        source=(public/name).resolve(strict=True);dest=(target/name).resolve()
        assert source.parent==public and source.is_relative_to(root)
        assert dest.parent==target.resolve() and dest.is_relative_to(runtime) and not dest.exists()
        source.rename(dest)
    print(json.dumps({'runs':len(runs),'files':len(files),'archive_bytes':archive.stat().st_size,'author_probe_pcm_difference':0}))

if __name__=='__main__':run()
