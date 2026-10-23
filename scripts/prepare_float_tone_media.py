"""Reuse the verified CLI harness with an independent basic-tone recipe."""
import ast
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT.parent/'float-hsl-lab-20261022/scripts/smoke_float_hsl_media.py').read_text('utf8')
source=source.replace('float-hsl','float-tone').replace('float_hsl','float_tone').replace('hsl_media_oracle','tone_media_oracle')
source=source.replace('floating eight-band HSL and explicit gamut policies demo','floating basic YCbCr tone and scalar coefficient demo')
source=source.replace('EIGHT-BAND HSL','BASIC YCbCr TONE').replace('eight-band HSL recipe','basic YCbCr tone recipe')
source=source.replace('source-alpha independent scalar colorsys HSL and neighboring bands oracle','source-alpha independent matrix-solve and scalar tone oracle')
source=source.replace("record['hsl_oracle']","record['tone_oracle']")
source=source.replace('blue hue uses time-root Bezier; green hue holds','gamma uses time-root Bezier; contrast holds')
source=source.replace("'effect_order':'exposure/HSL for clip and residual; HSL/exposure otherwise'","'effect_order':'exposure/tone for native_clip; tone/exposure otherwise'")
source=source.replace("['red_hue','orange_saturation','blue_hue','green_hue','intensity','amount']","['brightness','gamma','hue','contrast','intensity','amount']")
source=source.replace('independent-scalar-colorsys-neighbor-HSL-explicit-residual-and-source-exposure-equations',
    'independent-matrix-inverse-and-scalar-YCbCr-tone-author-time-and-source-exposure-equations')
source=source.replace('318 source inputs','320 source inputs').replace('== 318','== 320')
source=source.replace('passed-public-CLI-floating-selective-HSL-and-native-float-previews','passed-public-CLI-floating-basic-tone-and-native-float-previews')
ast.parse(source)
path=ROOT/'scripts/smoke_float_tone_media.py';assert not path.exists()
path.write_text(source,encoding='utf8',newline='\n')
print('prepared five-scene tone public CLI harness; tolerance predeclared 2e-6')
