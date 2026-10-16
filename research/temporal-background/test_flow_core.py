"""Independent geometry, exclusion and truth checks for the research kernel."""
import unittest
from unittest.mock import patch
import cv2
import numpy as np
from flow_core import array_bound, estimate, propagate, run


class FlowResearchTests(unittest.TestCase):
    def setUp(self):
        cv2.setNumThreads(1)
        cv2.setRNGSeed(0)

    def fixture(self, frames=6, h=64, w=96):
        y, x = np.indices((h, w))
        truth = np.stack([50 + (x % 9) * 15, 40 + (y % 7) * 20, 30 + (x + y) % 11 * 15], axis=2).astype(np.uint8)
        source = np.repeat(np.concatenate([truth, np.full((h, w, 1), 255, np.uint8)], axis=2)[None], frames, axis=0)
        selected = np.zeros(source.shape[:3], bool)
        selected[0, 16:40, 20:48] = True
        fallback = source.copy()
        source[selected, :3] = [251, 0, 175]
        fallback[selected, :3] = 110
        blocked = selected.copy()
        flows = {(i, j): np.zeros((h, w, 2), np.float32) for i in range(frames) for j in (i - 1, i + 1) if 0 <= j < frames}
        confidence = {key: np.ones((h, w), bool) for key in flows}
        return truth, source, blocked, selected, fallback, flows, confidence

    def test_analytic_zero_motion_recovers_observed_texture_interior(self):
        truth, source, blocked, selected, fallback, flows, quality = self.fixture()
        result, used, _ = propagate(source, blocked, selected, fallback, flows, quality)
        self.assertGreater(used.sum(), 600)
        np.testing.assert_array_equal(result[0, 20:36, 24:44, :3], truth[20:36, 24:44])
        np.testing.assert_array_equal(result[~selected], source[~selected])
        np.testing.assert_array_equal(result[:, :, :, 3], source[:, :, :, 3])

    def test_forbidden_bilinear_corner_is_rejected_exactly(self):
        _, source, blocked, selected, fallback, flows, quality = self.fixture()
        source[1, :, :, :3] = 60
        source[2:, :, :, :3] = 50
        fallback[~selected] = source[~selected]
        selected[:] = False
        selected[0, 12:42, 12:42] = True
        blocked[:] = False
        blocked[0] = selected[0]
        blocked[1, 16, 16] = True
        source[1, 16, 16, :3] = 255
        for (i, j), value in flows.items(): value[:] = (j - i) / 32
        result, _, _ = propagate(source, blocked, selected, fallback, flows, quality, min_donors=1, max_spread=64)
        # The forbidden donor corner contributes 1/1024 to a bilinear sample;
        # a 0.999 validity threshold incorrectly admits it as nearest donor.
        np.testing.assert_array_equal(result[0, 15, 15, :3], [50, 50, 50])
        changed = source.copy()
        changed[1, 16, 16, :3] = 0
        other = propagate(changed, blocked, selected, fallback, flows, quality, min_donors=1, max_spread=64)[0]
        np.testing.assert_array_equal(result[selected], other[selected])

    def test_selected_colors_cannot_change_motion_estimation(self):
        _, source, blocked, selected, fallback, _, _ = self.fixture()
        changed = source.copy()
        changed[blocked, :3] = [1, 255, 3]
        first = estimate(source, blocked)
        second = estimate(changed, blocked)
        self.assertEqual(set(first[0]), set(second[0]))
        for key in first[0]:
            np.testing.assert_array_equal(first[0][key], second[0][key])
            np.testing.assert_array_equal(first[1][key], second[1][key])

    def test_unobserved_region_abstains(self):
        _, source, blocked, selected, fallback, flows, quality = self.fixture()
        blocked[:, 16:40, 20:48] = True
        result, used, _ = propagate(source, blocked, selected, fallback, flows, quality)
        self.assertFalse(used.any())
        np.testing.assert_array_equal(result, fallback)

    def test_scene_cut_blocks_the_only_clean_references(self):
        _, source, blocked, selected, fallback, _, _ = self.fixture()
        selected[:3, 16:40, 20:48] = True
        blocked |= selected
        fallback[selected, :3] = 110
        output, used, report = run(source, blocked, selected, fallback, scene_cuts=(3,))
        self.assertFalse(used[:3].any())
        np.testing.assert_array_equal(output[:3], fallback[:3])
        self.assertTrue(any(x['status'] == 'explicit-scene-cut' for x in report['edges']))

    def test_alpha_is_preserved_and_nonopaque_donors_are_excluded(self):
        _, source, blocked, selected, fallback, flows, quality = self.fixture()
        source[1:, :, :, 3] = 128
        fallback[1:, :, :, 3] = 128
        output, used, _ = propagate(source, blocked, selected, fallback, flows, quality)
        self.assertFalse(used.any())
        np.testing.assert_array_equal(output[:, :, :, 3], source[:, :, :, 3])

    def test_all_forbidden_has_no_motion_edges(self):
        _, source, blocked, selected, fallback, _, _ = self.fixture()
        blocked[:] = True
        output, used, report = run(source, blocked, selected, fallback)
        self.assertFalse(used.any())
        np.testing.assert_array_equal(output, fallback)
        self.assertTrue(all(x['status'] == 'insufficient-observed-background' for x in report['edges']))

    def test_budget_failure_precedes_native_flow(self):
        _, source, blocked, selected, fallback, _, _ = self.fixture()
        n, h, w = source.shape[:3]
        with patch('flow_core.estimate', side_effect=AssertionError('must not execute')):
            with self.assertRaisesRegex(ValueError, 'ARRAY_BUDGET'):
                run(source, blocked, selected, fallback, budget=array_bound(n, h, w) - 1)

    def test_invalid_shapes_options_and_fallback_rejected(self):
        _, source, blocked, selected, fallback, flows, quality = self.fixture()
        with self.assertRaisesRegex(ValueError, 'MASK_INVALID'): run(source, blocked.astype(np.uint8), selected, fallback)
        broken = fallback.copy(); broken[0, 0, 0, 0] ^= 255
        with self.assertRaisesRegex(ValueError, 'FALLBACK_CHANGED'): run(source, blocked, selected, broken)
        with self.assertRaisesRegex(ValueError, 'SCENE_CUT'): run(source, blocked, selected, fallback, scene_cuts=(False,))
        with self.assertRaisesRegex(ValueError, 'DONOR_OPTIONS'): propagate(source, blocked, selected, fallback, flows, quality, min_donors=True)
        flows[0, 1][0, 0] = np.nan
        with self.assertRaisesRegex(ValueError, 'MAP_CONTRACT'): propagate(source, blocked, selected, fallback, flows, quality)

    def test_checkpoint_failure_stops_work(self):
        _, source, blocked, selected, fallback, _, _ = self.fixture()
        def stop(*_): raise RuntimeError('cancelled')
        with self.assertRaisesRegex(RuntimeError, 'cancelled'): run(source, blocked, selected, fallback, checkpoint=stop)


if __name__ == '__main__':
    unittest.main(verbosity=2)
