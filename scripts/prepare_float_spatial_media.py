"""Prepare the original public CLI mean-filter replay, including isolated mode."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT.parent/'float-gaussian-lab-20261022/scripts/smoke_float_gaussian_media.py').read_text('utf8')
source = source.replace('float-gaussian', 'float-spatial').replace('float_gaussian', 'float_spatial')
source = source.replace('gaussian_media_oracle', 'spatial_media_oracle').replace('gaussian_oracle', 'spatial_oracle')
source = source.replace('Gaussian direction planes and premultiplied coverage', 'average and box blur boundaries and premultiplied coverage')
source = source.replace('Gaussian direction and coverage recipe', 'average and box blur boundary and coverage recipe')
source = source.replace('GAUSSIAN BLUR', 'SPATIAL MEANS').replace('floating-Gaussian-', 'floating-spatial-means-')
source = source.replace('independent independent blurred-coverage boundary-system matrix oracle', 'independent finite-window tap and boundary-index matrix oracle')
source = source.replace('horizontal radius uses time-root Bezier', 'box radius uses time-root Bezier')
source = source.replace('exposure/Gaussian for premult_headroom; Gaussian/exposure otherwise', 'exposure/average for premult_headroom; mean/exposure otherwise')
source = source.replace('independent-dense-boundary-linear-systems-matrix-powers-blurred-coverage-and-source-exposure-equations',
                        'independent-dense-finite-taps-boundary-index-matrix-powers-blurred-coverage-and-source-exposure-equations')
source = source.replace('323 source inputs', '326 source inputs').replace('== 323', '== 326')
ast.parse(source)
target = ROOT/'scripts/smoke_float_spatial_media.py'; assert not target.exists()
target.write_text(source, encoding='utf8', newline='\n')
print('prepared original five-scene20-frame public CLI means demo; predeclared linear error2e-6')
