"""Bind V60 product/real-execution Skill evidence without replacing history."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
folder = Path(__file__).resolve().parent
audit = json.loads((folder/'skills.json').read_bytes())
full = json.loads((folder/'full-r2.json').read_bytes())
actual = json.loads((ROOT/'docs/validation/evidence/cuda-admission-vace-20261019-v60/verification.json').read_bytes())
install = json.loads((ROOT/'docs/validation/evidence/cuda-admission-install-20261019-v60-r3/verification.json').read_bytes())
native = json.loads((folder/'native-r3.json').read_bytes())
if (audit['skill_count'] != 14 or any(row['validator_exit_code'] or not row['installed_directory_resolves_to_repo'] for row in audit['results'])
        or not full['terminal_ok'] or full['methods'] != 1374 or full['skipped'] or not full['frozen_equal']
        or actual['status'] != 'failed' or install['status'] != 'passed_native_install_and_cuda_admission'
        or native['status'] != 'passed_native_cuda_sampling_allocation_and_loader_rejection'):
    raise ValueError('CURRENT_COMPLETED_V60_PRODUCT_ACTUAL_AND_SKILL_EVIDENCE_REQUIRED')
path = ROOT/'video-cut-install-manifest.json'
mapping = json.loads(path.read_bytes())
old = mapping['current_audit']
history = mapping.setdefault('audit_history', [])
if old not in history:
    history.append(old)
for row in mapping['skills']:
    checked = next(x for x in audit['results'] if x['skill'] == row['name'])
    row['skill_md_sha256'] = checked['sha256'][7:]
mapping['current_audit'] = {
    'record': (folder/'skills.json').relative_to(ROOT).as_posix(),
    'record_sha256': 'sha256:'+sha256((folder/'skills.json').read_bytes()).hexdigest(),
    'checked_at_utc': audit['checked_at_utc'],
    'skills': audit['skill_count'],
    'local_links_checked': audit['local_links_checked'],
    'semantics': ('V60 product: UUID-bound physical/Torch admission, own idle-cache accounting and text offload cleanup; '
                  '1374 completed frozen methods, native package/install, two isolated CLI and installed CUDA admission; '
                  'current native 128 MiB active allocation/cache release passed after resources recovered; first real model '
                  'and earlier revised small-allocation probe refusals retained; complete revised trained-model delivery '
                  'remains pending; no new repaired output; '
                  'observations are not reservations or OOM guarantees; natural quality and full CapCut parity unaccepted')}
path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
print(json.dumps({'skills': audit['skill_count'], 'local_links_checked': audit['local_links_checked'],
                  'prior_audits_preserved': len(history)}))
