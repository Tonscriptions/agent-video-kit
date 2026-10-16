"""Independent truth, visibility and model-selection checks for repair research."""
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from camera_motion import fit_similarity
from reference_core import array_bound, choose_reference, propagate_references, run


class ReferenceResearchTests(unittest.TestCase):
    def setUp(self):
        cv2.setNumThreads(1)
        cv2.setRNGSeed(0)

    def fixture(self, frames=6):
        rng = np.random.default_rng(238)
        texture = cv2.GaussianBlur(rng.integers(30, 220, (96, 160, 3), dtype=np.uint8), (5, 5), 0)
        truth = np.repeat(np.concatenate([texture, np.full((96, 160, 1), 255, np.uint8)], axis=2)[None], frames, axis=0)
        source = truth.copy()
        selected = np.zeros(source.shape[:3], bool)
        selected[0, 28:60, 54:86] = True
        source[selected, :3] = [250, 0, 173]
        fallback = source.copy()
        fallback[selected, :3] = 110
        flows = {(a, b): np.zeros((96, 160, 2), np.float32)
                 for a in range(frames) for b in (a - 1, a + 1) if 0 <= b < frames}
        quality = {key: np.ones((96, 160), bool) for key in flows}
        models = {'camera': (flows, quality), 'dense': (flows, quality)}
        return truth, source, selected, fallback, models

    def test_similarity_recovers_independent_transform_with_outliers(self):
        rng = np.random.default_rng(93)
        points = rng.uniform([15, 15], [300, 180], (120, 2)).astype(np.float32)
        angle = np.radians(2.)
        expected = np.array([[np.cos(angle), -np.sin(angle), 3.],
                             [np.sin(angle), np.cos(angle), -2.], [0., 0., 1.]])
        second = points @ expected[:2, :2].T + expected[:2, 2]
        second[:25] = rng.uniform([0, 0], [320, 200], (25, 2))
        matrix, report = fit_similarity(points, second.astype(np.float32), 200, 320)
        np.testing.assert_allclose(matrix, expected, atol=2e-4)
        self.assertEqual(report['inliers'], 95)

    def test_degenerate_or_out_of_profile_geometry_abstains(self):
        x = np.linspace(5, 150, 30, dtype=np.float32)
        line = np.stack([x, x * 0 + 45], axis=1)
        self.assertIsNone(fit_similarity(line, line + 2, 96, 160)[0])
        points = np.random.default_rng(5).uniform([5, 5], [150, 90], (50, 2)).astype(np.float32)
        self.assertIsNone(fit_similarity(points, points + 90, 96, 160)[0])
        with self.assertRaisesRegex(ValueError, 'POINT_PAIRS'):
            fit_similarity(points, points[:, :1], 96, 160)

    def test_exact_observed_texture_is_recovered_without_changing_other_pixels(self):
        truth, source, selected, fallback, models = self.fixture()
        output, used, _ = propagate_references(source, selected, selected, fallback, models)
        self.assertGreater(int(used.sum()), 900)
        np.testing.assert_array_equal(output[0, 33:55, 59:81], truth[0, 33:55, 59:81])
        np.testing.assert_array_equal(output[~selected], source[~selected])
        np.testing.assert_array_equal(output[:, :, :, 3], source[:, :, :, 3])

    def test_two_models_of_one_frame_are_not_two_independent_donors(self):
        _, source, selected, fallback, models = self.fixture(frames=2)
        output, used, report = propagate_references(source, selected, selected, fallback, models, min_donors=2)
        self.assertFalse(used.any())
        np.testing.assert_array_equal(output, fallback)
        self.assertEqual(report[0]['donor_frames'], [1])

    def test_context_selects_different_models_on_two_independent_surfaces(self):
        rng = np.random.default_rng(19)
        truth = cv2.GaussianBlur(rng.uniform(30, 220, (180, 192, 3)).astype(np.float32), (5, 5), 0)
        selected = np.zeros((180, 192), bool)
        selected[32:55, 75:100] = True
        selected[125:148, 75:100] = True
        camera, dense = truth.copy(), truth.copy()
        camera[100:] = np.roll(truth[100:], 5, axis=1)
        dense[:80] = np.roll(truth[:80], 5, axis=1)
        known = ~selected
        target = truth.copy()
        target[selected] = 0
        best, valid, _, choice, _ = choose_reference(
            target, [('camera', camera, np.ones_like(known)),
                     ('dense', dense, np.ones_like(known))], known)
        self.assertTrue(valid[selected].all())
        self.assertTrue((choice[32:55, 75:100] == 0).all())
        self.assertTrue((choice[125:148, 75:100] == 1).all())
        np.testing.assert_array_equal(best[selected], truth[selected])
        target[selected] = 255
        other = choose_reference(target, [('camera', camera, np.ones_like(known)),
                                          ('dense', dense, np.ones_like(known))], known)
        np.testing.assert_array_equal(other[0][selected], best[selected])

    def test_disjoint_visible_context_cannot_rank_two_supported_models(self):
        rgb = np.full((96, 160, 3), 60, np.float32)
        selected = np.zeros((96, 160), bool)
        selected[30:60, 65:95] = True
        first, second = selected.copy(), selected.copy()
        first[:, :65] = True
        second[:, 95:] = True
        _, valid, _, _, _ = choose_reference(
            rgb, [('camera', rgb, first), ('dense', rgb, second)], ~selected)
        self.assertFalse(valid[selected].any())

    def test_forbidden_bilinear_corner_cannot_supply_a_reference(self):
        _, source, selected, fallback, models = self.fixture()
        source[:, :, :, :3] = 60
        source[2:, :, :, :3] = 50
        selected[:] = False
        selected[0, 12:42, 12:42] = True
        blocked = selected.copy()
        blocked[1, 16, 16] = True
        source[1, 16, 16, :3] = 255
        fallback[:] = source
        fallback[selected, :3] = 110
        for (a, b), flow in models['dense'][0].items():
            flow[:] = (b - a) / 32
        output, _, _ = propagate_references(source, blocked, selected, fallback, models,
                                             min_donors=1, max_spread=64)
        np.testing.assert_array_equal(output[0, 15, 15, :3], [50, 50, 50])

    def test_never_observed_or_nonopaque_references_abstain(self):
        _, source, selected, fallback, models = self.fixture()
        blocked = np.repeat(selected[:1], len(source), axis=0)
        output, used, _ = propagate_references(source, blocked, selected, fallback, models)
        self.assertFalse(used.any())
        np.testing.assert_array_equal(output, fallback)
        source[1:, :, :, 3] = 128
        fallback[1:, :, :, 3] = 128
        output, used, _ = propagate_references(source, selected, selected, fallback, models)
        self.assertFalse(used.any())
        np.testing.assert_array_equal(output[:, :, :, 3], source[:, :, :, 3])

    def test_scene_cut_blocks_clean_references_in_both_motion_models(self):
        _, source, selected, fallback, _ = self.fixture()
        selected[:3, 28:60, 54:86] = True
        source[selected, :3] = [250, 0, 173]
        fallback[:] = source
        fallback[selected, :3] = 110
        output, used, report = run(source, selected, selected, fallback, scene_cuts=(3,))
        self.assertFalse(used[:3].any())
        np.testing.assert_array_equal(output[:3], fallback[:3])
        for field in ['camera_edges', 'dense_edges']:
            self.assertTrue(any(edge['status'] == 'explicit-scene-cut' for edge in report[field]))

    def test_erased_selected_rgb_cannot_change_native_motion_or_output(self):
        truth, source, selected, fallback, _ = self.fixture(frames=4)
        changed = source.copy()
        changed[selected, :3] = [0, 255, 11]
        first = run(source, selected, selected, fallback)
        second = run(changed, selected, selected, fallback)
        self.assertTrue(first[1].any())
        np.testing.assert_array_equal(first[0], second[0])
        np.testing.assert_array_equal(first[1], second[1])
        error = np.mean((first[0][selected, :3].astype(float) - truth[selected, :3]) ** 2)
        baseline = np.mean((fallback[selected, :3].astype(float) - truth[selected, :3]) ** 2)
        self.assertLess(error, baseline / 2)

    def test_budget_and_invalid_options_precede_native_estimation(self):
        _, source, selected, fallback, _ = self.fixture()
        with patch('reference_core.estimate_camera', side_effect=AssertionError('must not execute')):
            with self.assertRaisesRegex(ValueError, 'ARRAY_BUDGET'):
                run(source, selected, selected, fallback, budget=array_bound(6, 96, 160) - 1)
            with self.assertRaisesRegex(ValueError, 'DONOR_OPTIONS'):
                run(source, selected, selected, fallback, min_donors=True)
            with self.assertRaisesRegex(ValueError, 'SCENE_CUT'):
                run(source, selected, selected, fallback, scene_cuts=(False,))

    def test_checkpoint_cancellation_propagates_before_estimation(self):
        _, source, selected, fallback, _ = self.fixture()
        def stop(*_):
            raise RuntimeError('cancelled')
        with patch('reference_core.estimate_camera', side_effect=AssertionError('must not execute')):
            with self.assertRaisesRegex(RuntimeError, 'cancelled'):
                run(source, selected, selected, fallback, checkpoint=stop)


if __name__ == '__main__':
    unittest.main(verbosity=2)
