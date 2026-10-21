"""Prepare a strict publisher by retaining the reviewed V89 staging/registration procedure."""
import ast
import json
from pathlib import Path
import shutil
from run_frozen_regression import sha
ROOT=Path(__file__).resolve().parents[1]
PARENT=Path('E:/dev/sandbox/AI广告剪辑/product/.runtime/offline-media-profile-lab-20261021')
REL=ROOT/'docs/validation/evidence/multicam-affine-clock-20261021-lab'
TARGET=ROOT/'scripts/publish_multicam_affine_clock.py';assert not TARGET.exists()
old=(PARENT/'scripts/publish_offline_media_profile.py').read_text('utf8')
tree=ast.parse(old);node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
body=ast.get_source_segment(old,node)
changes={"'full_methods': 2043":"'full_methods': 2084","full_methods=2043":"full_methods=2084",
    "'targeted_methods': 260":"'targeted_methods': 157","'resources': 161":"'resources': 162",
    "'frozen_files': 260":"'frozen_files': 263",
    'feat: ship verified NumPy in the default offline media runtime':'feat: calibrate local camera clocks and preserve float resampling precision',
    'V89 media-analysis-v1 eight-wheel offline runtime including pinned NumPy; native operation/origin audit and tracked complete wheelhouse; no full CapCut parity acceptance':
        'V90 explicit affine device clock with bounded observed intervals, preserved calibration rates and float PCM; native/isolated controls and actual2084 complete suite; no full CapCut parity acceptance'}
for before,after in changes.items():
    assert before in body,before
    body=body.replace(before,after)
prefix=(ROOT/'scripts/multicam_affine_publication_prefix.py.txt').read_text('utf8')
source=prefix+'\n\n'+body+"\n\nif __name__=='__main__':main()\n"
ast.parse(source);TARGET.write_text(source,encoding='utf8',newline='\n')
helper=ROOT/'scripts/native_index_release_tools.py';assert not helper.exists()
shutil.copyfile(PARENT/'scripts/native_index_release_tools.py',helper)
(REL/'publication-preparation-r1.json').write_text(json.dumps({'status':'prepared-awaiting-actual2084',
    'original_publisher':str(PARENT/'scripts/publish_offline_media_profile.py'),'original_sha256':sha(PARENT/'scripts/publish_offline_media_profile.py'),
    'generic_main_ast_copied':True,'precise_main_changes':changes,'prefix_sha256':sha(ROOT/'scripts/multicam_affine_publication_prefix.py.txt'),
    'publisher_sha256':sha(TARGET),'helper_sha256':sha(helper),'main_written':False,'full_receipt_fabricated':False},ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
print('prepared',TARGET.name)
