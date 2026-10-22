"""Adapt byte-proven mask validation without modifying its live frozen files."""
import ast
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT.parent/'float-mask-lab-20261022'
source=(PARENT/'scripts/verify_float_mask.py').read_text('utf8')
for old,new,count in [
    ('float-mask-20261022-lab','float-crop-20261022-lab',1),
    ('len(before)==304','len(before)==306',1),
    ('foundation-r2.json','foundation-r1.json',1),
    ("names=['test_float_mask']","names=['test_float_crop']",1),
    ("names+=['test_float_exposure'","names+=['test_float_mask','test_float_exposure'",1),
]:
    assert source.count(old)==count,(old,source.count(old))
    source=source.replace(old,new)
ast.parse(source)
path=ROOT/'scripts/verify_float_crop.py'
assert not path.exists()
path.write_text(source.replace('Run native exposure','Run native crop'),encoding='utf8',newline='\n')
print('created native crop verifier')
