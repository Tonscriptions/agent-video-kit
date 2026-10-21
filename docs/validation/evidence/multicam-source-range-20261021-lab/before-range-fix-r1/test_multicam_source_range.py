"""Camera coverage must preserve the independently established event clock."""
from __future__ import annotations
import unittest
from ai_ad_editor.errors import AppError
from ai_ad_editor.multicam import build_switch_segments


def sync(delay,duration):
    return {'reference_asset_id':'reference','sources':[{'asset_id':'reference'},{'asset_id':'camera'}],
        'offsets':[{'asset_id':'reference','relative_delay_seconds':0.,'evidence':{'duration_seconds':3.}},
            {'asset_id':'camera','relative_delay_seconds':delay,'evidence':{'duration_seconds':duration}}]}


class MulticamCoverageTests(unittest.TestCase):
    def plan(self,delay,duration,left,right,**options):
        return build_switch_segments(sync(delay,duration),start_seconds=0.,end_seconds=3.,
            switch_plan=[{'start_seconds':left,'end_seconds':right,'camera_asset_id':'camera'}],**options)

    def test_default_refuses_a_camera_that_begins_after_the_requested_event(self):
        with self.assertRaises(AppError):self.plan(-.4,2.,0.,1.)

    def test_default_refuses_a_camera_that_ends_before_the_requested_event(self):
        with self.assertRaises(AppError):self.plan(.2,1.,.5,1.2)

    def test_fully_covered_source_keeps_the_original_event_mapping(self):
        rows,_=self.plan(.2,3.,.5,1.2)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['source_in_seconds'],.7)
        self.assertEqual(rows[0]['source_out_seconds'],1.4)
        self.assertEqual(rows[0]['speed'],1.)
        self.assertEqual(rows[0]['timeline_start_seconds'],.5)
        self.assertEqual(rows[0]['duration_seconds'],.7)


if __name__=='__main__':unittest.main()
