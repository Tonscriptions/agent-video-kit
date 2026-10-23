"""Reuse the actual native CLI/PCM/PNG harness, replacing original authored looks."""
import ast
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT.parent/'float-keyer-lab-20261023'
source=(PARENT/'scripts/smoke_float_keyer_media.py').read_text(encoding='utf8')
source=source.replace('keyer','shaper').replace('KEYER','SHAPER').replace('330 source','331 source').replace('== 330','== 331')

def replace(old,new):
    global source
    assert source.count(old)==1,(old,source.count(old))
    source=source.replace(old,new)

replace('Original floating green-blue color key feather and despill demo','Original standalone 1D and Resolve shaper LUT grading demo')
start=source.index('                phase = i//4\n')
end=source.index('                left = 12+i*11\n',start)
source=source[:start]+'''                frame[:, :, :3] = np.stack((.02+.96*x/(w-1), .03+.91*y/(h-1),
                    .08+.78*(.5+.5*np.sin((x+y+9*i)/29))), 2)
'''+source[end:]
replace("        save_ledger(project_root, ledger)",'''        from ai_ad_editor.lut_library import prepare_lut_registration, register_lut
        from shaper_media_oracle import write_tables
        for lut_source in write_tables(assets/'original-luts'):
            lut_record=register_lut(project_root,prepare_lut_registration(project_root,lut_source,lut_id=lut_source.stem))
            add_record(ledger,{'asset_id':lut_record['id'],'kind':'lut','verification_status':'verified',
                'source_type':'generated','source_url':str(lut_source),'license_spdx':'CC0-1.0',
                'evidence':str(ROOT/'scripts/shaper_media_oracle.py'),'permitted_uses':['all'],
                'sha256':lut_record['sha256'],'verified_by':'original-numeric-shaper-generator'})
        save_ledger(project_root, ledger)
        shutil.copyfile(project_root/'assets/lut-library.json',assets/'lut-library.json')''')
replace('all selected CLI RGB match independent color-distance matte dense feather and despill oracle',
    'all selected CLI RGB match independent Hermite 1D and ordered 3D shaper oracle')
start=source.index("        record['shaper_oracle'] =") if "        record['shaper_oracle'] =" in source else source.index("        record['shaper_oracle']={")
end=source.index("        (assets/'author-project.json')",start)
source=source[:start]+'''        record['shaper_oracle']={'delivery_range_policy':'clip','unclipped_linear_min':raw_min,'unclipped_linear_max':raw_max,
            'unclipped_outside_RGB_components':raw_outside,'maximum_linear_absolute_error':difference,'RGB_values':int(actual_rgb.size),
            'scenarios':list(METHODS),'frames_per_scenario':4,
            'animation':'original clip-local intensity ease_in_out and exposure ease_in',
            'effect_order':'exposure/LUT for 1d_cubic; LUT/exposure otherwise',
            'one_d_interpolations':['linear','cubic','spline','cosine','nearest'],
            'three_d_interpolations':['trilinear','tetrahedral'],
            'source_alpha_gradient':True,'oracle':'independent-Hermite-endpoint-tangents-and-3D-cell-weights',
            'oracle_sha256':sha(ROOT/'scripts/shaper_media_oracle.py'),'integer_intermediate':False}
'''+source[end:]
source=source.replace('Original RGB/chroma key feather and despill recipe','Original numeric 1D and Resolve shaper LUT recipe')
source=source.replace('floating-shaper','floating-shaper')
source=source.replace('p in assets.iterdir()','p in assets.rglob(\'*\')')
source=source.replace('COLOR KEY + DESPILL','1D LUT + SHAPER')
ast.parse(source)
destination=ROOT/'scripts/smoke_float_shaper_media.py'
assert not destination.exists()
destination.write_text(source,encoding='utf8',newline='\n')
print('created actual public render, preview and independent shaper media harness')
