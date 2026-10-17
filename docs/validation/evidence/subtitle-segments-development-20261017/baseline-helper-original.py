from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,subprocess,sys,zipfile,io
ROOT=Path(__file__).resolve().parents[2]
baseline='29369c4c444e66b209a7966d3046415e015fdaaf'
work=ROOT/'product/.runtime/subtitle-segments-baseline-20261017';work.mkdir(exist_ok=False)
out=ROOT/'docs/validation/evidence/subtitle-segments-baseline-20261017';out.mkdir(exist_ok=False)
raw=subprocess.run(['git','-c','core.autocrlf=false','archive',baseline,'product'],cwd=ROOT,capture_output=True,check=True).stdout
with zipfile.ZipFile(io.BytesIO(raw)) as z:z.extractall(work)
def inventory():return {p.relative_to(work).as_posix():'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest() for p in (work/'product/src').rglob('*') if p.is_file()}
before=inventory()
env=dict(os.environ);env['PYTHONPATH']=str(work/'product/src');env['PYTHONDONTWRITEBYTECODE']='1'
cmd=[sys.executable,'-B','-X','utf8','-m','ai_ad_editor','subtitle','segment','--project',str(work/'unused'),'--input','unused.json','--output','assets/subtitles/new.json']
r=subprocess.run(cmd,cwd=work,env=env,capture_output=True)
(out/'segment.stdout.log').write_bytes(r.stdout);(out/'segment.stderr.log').write_bytes(r.stderr)
assert r.returncode==2 and b'invalid choice' in r.stderr and b'segment' in r.stderr
c=subprocess.run([sys.executable,'-B','-X','utf8','-m','ai_ad_editor','capabilities'],cwd=work,env=env,capture_output=True)
(out/'capabilities.stdout.json').write_bytes(c.stdout);(out/'capabilities.stderr.log').write_bytes(c.stderr)
value=json.loads(c.stdout);assert c.returncode==0 and 'subtitle_segmentation' not in value['data']['capabilities']
assert before==inventory()
record={'checked_at_utc':datetime.now(timezone.utc).isoformat(),'status':'passed','baseline_ref':baseline,
 'segment_command_available':False,'command_rejection_exit_code':r.returncode,'capability_present':False,
 'source_unchanged':True,'source_files':len(before),'source_sha256':before,
 'scope':'fixed previous commit lacks the new command and capability; no claim its renderer fails',
 'files':{p.name:'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()}}
(out/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in record.items() if k not in {'source_sha256','files'}},ensure_ascii=False,indent=2))
