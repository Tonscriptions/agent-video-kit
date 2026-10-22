"""Adapt the accepted native CLI harness to five original RGB curve segments."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT.parent/'float-lut-lab-20261022'
source = (PARENT/'scripts/smoke_float_lut_media.py').read_text('utf8')
source = source.replace('float-lut','float-curves').replace('float_lut','float_curves').replace('lut_media_oracle','curves_media_oracle')
source = source.replace('floating local LUT grading demo','floating continuous RGB curves demo')
source = source.replace('5 LUT MODES + INTENSITY','RGB CURVES + CONTROL POINTS').replace('floating-LUTs','floating-curves')
source = source.replace('    from ai_ad_editor.lut_library import prepare_lut_registration, register_lut\n','')
start = source.index('        from curves_media_oracle import write_original_cube, effects, expected_rgb, METHODS')
stop = source.index("        sequence = p['sequences'][0]",start)
source = source[:start]+'''        save_ledger(project_root, ledger)
        from curves_media_oracle import effects, expected_rgb, METHODS
'''+source[stop:]
source = source.replace('source-alpha LUT colour-system and ordered effect oracle','source-alpha independent continuous spline and ordered effect oracle')
source = source.replace("record['lut_oracle']","record['curves_oracle']")
source = source.replace("'interpolations':list(METHODS),'frames_per_interpolation':4,'intensity':'.15 to .9 ease_in_out;original clip-local author tick','effect_order':'exposure/lut or lut/exposure as authored'",
    "'scenarios':list(METHODS),'frames_per_scenario':4,'intensity':'.2 to .85 ease_in_out or direct Bezier;original clip-local author tick','effect_order':'exposure/curves or curves/exposure as authored','animated_points':['all.1.y','red.1.x','post_master.1.y']")
source = source.replace('independent-polynomial-and-barycentric-linear-systems-explicit-transfer-and-linear-mix','independent-dense-natural-system-and-Hermite-polynomials-explicit-transfer-linear-mix')
source = source.replace('309 source inputs','311 source inputs').replace('== 309)','== 311)')
source = source.replace('Original CUBE, synthetic picture','Original curves, synthetic picture')
ast.parse(source)
path = ROOT/'scripts/smoke_float_curves_media.py';assert not path.exists()
path.write_text(source,encoding='utf8',newline='\n')
print('created five-scenario real public RGB curve CLI media harness')
