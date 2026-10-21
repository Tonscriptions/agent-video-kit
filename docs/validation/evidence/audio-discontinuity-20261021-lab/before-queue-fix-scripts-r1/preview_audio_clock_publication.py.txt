"""Build a private publication preview without supplying a fake full-suite receipt."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from audio_clock_release_common import ROOT,MAIN,REL as EVIDENCE,read,save,links
from audio_clock_release_docs import REL,MARKER,LATEST_DOCS,SKILLS,documents
from publish_native_audio_clock import source_audit,SCRIPTS
from run_frozen_regression import frozen,sha

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--revision',required=True);args=parser.parse_args()
    receipt=EVIDENCE/('publication-preview-'+args.revision+'.json');assert not receipt.exists()
    root=ROOT/'product/.runtime/audio-discontinuity-20261021'/('publication-preview-'+args.revision)/'tree'
    assert not root.exists();root.mkdir(parents=True)
    current=source_audit()
    names=set(LATEST_DOCS)|{'.gitattributes'}|{'skills/'+p.name+'/SKILL.md' for p in (MAIN/'skills').iterdir() if (p/'SKILL.md').is_file()}
    parents={name:sha(MAIN/name) for name in sorted(names)}
    for name in sorted(names):
        target=root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(MAIN/name,target)
        assert sha(target)==parents[name]
    record={'status':'preparing', 'started_at_utc':datetime.now(timezone.utc).isoformat(), 'root':str(root),
        'script_sha256':sha(Path(__file__)), 'native_windows':True,'virtualization':False,'network':False,
        'main_integrated':False,'registration_changed':False,'full_receipt_supplied':False,'full_capcut_parity':False}
    try:
        changed=documents(root,None);rows=[];validations=[]
        for name in sorted(changed|{n for n in names if n.startswith('skills/')}):
            if name=='.gitattributes':continue
            text=(root/name).read_text('utf8')
            if name in LATEST_DOCS:text=text.split('<!-- '+MARKER+' -->',1)[1].split('<!-- /'+MARKER+' -->',1)[0]
            rows+=links(name,text,(root,ROOT,MAIN))
        for name in SKILLS:
            command=[sys.executable,'-E','-B','-X','utf8',
                'C:/Users/carzy/.codex/skills/.system/skill-creator/scripts/quick_validate.py',str(root/'skills'/name)]
            result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
            validations.append({'skill':name,'command':command,'exit_code':result.returncode,
                'stdout':result.stdout.decode('utf8','replace'),'stderr':result.stderr.decode('utf8','replace')})
            assert result.returncode==0
        original=(MAIN/'README.md').read_text('utf8');candidate=(root/'README.md').read_text('utf8')
        for marker in ('OPENFILM-R15-INCREMENTAL','R14-CURRENT'):
            pattern=r'<!-- '+re.escape(marker)+r' -->.*?<!-- /'+re.escape(marker)+r' -->'
            assert re.search(pattern,original,re.S).group()==re.search(pattern,candidate,re.S).group()
        assert frozen()==current
        for name,digest in parents.items():assert sha(MAIN/name)==digest
        record.update(status='passed-unpublished-document-and-17-skill-preview',local_links=rows,
            canonical_skills=17,updated_drafts=4,validators=validations,parent_files=parents,
            generated_files={name:sha(root/name) for name in sorted(changed)},
            publication_scripts={name+'.py':sha(ROOT/'scripts'/(name+'.py')) for name in SCRIPTS},
            main_inputs_unchanged=True,source_frozen_inputs=current,OpenFilm_R14_R15_preserved=True)
    except BaseException as error:
        record.update(status='failed-preserved',error=repr(error));raise
    finally:
        record['finished_at_utc']=datetime.now(timezone.utc).isoformat();save(receipt,record)
        receipt.with_suffix('.script.py.txt').write_bytes(Path(__file__).read_bytes())
        print(json.dumps({'status':record['status'],'links':len(record.get('local_links',[])),
            'validators':len(record.get('validators',[])),'main_integrated':False},ensure_ascii=False))

if __name__=='__main__':main()
