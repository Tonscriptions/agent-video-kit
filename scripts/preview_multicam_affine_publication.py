"""Review projected docs, seven source deltas and seventeen skills without changing main."""
from datetime import datetime,timezone
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.parse
from publish_multicam_affine_clock import (ROOT,MAIN,REL,REPORT,CONTRACT,LATEST_DOCS,MODIFIED,ADDED,
    source_audit,source_files,documents,read,save,sha,frozen)

WORK=ROOT/'product/.runtime/multicam-affine-clock-20261021/publication-preview-r1'
assert not WORK.exists();WORK.mkdir(parents=True)
CANDIDATE=WORK/'candidate';CANDIDATE.mkdir()
OUT=ROOT/REL/'publication-preview-r1.json';assert not OUT.exists()
current=source_audit();before=frozen()
parents={p.parent.name:sha(p) for p in (MAIN/'skills').glob('*/SKILL.md')};assert len(parents)==17
for name in (*LATEST_DOCS,'.gitattributes',*(str(p.relative_to(MAIN).as_posix()) for p in (MAIN/'skills').glob('*/SKILL.md'))):
    target=CANDIDATE/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(MAIN/name,target)
for name in MODIFIED|ADDED:
    target=CANDIDATE/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
modified=documents(CANDIDATE,None)
for name,digest in current.items():
    projected=CANDIDATE/name if (CANDIDATE/name).is_file() else MAIN/name
    assert sha(projected)==digest,name
validator=Path('C:/Users/carzy/.codex/skills/.system/skill-creator/scripts/quick_validate.py')
skills={};links=[]
for source in sorted((CANDIDATE/'skills').glob('*/SKILL.md')):
    result=subprocess.run([sys.executable,'-E','-B','-X','utf8',validator,source.parent],
        cwd=ROOT,capture_output=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode==0,(source,result.stderr.decode('utf8','replace'))
    canonical=MAIN/'skills'/source.parent.name
    assert (Path('C:/Users/carzy/.codex/skills')/source.parent.name).resolve()==canonical.resolve()
    skills[source.parent.name]={'candidate_sha256':sha(source),'published_parent_sha256':parents[source.parent.name],
        'validator_exit_code':result.returncode,'validator_stdout':result.stdout.decode('utf8','replace'),
        'registered_directory_still_published_parent':True}
for name in sorted(modified-{'.gitattributes'}|{p.relative_to(CANDIDATE).as_posix() for p in (CANDIDATE/'skills').glob('*/SKILL.md')}):
    source=CANDIDATE/name
    for raw in re.findall(r'!?\[[^\]]*\]\(([^)\n]+)\)',source.read_text('utf8')):
        target=raw.strip('<>').split('#',1)[0]
        if not target or re.match(r'^[a-zA-Z][\w+.-]*:',target):continue
        resolved=(source.parent/urllib.parse.unquote(target)).resolve()
        assert resolved.is_relative_to(CANDIDATE),(name,target)
        relative=resolved.relative_to(CANDIDATE)
        actual=next((root/relative for root in (CANDIDATE,ROOT,MAIN) if (root/relative).exists()),None)
        assert actual,(name,target)
        links.append({'document':name,'target':relative.as_posix(),'actual_source':str(actual)})
old=(MAIN/'README.md').read_text('utf8')
r15='<!-- OPENFILM-R15-INCREMENTAL -->'+old.split('<!-- OPENFILM-R15-INCREMENTAL -->')[1].split('<!-- /OPENFILM-R15-INCREMENTAL -->')[0]+'<!-- /OPENFILM-R15-INCREMENTAL -->'
assert r15 in (CANDIDATE/'README.md').read_text('utf8')
assert frozen()==before==current
assert {p.parent.name:sha(p) for p in (MAIN/'skills').glob('*/SKILL.md')}==parents
record={'status':'passed-projected-source-documents-and-skills','checked_at_utc':datetime.now(timezone.utc).isoformat(),
    'candidate':str(CANDIDATE),'main_written':False,'product_promoted':False,'skills_registered':False,
    'full_receipt_fabricated':False,'full_gate_still_required':2084,'source_projection_inputs':len(current),
    'new_or_modified_source_files':7,'skills':skills,'skill_count':17,'local_links':links,
    'OpenFilm_R15_block_preserved':True,'documents':{name:sha(CANDIDATE/name) for name in sorted(modified)},
    'frozen_before':before,'frozen_after':frozen(),'script_sha256':sha(Path(__file__)),
    'publisher_sha256':sha(ROOT/'scripts/publish_multicam_affine_clock.py'),
    'document_generator_sha256':sha(ROOT/'scripts/multicam_affine_release_docs.py'),
    'scope':'Static projection and skill validation only; complete2084 is running and not accepted by this preview.'}
save(OUT,record)
print(json.dumps({'status':record['status'],'source_inputs':len(current),'skills':17,'local_links':len(links),
    'main_written':False,'full_receipt_fabricated':False},ensure_ascii=False))
