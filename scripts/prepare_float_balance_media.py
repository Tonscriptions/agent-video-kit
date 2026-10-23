"""Adapt the accepted real public CLI harness, preserving its checks and media."""
import ast
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT.parent/'float-levels-lab-20261022'
source=(PARENT/'scripts/smoke_float_levels_media.py').read_text('utf8')
source=source.replace('float-levels','float-balance').replace('float_levels','float_balance').replace('levels_media_oracle','balance_media_oracle')
source=source.replace('floating RGBA levels and animated exposure demo','floating three-way balance and creative Kelvin demo')
source=source.replace('LEVELS + ANIMATED EXPOSURE','THREE-WAY COLOR / KELVIN')
source=source.replace('source-alpha independent endpoint and animated exposure oracle','source-alpha binary64 balance and colorsys HSL oracle')
source=source.replace("record['levels_oracle']","record['balance_oracle']")
source=source.replace("'effect_order':'exposure/levels or levels/exposure as authored','animated_channels':['output_black','red_output_white','intensity','amount','black']",
    "'effect_order':'exposure/wheel for midrange, color/exposure otherwise','animated_channels':['red','midtones_green','shadows_red','kelvin','intensity','amount']")
source=source.replace('.2 to .85 ease_in_out or direct Bezier;original clip-local author tick',
    '.2 to .85 quadratic ease_in_out; Kelvin uses direct Bezier; original clip-local author tick')
source=source.replace('independent-source-endpoints-whole-plane-extrema-scalar-preserve-and-exposure-equations',
    'independent-binary64-minmax-weights-colorsys-HSL-midrange-and-source-exposure-equations')
source=source.replace('difference<=5e-7','difference<=2e-6').replace('maximum_linear_absolute_error=difference,','maximum_linear_absolute_error=difference,predeclared_tolerance=2e-6,')
source=source.replace('314 source inputs','316 source inputs').replace('== 314)','== 316)')
source=source.replace('Original levels/exposure recipe','Original three-way balance recipe')
source=source.replace("'output_signal': signal, 'window_frames': 3", "'output_signal': signal, 'range_policy': 'clip', 'window_frames': 3")
source=source.replace("        expected=expected_rgb(source_planes,list(range(3,17)))\n",
    "        unclipped_expected=expected_rgb(source_planes,list(range(3,17)))\n"
    "        raw_min,raw_max=float(unclipped_expected.min()),float(unclipped_expected.max())\n"
    "        raw_outside=int(np.count_nonzero((unclipped_expected<0)|(unclipped_expected>1)))\n"
    "        check('real headroom reaches explicit clip delivery edge',raw_max>1 and raw_outside>0,raw_linear_min=raw_min,raw_linear_max=raw_max,raw_outside_RGB_components=raw_outside)\n"
    "        check('formal and preview report explicit delivery clipping',decoded['edited']['manifest']['delivery']['pixel_pipeline']['transport']['clipped_RGB_components']>0 and ranged['pixel_pipeline']['transport']['clipped_RGB_components']>0)\n"
    "        expected=np.clip(unclipped_expected,0,1)\n")
source=source.replace("record['balance_oracle']={'maximum_linear_absolute_error':difference,",
    "record['balance_oracle']={'delivery_range_policy':'clip','unclipped_linear_min':raw_min,'unclipped_linear_max':raw_max,'unclipped_outside_RGB_components':raw_outside,'maximum_linear_absolute_error':difference,")
ast.parse(source)
path=ROOT/'scripts/smoke_float_balance_media.py';assert not path.exists()
path.write_text(source,encoding='utf8',newline='\n')
print('prepared five-scene real public balance CLI harness; RGB tolerance declared before execution: 2e-6')
