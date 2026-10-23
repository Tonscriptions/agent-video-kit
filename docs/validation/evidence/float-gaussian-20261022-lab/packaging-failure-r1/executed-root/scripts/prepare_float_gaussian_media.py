"""Prepare a real public CLI replay using an independent Gaussian oracle."""
import ast
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT.parent/'float-tone-lab-20261022/scripts/smoke_float_tone_media.py').read_text('utf8')
source=source.replace('float-tone','float-gaussian').replace('float_tone','float_gaussian').replace('tone_media_oracle','gaussian_media_oracle')
source=source.replace('floating basic YCbCr tone and scalar coefficient demo','floating Gaussian direction planes and premultiplied coverage demo')
source=source.replace('BASIC YCbCr TONE','GAUSSIAN BLUR').replace('basic YCbCr tone recipe','Gaussian direction and coverage recipe')
source=source.replace('source-alpha independent matrix-solve and scalar tone oracle','independent blurred-coverage boundary-system matrix oracle')
source=source.replace("record['tone_oracle']","record['gaussian_oracle']")
source=source.replace('gamma uses time-root Bezier; contrast holds','horizontal radius uses time-root Bezier; RGB-only radius holds')
source=source.replace("'effect_order':'exposure/tone for native_clip; tone/exposure otherwise'","'effect_order':'exposure/Gaussian for premult_headroom; Gaussian/exposure otherwise'")
source=source.replace("['brightness','gamma','hue','contrast','intensity','amount']","['radius','radius_x','radius_y','intensity','amount']")
source=source.replace('independent-matrix-inverse-and-scalar-YCbCr-tone-author-time-and-source-exposure-equations',
    'independent-dense-boundary-linear-systems-matrix-powers-blurred-coverage-and-source-exposure-equations')
source=source.replace('320 source inputs','323 source inputs').replace('== 320','== 323')
source=source.replace('passed-public-CLI-floating-basic-tone-and-native-float-previews','passed-public-CLI-floating-Gaussian-and-native-float-previews')
ast.parse(source)
path=ROOT/'scripts/smoke_float_gaussian_media.py';assert not path.exists()
path.write_text(source,encoding='utf8',newline='\n')
print('prepared five-scene Gaussian public CLI harness; tolerance predeclared 2e-6')
