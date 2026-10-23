"""Run changed LUT/registry/preview behavior using only the fresh installed site."""
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
