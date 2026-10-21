"""Independent native interval oracle for ordinary flattened nested video."""
from bisect import bisect_left,bisect_right
import copy
from fractions import Fraction
from decimal import Decimal,localcontext
import unittest

from ai_ad_editor.project import save_project
import test_cfr_boundaries as helpers


class NestedNativeClockTests(unittest.TestCase):
    setUp=helpers.CFRBoundaryTests.setUp
    run_native=helpers.CFRBoundaryTests.run_native
    source=helpers.CFRBoundaryTests.source
    project=helpers.CFRBoundaryTests.project
    render=helpers.CFRBoundaryTests.render

    def check(self,*,leaf_reverse=False,parent_reverse=False,vfr=True,speed=Fraction(3,2),
              start=9900,source_in=10170,curve=False,ramp=False,offset=None,short_source=False,deep=False,outer_reverse=False):
        points=[0,33,101,188,195,441,499,800,1002,1221,1600,1800] if vfr else None
        if short_source:points=points[:8]
        source,colors,times=self.source(count=len(points) if points else 55,vfr=points,
            container='mkv' if short_source else 'nut',audio_tail=short_source)
        if offset is not None:
            from ai_ad_editor.media import ffmpeg_path
            transformed=self.work/'offset.nut'
            self.run_native([ffmpeg_path(),'-v','error','-i',source,'-output_ts_offset',offset,
                '-fps_mode','passthrough','-enc_time_base','filter','-c:v','ffv1','-pix_fmt','bgra',transformed])
            source=transformed
        p,root,leaf=self.project(source,start=0,duration=117000,source_out=117000,
                                 patch={'reverse':leaf_reverse})
        child=copy.deepcopy(root);child['id']='child'
        for track in child['tracks']:track['id']='child_'+track['id']
        child_leaf=child['tracks'][0]['clips'][0];child_leaf['id']='leaf'
        source_out=source_in+90000
        duration=int(Fraction(source_out-source_in)/speed)
        if ramp:
            with localcontext() as ctx:
                ctx.prec=60
                integral=Decimal(3).ln()
                duration=int((integral*90000).to_integral_value())
        root['tracks'][0]['clips']=[{'id':'parent','sequence_id':'child',
            'timeline_start_tick':start,'duration_tick':duration,
            'source_in_tick':source_in,'source_out_tick':source_out,
            'speed':float(speed),'reverse':parent_reverse}]
        if curve or ramp:
            root['tracks'][0]['clips'][0]['speed_curve']={'keyframes':[
                {'at_tick':0,'speed':.5 if ramp else float(speed)},
                {'at_tick':90000,'speed':1.5 if ramp else float(speed)}]}
        p['sequences'].append(child)
        if deep:
            middle=copy.deepcopy(root);middle['id']='middle'
            for track in middle['tracks']:
                track['id']='middle_'+track['id']
                for clip in track['clips']:clip['id']='middle_'+clip['id']
            with localcontext() as ctx:
                ctx.prec=60
                outer_duration=int((Decimal('2.4')*(Decimal(5)/3).ln()*90000).to_integral_value())
            root['tracks'][0]['clips']=[{'id':'outer','sequence_id':'middle',
                'timeline_start_tick':2970,'duration_tick':outer_duration,
                'source_in_tick':7200,'source_out_tick':115200,'reverse':outer_reverse,
                'speed_curve':{'keyframes':[{'at_tick':0,'speed':.75},
                    {'at_tick':108000,'speed':1.25}]}}]
            p['sequences'].append(middle)
        save_project(self.root,p)
        actual,metadata,_=self.render(p,root)
        expected=[];identities=[];rate=Fraction(30000,1001)
        for frame in range(len(actual)):
            now=Fraction(frame)/rate;selected=-1
            outer_visible=True
            if deep:
                outer_visible=Fraction(2970,90000)<=now<Fraction(2970+outer_duration,90000)
                if outer_visible:
                    with localcontext() as ctx:
                        ctx.prec=60
                        ratio=(now-Fraction(2970,90000))/Fraction(outer_duration,90000)
                        progress=Decimal(ratio.numerator)/Decimal(ratio.denominator)
                        if outer_reverse:progress=1-progress
                        distance=Decimal('1.8')*(((Decimal(5)/3).ln()*progress).exp()-1)
                    now=Fraction(7200,90000)+Fraction(distance)
            if outer_visible and Fraction(start,90000)<=now<Fraction(start+duration,90000):
                elapsed=(now-Fraction(start,90000))*speed
                if ramp:
                    with localcontext() as ctx:
                        ctx.prec=60
                        ratio=(now-Fraction(start,90000))/Fraction(duration,90000)
                        progress=Decimal(ratio.numerator)/Decimal(ratio.denominator)
                        if parent_reverse:progress=1-progress
                        local=Decimal('.5')*((Decimal(3).ln()*progress).exp()-1)
                        elapsed=Fraction(local)
                child_time=Fraction(source_out,90000)-elapsed if parent_reverse else Fraction(source_in,90000)+elapsed
                if ramp and parent_reverse:child_time=Fraction(source_in,90000)+elapsed
                source_time=Fraction(117000,90000)-child_time if leaf_reverse else child_time
                backwards=leaf_reverse^parent_reverse^(deep and outer_reverse)
                selected=(bisect_left(times,source_time) if backwards else bisect_right(times,source_time))-1
                selected=max(0,selected)
                native_end=times[-1]+Fraction(1,25)
                if (source_time>native_end if backwards else source_time>=native_end):selected=-1
            identities.append(selected)
            color=colors[selected] if selected>=0 else (0,0,0,255)
            expected.append(bytes(color)*(helpers.W*helpers.H))
        actual_ids=[colors.index(tuple(frame[:4])) if tuple(frame[:4]) in colors else -1 for frame in actual]
        wrong=[i for i,(got,wanted) in enumerate(zip(actual,expected)) if got!=wanted]
        self.assertEqual(wrong,[],f'actual identities={actual_ids}; independent native identities={identities}')

    def test_nested_forward_retains_original_VFR_hold_boundaries(self):self.check()

    def test_parent_reverse_retains_original_VFR_hold_boundaries(self):self.check(parent_reverse=True)

    def test_leaf_reverse_retains_original_VFR_hold_boundaries(self):self.check(leaf_reverse=True)

    def test_double_reverse_retains_original_VFR_hold_boundaries(self):self.check(leaf_reverse=True,parent_reverse=True)

    def test_nested_CFR_control_matches_native_intervals(self):self.check(vfr=False)

    def test_short_VFR_hold_is_visible_at_exact_parent_inpoint(self):
        self.check(start=0,source_in=17100,speed=Fraction(1))

    def test_direct_VFR_short_hold_control_keeps_covering_native_frame(self):
        points=[0,33,101,188,195,441,499,800,1002,1221,1600,1800]
        source,colors,_=self.source(count=len(points),vfr=points)
        p,s,_=self.project(source,start=0,source_in=17100,source_out=107100)
        actual,_,_=self.render(p,s)
        self.assertEqual(actual[0],bytes(colors[3])*(helpers.W*helpers.H))

    def test_parent_curve_preserves_short_native_VFR_hold(self):
        self.check(start=0,source_in=17100,speed=Fraction(1),curve=True)


    def test_parent_constant_curve_reverse_preserves_native_intervals(self):
        self.check(parent_reverse=True,curve=True)

    def test_parent_constant_curve_with_leaf_reverse_preserves_native_intervals(self):
        self.check(leaf_reverse=True,curve=True)

    def test_parent_constant_curve_double_reverse_preserves_native_intervals(self):
        self.check(leaf_reverse=True,parent_reverse=True,curve=True)

    def test_parent_nonlinear_curve_preserves_native_VFR_intervals(self):
        self.check(start=0,source_in=17100,ramp=True)

    def test_parent_nonlinear_curve_reverse_preserves_native_VFR_intervals(self):
        self.check(parent_reverse=True,ramp=True)

    def test_parent_nonlinear_curve_leaf_reverse_preserves_native_VFR_intervals(self):
        self.check(leaf_reverse=True,ramp=True)

    def test_parent_nonlinear_curve_double_reverse_preserves_native_VFR_intervals(self):
        self.check(leaf_reverse=True,parent_reverse=True,ramp=True)

    def test_parent_nonlinear_curve_CFR_control(self):
        self.check(vfr=False,ramp=True)


    def test_nested_forward_curve_nonzero_demux_origin(self):
        self.check(curve=True,offset='5.117123')

    def test_nested_parent_reverse_curve_nonzero_demux_origin(self):
        self.check(parent_reverse=True,curve=True,offset='5.117123')

    def test_nested_leaf_reverse_curve_nonzero_demux_origin(self):
        self.check(leaf_reverse=True,curve=True,offset='5.117123')

    def test_nested_double_reverse_curve_nonzero_demux_origin(self):
        self.check(leaf_reverse=True,parent_reverse=True,curve=True,offset='5.117123')

    def test_nested_forward_curve_short_video_keeps_real_EOF(self):
        self.check(curve=True,short_source=True)

    def test_nested_parent_reverse_curve_short_video_keeps_real_EOF(self):
        self.check(parent_reverse=True,curve=True,short_source=True)

    def test_nested_leaf_reverse_curve_short_video_keeps_real_EOF(self):
        self.check(leaf_reverse=True,curve=True,short_source=True)

    def test_nested_double_reverse_curve_short_video_keeps_real_EOF(self):
        self.check(leaf_reverse=True,parent_reverse=True,curve=True,short_source=True)

    def test_nested_nonlinear_forward_curve_short_video_keeps_real_EOF(self):
        self.check(ramp=True,short_source=True)

    def test_nested_nonlinear_reverse_curve_short_video_keeps_real_EOF(self):
        self.check(parent_reverse=True,ramp=True,short_source=True)


    def test_two_nonlinear_ancestors_preserve_native_VFR_intervals(self):
        self.check(ramp=True,deep=True)

    def test_two_nonlinear_ancestors_outer_reverse_preserves_native_VFR_intervals(self):
        self.check(ramp=True,deep=True,outer_reverse=True)

    def test_two_nonlinear_ancestors_both_reverse_preserve_native_VFR_intervals(self):
        self.check(ramp=True,parent_reverse=True,deep=True,outer_reverse=True)

    def test_two_nonlinear_ancestors_leaf_reverse_preserves_native_VFR_intervals(self):
        self.check(ramp=True,leaf_reverse=True,deep=True)

    def test_two_nonlinear_ancestors_triple_reverse_preserves_native_VFR_intervals(self):
        self.check(ramp=True,leaf_reverse=True,parent_reverse=True,deep=True,outer_reverse=True)

    def test_two_nonlinear_ancestors_CFR_control(self):
        self.check(ramp=True,vfr=False,deep=True)


if __name__=='__main__':unittest.main()
