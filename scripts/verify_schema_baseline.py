"""Compare the real declared date property on fixed V46 and current source."""
import argparse,hashlib,io,json,os,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REF='29ee538912043993fe75aa5c59bcebfc9df2769c'


def run(work,output):
    work.mkdir(parents=True,exist_ok=False);output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists():raise ValueError('Existing evidence preserved')
    raw=subprocess.check_output(['git','-c','core.autocrlf=false','archive','--format=zip',REF,'product/src','docs/specs/agent-project.schema.json'],cwd=ROOT)
    source=work/'fixed-v46'
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for entry in archive.infolist():
            if entry.is_dir():continue
            path=(source/entry.filename).resolve();assert path.is_relative_to(source.resolve())
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(archive.read(entry))
    project=work/'project';boot="""import sys
sys.path.insert(0,sys.argv[1])
from ai_ad_editor.cli import main
raise SystemExit(main(sys.argv[2:]))
"""
    env=dict(os.environ);env.update(TEMP=str(ROOT/'product/.runtime/temp'),TMP=str(ROOT/'product/.runtime/temp'),AI_AD_EDITOR_RUNTIME_DIR=str(work/'runtime'))
    def cli(src,*args):
        result=subprocess.run([sys.executable,'-E','-B','-X','utf8','-c',boot,str(src),*map(str,args)],cwd=work,env=env,capture_output=True,timeout=90)
        return {'exit_code':result.returncode,'stdout':json.loads(result.stdout),'stderr':result.stderr.decode('utf-8')}
    initialized=cli(source/'product/src','project','init',project);assert initialized['exit_code']==0,initialized
    path=project/'project.json';payload=json.loads(path.read_bytes());payload['project']['created_at']='this-is-not-a-date';path.write_text(json.dumps(payload),encoding='utf-8')
    before=path.read_bytes();old=cli(source/'product/src','validate','--project',project);current=cli(ROOT/'product/src','validate','--project',project)
    assert old['exit_code']==0 and old['stdout']['data']['schema_engine']=='jsonschema',old
    assert current['exit_code']==2 and any(x['path']=='project.created_at' and x['code']=='SCHEMA_VALIDATION_FAILED' for x in current['stdout']['errors']),current
    assert path.read_bytes()==before
    record={'status':'verified','fixed_commit':REF,'field':'project.created_at','input':payload,'input_sha256':'sha256:'+hashlib.sha256(before).hexdigest(),'old_source':old,'current_source':current,'project_unchanged':True,'earlier_baseline_correction':'schema-release-baseline-20261018.json used an extra top-level created_at; that call did not prove format coverage. The detached wheel degradation observations are independent. This record uses the declared field.','network':False,'virtualization':False}
    output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps({'status':record['status'],'field':record['field'],'old':old['exit_code'],'current':current['exit_code']}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.work.resolve(),a.output.resolve())
