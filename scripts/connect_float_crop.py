"""Connect only the new crop projection; assert each parent anchor once."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT/'product/src/ai_ad_editor/float_timeline.py'
source = path.read_text(encoding='utf8')


def replace(old, new):
    global source
    assert source.count(old) == 1, old
    source = source.replace(old, new)


replace('from .float_mask import compile_mask, apply_mask', 'from .float_mask import compile_mask, apply_mask\nfrom .float_crop import compile_crop, project_crop')
replace('self.mask_plans={};self.clip_count=0', 'self.mask_plans={};self.crop_plans={};self.clip_count=0')
replace("('transition_in','transition_out','crop','generator','subtitle','tracking_binding')", "('transition_in','transition_out','generator','subtitle','tracking_binding')")
replace('self.mask_plans[path]=compile_mask(clip)\n                allowed=TRANSFORM_PROPERTIES|(self.mask_plans[path].properties if self.mask_plans[path] else set())',
    'self.mask_plans[path]=compile_mask(clip)\n                self.crop_plans[path]=compile_crop(clip)\n                allowed=TRANSFORM_PROPERTIES|(self.mask_plans[path].properties if self.mask_plans[path] else set())|(self.crop_plans[path].properties if self.crop_plans[path] else set())')
replace("        height,width=surface.shape[:2];cw,ch=canvas['width'],canvas['height']", """        height,width=surface.shape[:2];cw,ch=canvas['width'],canvas['height']
        if self.crop_plans[path] is not None:
            result,crop_metadata=project_crop(surface,self.crop_plans[path],tick,(cw,ch),scale=scale,rotation=angle,
                position=(px,py),anchor=(ax,ay),max_working_bytes=self.max_working_bytes,cancel=self.poll)
            mask_metadata=None
            if self.mask_plans[path] is not None:
                result,mask_metadata=apply_mask(result,self.mask_plans[path],tick,max_working_bytes=self.max_working_bytes,cancel=self.poll)
            return result,opacity,crop_metadata['inverse'],mask_metadata,crop_metadata""")
replace('return result,opacity,inverse,mask_metadata', 'return result,opacity,inverse,mask_metadata,None')
replace('layer,opacity,inverse,mask_metadata=self._project', 'layer,opacity,inverse,mask_metadata,crop_metadata=self._project')
replace("'effects':effect_metadata,'mask':mask_metadata", "'effects':effect_metadata,'mask':mask_metadata,'crop':crop_metadata")
path.write_text(source,encoding='utf8',newline='\n')
path = ROOT/'product/tests/test_float_timeline.py'
source = path.read_text(encoding='utf8')
old = "('crop',{'x':0})"
assert source.count(old) == 1
path.write_text(source.replace(old,"('generator',{'type':'color'})"),encoding='utf8',newline='\n')
path = ROOT/'product/src/ai_ad_editor/capabilities.py'
source = path.read_text(encoding='utf8')
anchor = "        \"capabilities\": {\n"
assert source.count(anchor) == 1
source = source.replace(anchor, anchor+"""            'timeline_native_float_crop': {
                'status':'implemented_with_limits', 'protocol':'author-clock-float32-crop-projection-v1',
                'selection':'settings.pixel_pipeline.engine=float32-native-v1',
                'commands':['render','preview.range','preview.frame'],
                'features':['pixel_and_normalized_units','fit_fill_stretch','static_and_animated_xy_width_height',
                    'clip_and_crop_local_keyframes','six_author_interpolations','original_author_clock',
                    'leaf_static_rounding_and_position_only_truncation','continuous_compound_crop',
                    'single_pass_crop_fit_TRS','fill_overscan_retained_until_final_canvas',
                    'premultiplied_alpha_sampling','parent_canvas_mask_after_crop_projection',
                    'bounded_tiles_and_cancellation'],
                'limits':['nearest_or_bilinear_not_area_or_lanczos','transparent_fit_bars',
                    'not_legacy_integer_filter_byte_equivalence',
                    'workspace_estimate_not_total_RSS','no_natural_HDR_or_full_CapCut_parity_acceptance'],
            },
""")
path.write_text(source,encoding='utf8',newline='\n')
print('connected crop host/capability; parent unsupported fixture now tests generator')
