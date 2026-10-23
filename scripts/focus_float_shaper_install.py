"""Constrain the unexecuted package plan to changed paths and their integrations."""
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REL=ROOT/'docs/validation/evidence/float-shaper-20261023-lab'

def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    output=REL/'package-plan-r2';output.mkdir(exist_ok=False)
    assert not (REL/'installed-r1').exists()
    for name in ('verify_float_shaper_install.py','run_float_shaper_installed_suite.py','prepare_float_shaper_install.py'):
        (output/(name+'.planned837-not-executed.txt')).write_bytes((ROOT/'scripts'/name).read_bytes())
    source=(ROOT/'scripts/verify_float_shaper_install.py').read_text(encoding='utf8').replace('837','118')
    start=source.index('        names = [');end=source.index('\n        result =',start)
    source=source[:start]+"        names = ['test_float_shaper','test_float_lut','test_lut_automation','test_float_preview']"+source[end:]
    assert source.count('run_pipeline_installed_suite.py')==1
    source=source.replace('run_pipeline_installed_suite.py','run_float_shaper_installed_suite.py')
    source=source.replace('HTML_preparation_diagnostics_integrated=True,','')
    ast.parse(source)
    (ROOT/'scripts/verify_float_shaper_install.py').write_text(source,encoding='utf8',newline='\n')
    runner='''"""Run changed LUT/registry/preview behavior using only the fresh installed site."""
import json
from pathlib import Path
import sys
import unittest

def main():
    site,tests=Path(sys.argv[1]).resolve(),Path(sys.argv[2]).resolve()
    names=json.loads(sys.argv[3]);assert names==['test_float_shaper','test_float_lut','test_lut_automation','test_float_preview']
    sys.path[:0]=[str(site),str(tests)]
    from ai_ad_editor.runtime import configure_local_runtime
    configure_local_runtime()
    suite=unittest.defaultTestLoader.loadTestsFromNames(names)
    assert suite.countTestCases()==118,suite.countTestCases()
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    origins={name:str(Path(value.__file__).resolve()) for name,value in sys.modules.items()
        if getattr(value,'__file__',None) and (name=='ai_ad_editor' or name.startswith('ai_ad_editor.')
            or name=='numpy' or name.startswith('numpy.') or name=='PIL' or name.startswith('PIL.'))}
    assert origins and all(Path(path).is_relative_to(site) for path in origins.values())
    print(json.dumps({'methods':result.testsRun,'skipped':len(result.skipped),'origins':origins,
        'native_test_records':{name:getattr(sys.modules[name],'NATIVE_CALLS',[]) for name in names}}))
    return 0 if result.wasSuccessful() and not result.skipped else 1

if __name__=='__main__': raise SystemExit(main())
'''
    ast.parse(runner)
    (ROOT/'scripts/run_float_shaper_installed_suite.py').write_text(runner,encoding='utf8',newline='\n')
    receipt=dict(status='prepared-focused-offline118-not-executed',at_utc=datetime.now(timezone.utc).isoformat(),
        actual_methods_executed_here=0,planned_installed_methods=118,planned_full_methods=2930,
        previous_837_plan_executed=False,source_modules=['test_float_shaper','test_float_lut','test_lut_automation','test_float_preview'],
        reason='Changed runtime files are LUT parsing/evaluation, registration metadata and capabilities. The fresh package must exercise new shapers, unchanged 3D LUT behavior, registry automation and real formal/preview/PCM/PNG integration. Global regression remains a separate complete suite.',
        scripts={name:sha(ROOT/'scripts'/name) for name in ('verify_float_shaper_install.py','run_float_shaper_installed_suite.py')})
    (output/'verification.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'status':receipt['status'],'actual_methods_executed_here':0}))

if __name__=='__main__':main()
