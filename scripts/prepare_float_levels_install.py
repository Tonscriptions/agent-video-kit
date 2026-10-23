"""Prepare the isolated offline RGBA-levels package and real CLI proof."""
import ast
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT.parent/'float-curves-lab-20261022'
source = (PARENT/'scripts/verify_float_curves_install.py').read_text('utf8')
mapping = {'400':'442','186':'188','311':'314','200':'242'}
source = re.sub(r'\b(?:400|186|311|200)\b',lambda m:mapping[m[0]],source)
source = source.replace('float-curves-20261022','float-levels-20261022').replace('smoke_float_curves_media','smoke_float_levels_media')
source = source.replace('floating-curves','floating-levels').replace("REL/'native-r3/verification.json'","REL/'native-r2/verification.json'")
source = source.replace("REL/'media-r2/verification.json'","REL/'media-r1/verification.json'")
assert source.count("'test_float_curves']")==1
source = source.replace("'test_float_curves']","'test_float_curves','test_float_levels']")
source = source.replace('native_float_curves_integrated=True, default_backend_migrated=False',
    'native_float_curves_integrated=True, native_float_levels_integrated=True, native_animated_exposure_integrated=True, default_backend_migrated=False')
ast.parse(source)
path = ROOT/'scripts/verify_float_levels_install.py';assert not path.exists()
path.write_text(source,encoding='utf8',newline='\n')
print('created fresh eight-wheel levels installation verifier; 442 is a target until executed')
