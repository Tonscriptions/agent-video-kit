"""Record the audited V59 research Skill text; preserve prior audits and registrations."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
folder = Path(__file__).resolve().parent
audit = json.loads((folder/'skills.json').read_bytes())
path = ROOT/'video-cut-install-manifest.json'
mapping = json.loads(path.read_bytes())
old = mapping['current_audit']
history = mapping.setdefault('audit_history', [])
if old not in history:
    history.append(old)
for row in mapping['skills']:
    checked = next(x for x in audit['results'] if x['skill'] == row['name'])
    row['skill_md_sha256'] = checked['sha256'][7:]
from hashlib import sha256
mapping['current_audit'] = {'record': (folder/'skills.json').relative_to(ROOT).as_posix(),
    'record_sha256': 'sha256:'+sha256((folder/'skills.json').read_bytes()).hexdigest(),
    'checked_at_utc': audit['checked_at_utc'], 'skills': audit['skill_count'],
    'local_links_checked': audit['local_links_checked'],
    'semantics': 'V59 research acquisition and strict native loading; zero ROSE forwards; production remains V58'}
path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
print(json.dumps({'skills': audit['skill_count'], 'local_links_checked': audit['local_links_checked'],
                  'prior_audits_preserved': len(history)}))
