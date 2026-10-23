"""Reproduce/verify the inherited offline install driver before execution."""
import ast
import json
from pathlib import Path
import re
from run_frozen_regression import sha

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT.parent/'float-balance-lab-20261022'
source=(PARENT/'scripts/verify_float_balance_install.py').read_text('utf8')
numbers={'484':'528','189':'190','316':'318','284':'328'}
source=re.sub(r'\b(?:484|189|316|284)\b',lambda m:numbers[m[0]],source)
source=source.replace('float-balance','float-hsl').replace('float_balance','float_hsl')
source=source.replace("'test_float_hsl']","'test_float_balance','test_float_selective_hsl']")
source=source.replace('passed-public-CLI-floating-levels-and-native-float-previews',
    'passed-public-CLI-floating-selective-HSL-and-native-float-previews')
source=source.replace('native_float_hsl_integrated=True',
    'native_float_balance_integrated=True, native_float_selective_hsl_integrated=True')
assert "'test_float_balance','test_float_selective_hsl']" in source
ast.parse(source)
path=ROOT/'scripts/verify_float_hsl_install.py'
if path.exists():assert path.read_text('utf8')==source
else:path.write_text(source,encoding='utf8',newline='\n')
receipt=ROOT/'docs/validation/evidence/float-hsl-20261022-lab/install-driver-r1.json'
assert not receipt.exists()
receipt.write_text(json.dumps({'status':'prepared-driver-not-installation-proof',
    'parent_sha256':sha(PARENT/'scripts/verify_float_balance_install.py'),
    'driver_sha256':sha(path),'source_methods_gate':328,'installed_methods_target':528,
    'shipping_resource_target':190,'network':False,'virtualization':False},indent=2)+'\n',encoding='utf8')
print('verified reproducible eight-wheel offline installer; 528 methods remain an execution target')
