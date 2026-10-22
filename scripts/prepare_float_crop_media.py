"""Adapt actual public CLI harness; keep originals and verify helper identity."""
import ast
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT.parent/'float-mask-lab-20261022'
source=(PARENT/'scripts/smoke_float_mask_media.py').read_text('utf8')
source=source.replace('mask','crop').replace('MASKS + FEATHER','CROP + CAMERA PATH')


def replace(old,new,count=1):
    global source
    assert source.count(old)==count,(old,source.count(old))
    source=source.replace(old,new)


replace('from crop_media_oracle import clip_crop,curve_crop,expected_rgb', 'from crop_media_oracle import clip_crop,curve_crop,clip_motion,curve_motion,expected_rgb')
replace('source_out_tick=90000,crop=clip_crop())','source_out_tick=90000,crop=clip_crop(),keyframes=clip_motion())')
replace('source_out_tick=180000,crop=curve_crop())',"source_out_tick=180000,crop=curve_crop(),keyframes=curve_motion(),transform={'anchor':{'x':.45,'y':.55},'position':{'x':.53,'y':.49}})")
replace("'static_polygon_frames':list(range(3,10)),'dynamic_cubic_frames':list(range(10,17))", "'fixed_size_animated_origin_frames':list(range(3,10)),'animated_size_TRS_frames':list(range(10,17))")
replace('independent-direct-sums-polynomial-ray-crossing','independent-forward-homogeneous-matrix-and-separable-premultiplied-bilinear')
replace('independent source-alpha crop feather and composite oracle','independent source-alpha crop forward-transform and composite oracle')
replace('No third-party footage, voice, music, font, model or likeness.', 'No third-party footage, voice, music, model or likeness. Labels use the bundled Pillow default font; no font file is separately redistributed.')
source=source.replace('304 source inputs','306 source inputs').replace("== 304)","== 306)")
replace("        (rel/'executed-script.py.txt').write_bytes(Path(__file__).read_bytes())", "        (rel/'executed-script.py.txt').write_bytes(Path(__file__).read_bytes())\n        (rel/'executed-oracle.py.txt').write_bytes((ROOT/'scripts/crop_media_oracle.py').read_bytes())")
ast.parse(source)
path=ROOT/'scripts/smoke_float_crop_media.py';assert not path.exists()
path.write_text(source,encoding='utf8',newline='\n')
print('created source/isolated real crop CLI media harness')
