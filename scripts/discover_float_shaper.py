"""Record actual discovery separately from execution and acceptance."""
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import unittest
from run_frozen_regression import frozen,sha

ROOT=Path(__file__).resolve().parents[1]
REL=ROOT/'docs/validation/evidence/float-shaper-20261023-lab'

def flatten(suite):
    for item in suite:
        if isinstance(item,unittest.TestSuite):yield from flatten(item)
        else:yield item.id()

def main():
    output=REL/'discovery-r1.json';assert not output.exists()
    before=frozen();assert len(before)==331
    sys.path[:0]=[str(ROOT/'product/src'),str(ROOT/'product/tests')]
    from ai_ad_editor.runtime import configure_local_runtime
    configure_local_runtime()
    names=['test_float_shaper','test_float_lut','test_lut_automation','test_float_preview']
    full=list(flatten(unittest.defaultTestLoader.discover(str(ROOT/'product/tests'))))
    installed=list(flatten(unittest.defaultTestLoader.loadTestsFromNames(names)))
    assert len(full)==2930 and len(installed)==118 and len(set(full))==len(full)
    assert set(installed)<=set(full) and not any('_FailedTest' in n for n in full)
    assert frozen()==before
    result=dict(status='discovered-not-executed',at_utc=datetime.now(timezone.utc).isoformat(),
        full_methods=len(full),installed_methods=len(installed),new_shaper_methods=sum(n.startswith('test_float_shaper.') for n in full),
        actual_methods_executed_here=0,full_test_ids=full,installed_test_ids=installed,frozen_inputs=before,
        script_sha256=sha(Path(__file__)),full_capcut_parity=False)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({k:result[k] for k in ('status','full_methods','installed_methods','new_shaper_methods','actual_methods_executed_here')}))

if __name__=='__main__':main()
