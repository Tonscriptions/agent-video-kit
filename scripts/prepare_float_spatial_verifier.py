"""Prepare the frozen source/real-native spatial verifier from its parent."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT.parent/'float-gaussian-lab-20261022/scripts/verify_float_gaussian.py').read_text('utf8')
source = source.replace('float-gaussian', 'float-spatial').replace('float_gaussian', 'float_spatial')
source = source.replace('native_gaussian_records', 'native_spatial_records')
source = source.replace("names+=['test_float_tone'", "names+=['test_float_gaussian','test_float_tone'")
source = source.replace('==323', '==326')
ast.parse(source)
target = ROOT/'scripts/verify_float_spatial.py'
assert not target.exists()
target.write_text(source, encoding='utf8', newline='\n')
print('prepared unexecuted spatial source verifier; expected326 inputs')
