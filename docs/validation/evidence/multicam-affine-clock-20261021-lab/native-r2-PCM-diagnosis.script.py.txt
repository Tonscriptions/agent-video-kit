"""Retain exact differences between the independent PCM and the real baseline."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
REL=ROOT/'docs/validation/evidence/multicam-affine-clock-20261021-lab'


def main():
    output=REL/'native-r2-PCM-diagnosis.json';assert not output.exists()
    failed=json.loads((REL/'native-r2/verification.json').read_bytes());assert failed['status']=='failed'
    assert failed['frozen_before']==failed['frozen_after']==frozen()
    calls={row['label']:row for row in failed['calls']}
    samples={};proof=[]
    for name in ('independent-reference-master-PCM','positive-offset-lossless-PCM'):
        row=calls[name]
        result=subprocess.run(row['command'],cwd=ROOT,capture_output=True,timeout=300,creationflags=subprocess.CREATE_NO_WINDOW)
        assert result.returncode==0,result.stderr.decode('utf8','replace')
        digest='sha256:'+hashlib.sha256(result.stdout).hexdigest()
        assert digest==row['stdout_sha256']
        samples[name]=np.frombuffer(result.stdout,dtype='<f4').reshape(-1,2)
        proof.append({'label':name,'command':row['command'],'sha256':digest,'bytes':len(result.stdout)})
    expected=samples['independent-reference-master-PCM'];actual=samples['positive-offset-lossless-PCM']
    assert actual.shape==expected.shape==(576000,2)
    results=[]
    for index in range(3):
        left=index*192000;right=left+192000
        for region,start,end in (('all',left,right),('interior',left+2400,right-2400)):
            a=actual[start:end].astype(np.float64);b=expected[start:end].astype(np.float64)
            delta=a-b;ratio=float(np.sum(a*b)/np.sum(b*b))
            results.append({'window':index,'region':region,'unequal_scalars':int(np.count_nonzero(a!=b)),
                'maximum_absolute_delta':float(np.max(np.abs(delta))),
                'rms_delta':float(np.sqrt(np.mean(delta*delta))), 'linear_gain':ratio,
                'maximum_delta_after_linear_gain':float(np.max(np.abs(a-ratio*b))),
                'first_actual_left':a[:8,0].tolist(),'first_expected_left':b[:8,0].tolist()})
    record={'status':'measured-readonly-PCM-difference','at_utc':datetime.now(timezone.utc).isoformat(),
        'original_failure':'positive-offset-exact-master-PCM','commands':proof,'regions':results,
        'product_inputs_unchanged':frozen()==failed['frozen_before'],
        'scope':'Measurement only; no assertion or product algorithm changed.'}
    output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    (REL/'native-r2-PCM-diagnosis.script.py.txt').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({'status':record['status'],'interiors':[
        {key:row[key] for key in ('window','maximum_absolute_delta','rms_delta','linear_gain','maximum_delta_after_linear_gain')}
        for row in results if row['region']=='interior']}))


if __name__=='__main__':main()
