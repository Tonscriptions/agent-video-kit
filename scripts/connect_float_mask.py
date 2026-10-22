"""Apply a bounded, reviewed host connection only to this private candidate."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def once(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new)


def main():
    path = ROOT/'product/src/ai_ad_editor/float_timeline.py'
    text = path.read_text('utf8')
    text = once(text, 'from .float_geometry import resample_rgba',
                'from .float_geometry import resample_rgba\nfrom .float_mask import compile_mask, apply_mask')
    text = once(text, 'self.effect_plans={};self.clip_count=0', 'self.effect_plans={};self.mask_plans={};self.clip_count=0')
    start = text.index("                mask=clip.get('mask') or {}")
    end = text.index("                properties=[frame.get('property')", start)
    text = text[:start]+"                self.mask_plans[path]=compile_mask(clip)\n                allowed=TRANSFORM_PROPERTIES|(self.mask_plans[path].properties if self.mask_plans[path] else set())\n"+text[end:]
    start = text.index('    def _mask(')
    end = text.index('    def _project(', start)
    text = text[:start]+text[end:]
    text = once(text, 'def _project(self,clip,surface,canvas,tick):', 'def _project(self,clip,surface,canvas,tick,path):')
    start = text.index('        mask=self._mask(')
    end = text.index('        result,_=resample_rgba', start)
    text = text[:start]+"        mask_metadata=None\n        if self.mask_plans[path] is not None:\n            surface,mask_metadata=apply_mask(surface,self.mask_plans[path],tick,max_working_bytes=self.max_working_bytes,cancel=self.poll)\n"+text[end:]
    text = once(text, 'return result,opacity,inverse', 'return result,opacity,inverse,mask_metadata')
    text = once(text, 'layer,opacity,inverse=self._project(clip,source,canvas,tick)', 'layer,opacity,inverse,mask_metadata=self._project(clip,source,canvas,tick,path)')
    text = once(text, "'opacity':opacity,'effects':effect_metadata", "'opacity':opacity,'effects':effect_metadata,'mask':mask_metadata")
    path.write_text(text, encoding='utf8', newline='\n')
    path = ROOT/'product/tests/test_float_timeline.py'
    text = path.read_text('utf8')
    text = once(text, "('mask',{'type':'polygon'}),('mask',{'type':'circle','feather':.1})", "('mask',{'type':'gradient'}),('mask',{'type':'rounded_rectangle'})")
    path.write_text(text, encoding='utf8', newline='\n')
    path = ROOT/'product/src/ai_ad_editor/capabilities.py'
    text = path.read_text('utf8')
    anchor = '        "capabilities": {\n'
    addition = '''            'timeline_native_float_mask': {
                'status':'implemented_with_limits', 'protocol':'author-clock-float32-alpha-mask-v1',
                'selection':'settings.pixel_pipeline.engine=float32-native-v1',
                'commands':['render','preview.range','preview.frame'],
                'features':['rectangle_circle_ellipse','even_odd_polygon','sampled_line_and_cubic_path',
                    'clip_and_mask_local_keyframes','original_author_clock','invert','source_alpha_preserved',
                    'static_alpha_only_symmetric_box2','animated_inner_distance_feather',
                    'straight_RGB_bits_preserved_before_affine','bounded_tiles_and_cancellation'],
                'limits':['32_path_candidate_points_8_segments','cubic_is_sampled_polyline_not_analytic',
                    'ellipse_distance_is_normalized_radial_approximation',
                    'static_and_animated_feather_have_distinct_authored_semantics',
                    'workspace_estimate_not_total_RSS','no_natural_HDR_or_full_CapCut_parity_acceptance'],
            },
'''
    text = once(text, anchor, anchor+addition)
    path.write_text(text, encoding='utf8', newline='\n')
    print('connected independent Float32 mask in private candidate only')


if __name__ == '__main__':
    main()
