"""Prepare the existing fresh offline installation proof for continuous curves."""
import ast
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT.parent/'float-lut-lab-20261022'
source = (PARENT/'scripts/verify_float_lut_install.py').read_text('utf8')
mapping = {'360':'400','185':'186','309':'311','160':'200'}
source = re.sub('|'.join(mapping),lambda m:mapping[m[0]],source)
source = source.replace('float-lut-20261022','float-curves-20261022').replace('smoke_float_lut_media','smoke_float_curves_media')
source = source.replace('floating-LUTs','floating-curves')
source = source.replace("REL/'media-r1/verification.json'","REL/'media-r2/verification.json'")
assert source.count("'test_float_lut']")==1
source = source.replace("'test_float_lut']","'test_float_lut','test_float_curves']")
source = source.replace('native_float_lut_integrated=True, default_backend_migrated=False',
    'native_float_lut_integrated=True, native_float_curves_integrated=True, default_backend_migrated=False')
ast.parse(source)
path = ROOT/'scripts/verify_float_curves_install.py';assert not path.exists()
path.write_text(source,encoding='utf8',newline='\n')
print('created fresh eight-wheel curves installation verifier; 400 is a target until executed')
