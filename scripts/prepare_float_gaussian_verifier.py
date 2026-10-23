"""Prepare a source verifier; it records executed inputs and actual native I/O."""
import ast
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT.parent/'float-tone-lab-20261022/scripts/verify_float_tone.py').read_text('utf8')
source=source.replace('float-tone','float-gaussian').replace('float_tone','float_gaussian')
source=source.replace('native_tone_records','native_gaussian_records')
source=source.replace("names+=['test_float_selective_hsl'","names+=['test_float_tone','test_float_selective_hsl'")
source=source.replace('==320','==323')
ast.parse(source)
target=ROOT/'scripts/verify_float_gaussian.py';assert not target.exists()
target.write_text(source,encoding='utf8',newline='\n')
print('prepared unexecuted Gaussian verifier: 323 expected frozen product inputs')
