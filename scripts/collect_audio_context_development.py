"""Preserve negative native probes and isolated development attempts, separately."""
from datetime import datetime,timezone
import gzip
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/audio-source-context-20261019-v64/development'
def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

def main():
    BASE.mkdir(parents=True,exist_ok=False);inventory=[];probes=[]
    for source in sorted((ROOT/'product/.runtime').glob('audio-source-context-20261019-v63-probe*')):
        out=BASE/source.name;out.mkdir()
        receipt=json.loads((source/'verification.json').read_bytes())
        probes.append({'folder':source.name,'native_cases':len(receipt['records']),'status':receipt['status'],
                       'verification_sha256':sha(source/'verification.json')})
        for p in source.iterdir():
            if not p.is_file():continue
            row={'source':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)}
            # Full expanded output can be 24 MiB each. Preserve exact selected
            # PCM publicly; keep full-output hashes and local originals as well.
            if p.name.endswith('-output.wav'):
                row['public_copy']=None;row['reason']='expanded native WAV retained locally; selected PCM and digest published'
            elif p.suffix=='.f32le':
                target=out/(p.name+'.gz');target.write_bytes(gzip.compress(p.read_bytes(),mtime=0))
                row.update(public_copy=target.relative_to(ROOT).as_posix(),compressed_sha256=sha(target))
            else:
                target=out/p.name;shutil.copyfile(p,target);row['public_copy']=target.relative_to(ROOT).as_posix()
            inventory.append(row)
        if not (out/'executed-probe_audio_source_context.py').exists():
            # These final two runs did not create their own launch-time script
            # receipt. Label the current reproduction recipe accordingly.
            shutil.copyfile(ROOT/'scripts/probe_audio_source_context.py',out/'current-reproduction-probe.py')
    candidate=ROOT/'product/.runtime/audio-source-context-20261019-v64-candidate/product/.runtime'
    target=BASE/'isolated-candidate';shutil.copytree(candidate,target)
    units=[]
    for p in sorted(target.glob('candidate-unit-r?.json')):
        v=json.loads(p.read_bytes());units.append({'name':p.name,**{k:v.get(k) for k in ('methods','exit_code','skipped','terminal_ok','frozen_equal','elapsed_seconds')}})
    record={'status':'preserved_development_and_native_probes','checked_at_utc':datetime.now(timezone.utc).isoformat(),
            'probes':probes,'native_calls_separate':sum(x['native_cases'] for x in probes),'inventory':inventory,
            'candidate_units_not_added_to_product_regression':units,'candidate_source_archive':str((target/'candidate-unit-r2-sources.zip').relative_to(ROOT)),
            'model_inference':False,'natural_quality_accepted':False,'audio_listened':False,
            'full_expanded_wav_published':False,'generator_sha256':sha(Path(__file__))}
    save(BASE/'verification.json',record)
    print(json.dumps({'probes':len(probes),'native_calls_separate':record['native_calls_separate'],'candidate_attempts':len(units)}))

if __name__=='__main__':main()
