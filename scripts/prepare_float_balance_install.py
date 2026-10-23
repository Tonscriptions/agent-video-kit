"""Prepare a real eight-wheel install/replay and 484 isolated methods."""
import ast
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT.parent/'float-levels-lab-20261022'
source=(PARENT/'scripts/verify_float_levels_install.py').read_text('utf8')
numbers={'442':'484','188':'189','314':'316','242':'284'}
source=re.sub(r'\b(?:442|188|314|242)\b',lambda m:numbers[m[0]],source)
source=source.replace('float-levels-20261022','float-balance-20261022').replace('smoke_float_levels_media','smoke_float_balance_media')
# The accepted source harness retains this historical terminal status label;
# balance_oracle and frozen source identities identify the actual new scope.
source=source.replace("REL/'media-r1/verification.json'","REL/'media-r2/verification.json'")
assert source.count("'test_float_levels']")==1
source=source.replace("'test_float_levels']","'test_float_levels','test_float_balance']")
source=source.replace('native_animated_exposure_integrated=True, default_backend_migrated=False',
    'native_animated_exposure_integrated=True, native_float_balance_integrated=True, default_backend_migrated=False')
source=source.replace('timeout=2400','timeout=7200')
ast.parse(source)
path=ROOT/'scripts/verify_float_balance_install.py';assert not path.exists()
path.write_text(source,encoding='utf8',newline='\n')
print('prepared isolated offline balance verifier; 484 remains an execution target')
