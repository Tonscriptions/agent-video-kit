"""Adapt the accepted real CLI harness to five local LUT author segments."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT.parent/'float-crop-lab-20261022'
source = (PARENT/'scripts/smoke_float_crop_media.py').read_text('utf8')
source = source.replace('float-crop','float-lut').replace('float_crop','float_lut').replace('crop_media_oracle','lut_media_oracle')
source = source.replace('floating alpha crops demo','floating local LUT grading demo')
source = source.replace('CROP + CAMERA PATH','5 LUT MODES + INTENSITY').replace('floating-crops','floating-LUTs')


def replace(old,new):
    global source
    assert source.count(old)==1,(old,source.count(old))
    source = source.replace(old,new)


replace("    from ai_ad_editor.rights import add_record, load_ledger, save_ledger",
    "    from ai_ad_editor.rights import add_record, load_ledger, save_ledger\n    from ai_ad_editor.lut_library import prepare_lut_registration, register_lut")
replace("        save_ledger(project_root, ledger)",
    """        from lut_media_oracle import write_original_cube, effects, expected_rgb, METHODS
        lut_source = assets/'original-look.cube'
        write_original_cube(lut_source)
        lut_record = register_lut(project_root,prepare_lut_registration(project_root,lut_source,lut_id='original_look'))
        add_record(ledger,{'asset_id':lut_record['id'],'kind':'lut','verification_status':'verified',
            'source_type':'generated','source_url':str(lut_source),'license_spdx':'CC0-1.0',
            'evidence':str(ROOT/'scripts/lut_media_oracle.py'),'permitted_uses':['all'],
            'sha256':lut_record['sha256'],'verified_by':'original-numeric-table-generator'})
        save_ledger(project_root, ledger)
        shutil.copyfile(project_root/'assets/lut-library.json',assets/'lut-library.json')""")
old = """        from lut_media_oracle import clip_crop,curve_crop,clip_motion,curve_motion,expected_rgb
        base.update(duration_tick=90000,source_out_tick=90000,crop=clip_crop(),keyframes=clip_motion())
        curve=copy.deepcopy(base)
        curve.update(id='curve_clip',timeline_start_tick=90000,source_in_tick=90000,source_out_tick=180000,crop=curve_crop(),keyframes=curve_motion(),transform={'anchor':{'x':.45,'y':.55},'position':{'x':.53,'y':.49}})
        sequence['tracks'][0]['clips']=[base,curve]"""
replace(old,"""        sequence['tracks'][0]['clips'] = [dict(base,id='look_'+method,timeline_start_tick=i*36000,
            source_in_tick=i*36000,source_out_tick=(i+1)*36000,duration_tick=36000,effects=effects(method))
            for i,method in enumerate(METHODS)]""")
replace('source-alpha crop forward-transform and composite oracle','source-alpha LUT colour-system and ordered effect oracle')
replace("record['crop_oracle']", "record['lut_oracle']")
replace("'fixed_size_animated_origin_frames':list(range(3,10)),'animated_size_TRS_frames':list(range(10,17))",
    "'interpolations':list(METHODS),'frames_per_interpolation':4,'intensity':'.15 to .9 ease_in_out;original clip-local author tick','effect_order':'exposure/lut or lut/exposure as authored'")
replace('independent-forward-homogeneous-matrix-and-separable-premultiplied-bilinear','independent-polynomial-and-barycentric-linear-systems-explicit-transfer-and-linear-mix')
source = source.replace('306 source inputs','309 source inputs').replace('== 306)','== 309)')
source = source.replace('Synthetic picture and sine-wave audio generated', 'Original CUBE, synthetic picture and sine-wave audio generated')
ast.parse(source)
path = ROOT/'scripts/smoke_float_lut_media.py'
assert not path.exists()
path.write_text(source,encoding='utf8',newline='\n')
print('created five-mode real public LUT CLI media harness')
