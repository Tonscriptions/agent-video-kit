"""Adapt a fresh eight-wheel installation proof to the full LUT chain."""
import ast
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT.parent/'float-crop-lab-20261022'
source = (PARENT/'scripts/verify_float_crop_install.py').read_text('utf8')
mapping = {'323':'360','183':'185','306':'309','123':'160'}
source = re.sub('|'.join(mapping),lambda m:mapping[m[0]],source)
source = source.replace('float-crop-20261022','float-lut-20261022').replace('smoke_float_crop_media','smoke_float_lut_media')
source = source.replace('native-r2','native-r3').replace('floating-crops','floating-LUTs')
assert source.count("'test_float_crop']")==1
source = source.replace("'test_float_crop']","'test_float_crop', 'test_float_lut']")
assert source.count('native_float_crop_integrated=True, default_backend_migrated=False')==1
source = source.replace('native_float_crop_integrated=True, default_backend_migrated=False',
    'native_float_crop_integrated=True, native_float_lut_integrated=True, default_backend_migrated=False')
ast.parse(source)
path = ROOT/'scripts/verify_float_lut_install.py';assert not path.exists()
path.write_text(source,encoding='utf8',newline='\n')
print('created fresh offline LUT installation verifier; 360 methods are a target until executed')
