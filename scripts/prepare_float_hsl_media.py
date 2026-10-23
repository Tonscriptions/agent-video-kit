"""Adapt the accepted real public CLI harness; preserve all checks and media."""
import ast
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT.parent/'float-balance-lab-20261022'
source=(PARENT/'scripts/smoke_float_balance_media.py').read_text('utf8')
source=source.replace('float-balance','float-hsl').replace('float_balance','float_hsl').replace('balance_media_oracle','hsl_media_oracle')
source=source.replace('floating three-way balance and creative Kelvin demo','floating eight-band HSL and explicit gamut policies demo')
source=source.replace('THREE-WAY COLOR / KELVIN','EIGHT-BAND HSL')
source=source.replace('source-alpha binary64 balance and colorsys HSL oracle','source-alpha independent scalar colorsys HSL and neighboring bands oracle')
source=source.replace("record['balance_oracle']","record['hsl_oracle']")
source=source.replace("'effect_order':'exposure/wheel for midrange, color/exposure otherwise','animated_channels':['red','midtones_green','shadows_red','kelvin','intensity','amount']",
    "'effect_order':'exposure/HSL for clip and residual; HSL/exposure otherwise','animated_channels':['red_hue','orange_saturation','blue_hue','green_hue','intensity','amount']")
source=source.replace('.2 to .85 quadratic ease_in_out; Kelvin uses direct Bezier; original clip-local author tick',
    '.2 to .85 quadratic ease_in_out; blue hue uses time-root Bezier; green hue holds; original clip-local author tick')
source=source.replace('independent-binary64-minmax-weights-colorsys-HSL-midrange-and-source-exposure-equations',
    'independent-scalar-colorsys-neighbor-HSL-explicit-residual-and-source-exposure-equations')
source=source.replace('316 source inputs','318 source inputs').replace('== 316)','== 318)')
source=source.replace('Original three-way balance recipe','Original eight-band HSL recipe')
source=source.replace('passed-public-CLI-floating-levels-and-native-float-previews','passed-public-CLI-floating-selective-HSL-and-native-float-previews')
ast.parse(source)
path=ROOT/'scripts/smoke_float_hsl_media.py';assert not path.exists()
path.write_text(source,encoding='utf8',newline='\n')
print('prepared five-scene public HSL CLI harness; linear RGB tolerance predeclared: 2e-6')
