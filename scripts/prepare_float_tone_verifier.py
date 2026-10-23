"""Prepare an unexecuted tone driver from the immutable HSL verifier."""
import ast
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT.parent/'float-hsl-lab-20261022/scripts/verify_float_hsl.py').read_text('utf8')
source=source.replace('float-hsl','float-tone').replace('float_hsl','float_tone')
source=source.replace('test_float_selective_hsl','test_float_tone').replace('native_hsl_records','native_tone_records')
source=source.replace("names+=['test_float_balance'","names+=['test_float_selective_hsl','test_float_balance'")
source=source.replace('==318','==320')
ast.parse(source)
path=ROOT/'scripts/verify_float_tone.py';assert not path.exists()
path.write_text(source,encoding='utf8',newline='\n')
print('prepared source verifier, 320 expected product inputs')
