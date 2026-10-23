"""Observe parent spatial admission before designing bounded 4K support."""
from datetime import datetime,timezone
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT.parent/'float-gaussian-lab-20261022'
REL=ROOT/'docs/validation/evidence/float-spatial-20261022-lab'
sys.path[:0]=[str(PARENT/'product/src'),str(PARENT/'scripts')]
from run_frozen_regression import frozen,sha
from ai_ad_editor.runtime import configure_local_runtime
configure_local_runtime()
import numpy as np
from ai_ad_editor.errors import AppError
from ai_ad_editor.float_color_signal import ColorSignal
from ai_ad_editor.float_gaussian import compile_gaussian,apply_gaussian,MAX_WORKING_BYTES


def main():
    REL.mkdir(parents=True,exist_ok=True);target=REL/'admission-probe-r1.json';assert not target.exists()
    before=frozen();assert len(before)==323
    signal={'primaries':'bt709','transfer':'linear'}
    plan=compile_gaussian({'type':'blur','parameters':{'input_signal':signal,'output_signal':signal,'radius':4}})
    value=np.zeros((2160,3840,4),np.float32);code=None
    try:apply_gaussian(value,plan,0,working_signal=ColorSignal(**signal))
    except AppError as exc:code=exc.code
    assert code=='FLOAT_GAUSSIAN_BUDGET',code
    fixed=6*value.nbytes+4*len(plan.tracks_json.encode('utf8'))+1048576
    default_estimate=fixed+min(16384,2160*3840)*2048
    arithmetic_max_tile=(MAX_WORKING_BYTES-fixed)//2048
    assert 0<arithmetic_max_tile<16384 and default_estimate>MAX_WORKING_BYTES
    assert np.count_nonzero(value)==0 and frozen()==before
    row={'status':'confirmed-existing-default-tile-4K-admission-limit','at_utc':datetime.now(timezone.utc).isoformat(),
        'frame':[3840,2160],'raster':'float32-straight-RGBA','actual_error':code,
        'surface_bytes':value.nbytes,'declared_default_estimate':default_estimate,'limit':MAX_WORKING_BYTES,
        'arithmetic_max_tile_under_same_spatial_budget':arithmetic_max_tile,
        'smaller_tile_execution_or_quality_accepted':False,'new_runtime_implemented':False,
        'followup':'Bound conversion/check tiles by remaining budget while retaining full spatial scratch admission; verify pixels/cancellation/installation separately.',
        'primary_next_filter_references':['https://raw.githubusercontent.com/FFmpeg/FFmpeg/n8.1/libavfilter/vf_avgblur.c',
            'https://raw.githubusercontent.com/FFmpeg/FFmpeg/n8.1/libavfilter/vf_boxblur.c'],
        'reference_observations':['Average blur has explicit integer planar formats and edge replication; sizeY zero inherits X and radii clamp to half plane dimensions.',
            'Box blur uses reflected edge samples, fixed-point reciprocal and repeated axis passes; use explicit integer native references, not assumed float compatibility.'],
        'references_read_via_official_web_reader':True,'local_n8_1_sources_claimed_downloaded':False,
        'product_inputs':before,'parent_unchanged':True,'virtualization':False,'full_capcut_parity':False}
    target.write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    (REL/'admission-probe-r1.executed-script.py.txt').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({k:row[k] for k in ('status','actual_error','surface_bytes','declared_default_estimate','limit','arithmetic_max_tile_under_same_spatial_budget')}))


if __name__=='__main__':main()
