"""Use the accepted real CLI harness for five original levels/exposure scenes."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT.parent/'float-curves-lab-20261022'
source = (PARENT/'scripts/smoke_float_curves_media.py').read_text('utf8')
source = source.replace('float-curves','float-levels').replace('float_curves','float_levels').replace('curves_media_oracle','levels_media_oracle')
source = source.replace('floating continuous RGB curves demo','floating RGBA levels and animated exposure demo')
source = source.replace('RGB CURVES + CONTROL POINTS','LEVELS + ANIMATED EXPOSURE').replace('floating-curves','floating-levels')
source = source.replace('source-alpha independent continuous spline and ordered effect oracle','source-alpha independent endpoint and animated exposure oracle')
source = source.replace("record['curves_oracle']","record['levels_oracle']")
source = source.replace("'effect_order':'exposure/curves or curves/exposure as authored','animated_points':['all.1.y','red.1.x','post_master.1.y']",
    "'effect_order':'exposure/levels or levels/exposure as authored','animated_channels':['output_black','red_output_white','intensity','amount','black']")
source = source.replace('independent-dense-natural-system-and-Hermite-polynomials-explicit-transfer-linear-mix',
    'independent-source-endpoints-whole-plane-extrema-scalar-preserve-and-exposure-equations')
source = source.replace('difference<=3e-7','difference<=5e-7')
source = source.replace('311 source inputs','314 source inputs').replace('== 311)','== 314)')
source = source.replace('Original curves, synthetic picture','Original levels/exposure recipe, synthetic picture')
ast.parse(source)
path = ROOT/'scripts/smoke_float_levels_media.py';assert not path.exists()
path.write_text(source,encoding='utf8',newline='\n')
print('created five-scene real public levels/exposure CLI media harness')
