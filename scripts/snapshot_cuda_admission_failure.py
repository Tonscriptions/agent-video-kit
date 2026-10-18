"""Preserve the first real rejection and its exact pre-cache-fix source tree."""
import hashlib
import json
from pathlib import Path
import zipfile
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/cuda-admission-20261019-v60'
REAL=ROOT/'docs/validation/evidence/cuda-admission-vace-20261019-v60'
def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
inventory=frozen();full=json.loads((BASE/'full-r1.json').read_bytes())
actual=json.loads((REAL/'verification.json').read_bytes())
if inventory!=full['frozen_before'] or actual['status']!='failed' or actual['frozen_before']!=inventory:
    raise ValueError('unchanged first-run source and real failure required')
log=REAL/'actual-vace.stderr.log'
envelope=json.JSONDecoder().raw_decode(log.read_text(encoding='utf-8').split('RuntimeError: ',1)[1])[0]
worker=json.JSONDecoder().raw_decode(envelope['errors'][0]['cause'])[0]
rejection=worker['gpu_admission_failure']
if (worker['status']!='failed' or rejection['stage']!='video-window-1'
        or rejection['error_code']!='CUDA_ADMISSION_INSUFFICIENT_TORCH_FREE'
        or rejection['required_free_bytes']!=768*1024**2
        or not rejection['torch_free_bytes']<rejection['required_free_bytes']<=rejection['physical_free_bytes']):
    raise ValueError('unexpected first real rejection')
archive=BASE/'r1-frozen-inputs.zip';receipt=BASE/'r1-source-snapshot.json'
if archive.exists() or receipt.exists() or (REAL/'r1-worker-response.json').exists():
    raise ValueError('fresh failure source evidence required')
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as target:
    for name in sorted(inventory):
        info=zipfile.ZipInfo(name,(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
        target.writestr(info,(ROOT/name).read_bytes())
if frozen()!=inventory:raise ValueError('source changed during archival')
save(REAL/'r1-worker-response.json',worker)
save(receipt,{'status':'preserved_first_real_rejection_and_188_exact_source_inputs',
    'frozen_inputs':inventory,'archive_sha256':sha(archive),'files':len(inventory),
    'actual_failure_receipt_sha256':sha(REAL/'verification.json'),'actual_stderr_sha256':sha(log),
    'worker_response_sha256':sha(REAL/'r1-worker-response.json'),'rejection':rejection,
    'video_denoising_windows_started':0,'model_components_loaded_before_rejection':True,
    'quality_result':None,'generator_sha256':sha(Path(__file__))})
print(json.dumps({'status':'preserved_first_real_rejection','files':len(inventory),'torch_free_bytes':rejection['torch_free_bytes']}))
