"""Independent native interval oracle for ordinary flattened nested video."""
from bisect import bisect_left,bisect_right
import copy
from fractions import Fraction
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
              start=9900,source_in=10170,curve=False):
        points=[0,33,101,188,195,441,499,800,1002,1221,1600,1800] if vfr else None
        source,colors,times=self.source(count=len(points) if points else 55,vfr=points)
        p,root,leaf=self.project(source,start=0,duration=117000,source_out=117000,
                                 patch={'reverse':leaf_reverse})
        child=copy.deepcopy(root);child['id']='child'
        for track in child['tracks']:track['id']='child_'+track['id']
        child_leaf=child['tracks'][0]['clips'][0];child_leaf['id']='leaf'
        source_out=source_in+90000
        duration=int(Fraction(source_out-source_in)/speed)
        root['tracks'][0]['clips']=[{'id':'parent','sequence_id':'child',
            'timeline_start_tick':start,'duration_tick':duration,
            'source_in_tick':source_in,'source_out_tick':source_out,
            'speed':float(speed),'reverse':parent_reverse}]
        if curve:
            root['tracks'][0]['clips'][0]['speed_curve']={'keyframes':[
                {'at_tick':0,'speed':float(speed)},{'at_tick':90000,'speed':float(speed)}]}
        p['sequences'].append(child);save_project(self.root,p)
        actual,metadata,_=self.render(p,root)
        expected=[];identities=[];rate=Fraction(30000,1001)
        for frame in range(len(actual)):
            now=Fraction(frame)/rate;selected=-1
            if Fraction(start,90000)<=now<Fraction(start+duration,90000):
                elapsed=(now-Fraction(start,90000))*speed
                child_time=Fraction(source_out,90000)-elapsed if parent_reverse else Fraction(source_in,90000)+elapsed
                source_time=Fraction(117000,90000)-child_time if leaf_reverse else child_time
                backwards=leaf_reverse!=parent_reverse
                selected=(bisect_left(times,source_time) if backwards else bisect_right(times,source_time))-1
                selected=max(0,selected)
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


if __name__=='__main__':unittest.main()
