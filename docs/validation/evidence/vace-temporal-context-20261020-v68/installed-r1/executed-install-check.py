"""Verify the native V68 package, isolated context contracts and real LaMa control.

The contract probe executes installed modules only. It does not run VACE or
claim generated video quality; the separate unchanged-profile model run does.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')


PROBE = r'''
import json,sys
from pathlib import Path
site=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(site))
from ai_ad_editor import local_vace, vace_context
from ai_ad_editor.errors import AppError
assert Path(local_vace.__file__).is_relative_to(site)
assert Path(vace_context.__file__).is_relative_to(site)
base=local_vace.normalize_generation(prompt='Keep the supplied scene.',window_frames=5,window_overlap=2,frames=8)
explicit=local_vace.normalize_generation(prompt='Keep the supplied scene.',window_frames=5,window_overlap=2,temporal_context='none',frames=8)
previous=local_vace.normalize_generation(prompt='Keep the supplied scene.',window_frames=5,window_overlap=2,temporal_context='previous',frames=8)
assert base==explicit and 'temporal_context' not in base
assert previous=={**base,'temporal_context':'previous'}
assert local_vace.buffer_budget(64,48,previous,256)-local_vace.buffer_budget(64,48,base,256)==64*48*4*2
assert local_vace.IMPLEMENTATIONS['temporal_context']=='vace_context.py'
asset={'kind':'video','probe':{'streams':[{'codec_type':'video','nb_frames':'8'}]}}
vace_context.validate_generation_metadata(previous,asset=asset)
for bad in ({**previous,'window_overlap':0},{**previous,'temporal_context':'auto'},{**previous,'scene_cut_frames':[999]}):
    try:vace_context.validate_generation_metadata(bad,asset=asset)
    except AppError as error:assert error.code=='VACE_GENERATION_METADATA_INVALID'
    else:raise AssertionError('bad saved generation accepted')
print(json.dumps({'status':'passed','checks':['installed_module_origins','canonical_none','explicit_previous','extra_owned_bytes','adapter_context_closure','valid_saved_generation','three_invalid_saved_generations'],
    'module_files':{'local_vace':str(Path(local_vace.__file__).relative_to(site)),'vace_context':str(Path(vace_context.__file__).relative_to(site))},'actual_vace_forwards':0}))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('bundle', 'work', 'evidence', 'public', 'development-evidence', 'development-assets'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    for name, value in vars(args).items():
        setattr(args, name, value.resolve())
    args.evidence.mkdir(parents=True, exist_ok=False)
    before = frozen()
    calls = []
    record = {'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),
        'frozen_before':before,'calls':calls,'virtualization':False,'network':'disabled',
        'actual_vace_forwards':0,'natural_quality_accepted':False,'different_machine_accepted':False}
    shutil.copyfile(__file__,args.evidence/'executed-install-check.py')
    env = dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TEMP=str(args.work),TMP=str(args.work),TMPDIR=str(args.work))

    def command(values, label, timeout=180):
        result=subprocess.run(list(map(str,values)),cwd=ROOT,env=env,capture_output=True,timeout=timeout)
        out=args.evidence/(label+'.stdout.log');err=args.evidence/(label+'.stderr.log')
        out.write_bytes(result.stdout);err.write_bytes(result.stderr)
        calls.append({'name':label,'command':list(map(str,values)),'exit_code':result.returncode,
            'stdout':out.name,'stderr':err.name,'stdout_sha256':sha(out),'stderr_sha256':sha(err)})
        save(args.evidence/'verification.json',record)
        if result.returncode:raise RuntimeError(label+' failed; see retained logs')
        return result.stdout

    try:
        common=[]
        for name in ('bundle','work','public','development-evidence','development-assets'):
            common+=['--'+name,str(getattr(args,name.replace('-','_')))]
        command([sys.executable,'-B','-X','utf8',ROOT/'scripts/verify_video_outpainting_install.py',
            *common,'--evidence',args.evidence/'base'],'install-and-real-lama-control',timeout=2400)
        base=json.loads((args.evidence/'base/verification.json').read_bytes())
        assert base['status']=='passed' and base['frozen_equal'] and base['frozen_before']==before
        target=args.work/'installed'
        prefix=[sys.executable,'-I','-S','-B','-X','utf8',target/'run.py']
        for verb in ('inpaint','outpaint'):
            help_text=command([*prefix,'media',verb,'--help'],verb+'-help').decode('utf8')
            assert '--temporal-context {none,previous}' in help_text
        caps=json.loads(command([*prefix,'capabilities'],'context-capabilities'))
        context=caps['data']['capabilities']['generative_video_editing']['generation_parameters']['temporal_context']
        assert context['choices']==['none','previous'] and context['default']=='none'
        assert context['previous_requires_positive_overlap'] and context['controller_and_model_input_traces']
        assert context['generated_context_is_ground_truth'] is False and context['natural_quality_accepted'] is False
        result=json.loads(command([sys.executable,'-I','-S','-B','-X','utf8','-c',PROBE,target/'site'],'installed-contract-probe'))
        assert result['status']=='passed' and result['actual_vace_forwards']==0
        record.update(status='passed',packaged_files=base['packaged_files'],
            isolated_cli_calls=base['isolated_cli_calls']+3,isolated_module_contract_calls=1,
            contract_probe=result,actual_lama_forwards=8,
            base_receipt_sha256=sha(args.evidence/'base/verification.json'),
            frozen_after=frozen())
        record['frozen_equal']=record['frozen_before']==record['frozen_after']
        if not record['frozen_equal']:raise ValueError('source changed during verification')
    except Exception as exc:
        record.update(status='failed',error=type(exc).__name__+': '+str(exc),frozen_after=frozen())
        raise
    finally:
        record['finished_at_utc']=datetime.now(timezone.utc).isoformat()
        save(args.evidence/'verification.json',record)
    print(json.dumps({k:record[k] for k in ('status','packaged_files','isolated_cli_calls','isolated_module_contract_calls','frozen_equal')}))


if __name__=='__main__':main()
