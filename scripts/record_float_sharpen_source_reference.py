"""Consolidate already-fetched upstream source with native version/help and retained failures."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
REL=ROOT/'docs/validation/evidence/float-sharpen-20261022-lab'
def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def main():
 out=REL/'source-reference-r4';out.mkdir(exist_ok=False)
 r1=json.loads((REL/'source-reference-r1/verification.json').read_bytes())
 ref=r1['references'][0];original=REL/'source-reference-r1/libavfilter__vf_unsharp.c.txt'
 assert sha(original)==ref['sha256'] and original.stat().st_size==ref['bytes']
 (out/'vf_unsharp.c.txt').write_bytes(original.read_bytes())
 license_path=ROOT.parents[2]/'sources/upstream/ffmpeg/COPYING.GPLv2'
 # Use the existing workspace copy of the GPL v2 text, never fetch a second runtime.
 assert license_path.is_file(),str(license_path)
 (out/'COPYING.GPLv2.txt').write_bytes(license_path.read_bytes())
 sys.path.insert(0,str(ROOT/'product/src'))
 from ai_ad_editor.runtime import configure_local_runtime
 configure_local_runtime()
 from ai_ad_editor.media import ffmpeg_path
 binary=Path(ffmpeg_path()).resolve(strict=True)
 state={'status':'running','at_utc':datetime.now(timezone.utc).isoformat(),'native_windows':True,'virtualization':False,
  'network_in_this_consolidation':False,'runtime_network':False,'reference':ref,'source_sha256':sha(out/'vf_unsharp.c.txt'),
  'license_origin':str(license_path),'license_sha256':sha(out/'COPYING.GPLv2.txt'),'runtime_C_copied':False,
  'native_binary':str(binary),'native_binary_sha256':sha(binary),'calls':[],
  'earlier_failures':[{'revision':'source-reference-r1','cause':'valid n8.1 vf_unsharp.c succeeded; nonexistent libavfilter/unsharp.h returned404'},
   {'revision':'source-reference-r2','cause':'valid n8.0 vf_unsharp.c succeeded with identical hash; nonexistent unsharp.h returned404'},
   {'revision':'source-reference-r3','cause':'COPYING.GPLv2 request DNS getaddrinfo11001; existing copied C retained; inline exit1 without receipt'},
   {'revision':'exploratory-14bit-native','cause':'yuva444p14le is not an accepted native format; inline exit1 after first four formats, not a six-format pass'}],
  'findings':{'native_alpha_nonzero_reference_accepted':False,
   'native_alpha_observation':'native-r1 retained three Windows access violations3221225477 with nonzero alpha_amount; source config_input initializes luma/chroma but not alpha scratch',
   'native_14bit_pixel_format':False,'native_uint16_amount_extra_shift_bits':8,
   'native_fixedpoint_overflow_reproduced':False,'native_pixel_bit_equivalence':False,'natural_or_HDR_acceptance':False}}
 save(out/'verification.json',state)
 try:
  for label,args in [('version',['-version']),('unsharp-help',['-hide_banner','-h','filter=unsharp'])]:
   command=[str(binary),*args];p=subprocess.run(command,capture_output=True,timeout=30)
   (out/(label+'.stdout.log')).write_bytes(p.stdout);(out/(label+'.stderr.log')).write_bytes(p.stderr)
   state['calls'].append({'name':label,'command':command,'exit_code':p.returncode,'stdout_sha256':sha(out/(label+'.stdout.log')),'stderr_sha256':sha(out/(label+'.stderr.log'))})
   assert p.returncode==0
  state['status']='passed-pinned-source-native-version-help-and-failures-recorded'
 except BaseException as exc:state.update(status='failed-preserved',error=repr(exc));raise
 finally:save(out/'verification.json',state)
 print(json.dumps({k:state[k] for k in ('status','source_sha256','runtime_C_copied')},ensure_ascii=False))
if __name__=='__main__':main()
