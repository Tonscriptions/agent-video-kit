"""Adapt the accepted fresh eight-wheel proof for crop and all parent modules."""
import ast
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT.parent/'float-mask-lab-20261022'
source=(PARENT/'scripts/verify_float_mask_install.py').read_text('utf8')
for old,new in [('float-mask-20261022','float-crop-20261022'),('smoke_float_mask_media.py','smoke_float_crop_media.py'),
    ('installed-r2','installed-r1'),('foundation-r2.json','foundation-r1.json'),('native-r3','native-r2'),('media-r4','media-r1'),
    ('floating-masks','floating-crops'),('295','323'),('182','183'),('304','306'),('95 methods','123 methods'),("['methods'] == 95","['methods'] == 123")]:
    assert old in source,old
    source=source.replace(old,new)
old="'test_float_exposure', 'test_float_mask']"
assert source.count(old)==1
source=source.replace(old,"'test_float_exposure', 'test_float_mask', 'test_float_crop']")
old="native_float_mask_integrated=True, default_backend_migrated=False"
assert source.count(old)==1
source=source.replace(old,'native_float_mask_integrated=True, native_float_crop_integrated=True, default_backend_migrated=False')
old="and media['actual_public_preview_CLI_processes'] == 3)"
assert source.count(old)==1
source=source.replace(old,"and media['actual_public_preview_CLI_processes'] == 3 and media['frozen_after'] == before)")
ast.parse(source)
path=ROOT/'scripts/verify_float_crop_install.py';assert not path.exists()
path.write_text(source,encoding='utf8',newline='\n')
print('created offline isolated crop verifier; 323 planned methods, not run yet')
