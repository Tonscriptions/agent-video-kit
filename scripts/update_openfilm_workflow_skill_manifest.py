"""Append three verified local workflow Skill registrations, preserving audit history."""
import argparse
import json
from pathlib import Path
import re
from openfilm_workflow_evidence import ROOT,sha,save

NAMES=('video-cut-reference-remake','video-cut-long-to-short','video-cut-screen-demo')


def run(audit_path):
    audit=json.loads(audit_path.read_bytes());path=ROOT/'video-cut-install-manifest.json';mapping=json.loads(path.read_bytes())
    if audit['skill_count']!=17 or any(row['validator_exit_code'] or not row['installed_directory_resolves_to_repo'] for row in audit['results']):
        raise ValueError('17 validated local registrations required')
    if mapping['skill_count']!=14 or any(row['name'] in NAMES for row in mapping['skills']):
        raise ValueError('fresh V61 manifest append requires unchanged 14-Skill baseline')
    old=mapping['current_audit'];history=mapping.setdefault('audit_history',[])
    if old not in history:history.append(old)
    for name in NAMES:
        source=ROOT/'skills'/name/'SKILL.md';row=next(item for item in audit['results'] if item['skill']==name)
        if row['sha256']!=sha(source):raise ValueError('new Skill bytes changed after validation')
        description=re.search(r'^description: (.+)$',source.read_text(encoding='utf-8'),re.M)[1]
        mapping['skills'].append({'name':name,'invocation':'$'+name,'canonical_directory':str(source.parent),
            'registration_directory':str(Path('C:/Users/carzy/.codex/skills')/name),'description':description,
            'source_kind':'local-product-workflow-adapted-from-openfilm','source_repository':'openfilm/openfilm',
            'source_commit':'7a64d1feacdb59fb631694af7501a4ca570254ca','source_license_notice':'product/src/ai_ad_editor/OPENFILM_LICENSE.txt',
            'skill_md_sha256':row['sha256'][7:],'file_count':1,'validation':row['validator_stdout'],
            'prefix_verified':True,'registration_verified':True,
            'validation_scope':'current controlled CLI/media workflow; automatic semantic/UI understanding and natural quality unaccepted'})
    mapping['skills'].sort(key=lambda row:row['name']);mapping['skill_count']=17
    for row in mapping['skills']:
        checked=next(item for item in audit['results'] if item['skill']==row['name'])
        row['skill_md_sha256']=checked['sha256'][7:]
    mapping['current_audit']={'record':audit_path.relative_to(ROOT).as_posix(),'record_sha256':sha(audit_path),
        'checked_at_utc':audit['checked_at_utc'],'skills':17,'local_links_checked':audit['local_links_checked'],
        'semantics':'V61: three locally adapted OpenFilm creative workflows, controlled encoded media and explicit limits; '
        '17 video-cut Skills; V60 product inputs unchanged, inherited 1374-method regression; no new AI understanding kernel, '
        'speech publication, natural quality or full CapCut parity acceptance'}
    save(path,mapping)
    print(json.dumps({'skill_count':17,'new_skills':list(NAMES),'prior_audits_preserved':len(history)}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--skills',type=Path,required=True)
    run(parser.parse_args().skills.resolve())
