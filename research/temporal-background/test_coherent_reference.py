"""Independent donor-admission, reconstruction and label-seam checks."""
from unittest import TestCase
from unittest.mock import patch

import numpy as np

import coherent_reference as coherent


class CoherentReferenceTests(TestCase):
    def fields(self):
        bank = np.empty((2, 20, 24, 3), np.float32)
        bank[0] = 100
        bank[1] = 120
        y, x = np.indices((20, 24))
        unary = np.stack([.01 * ((x + y) % 2), .01 * (1 - (x + y) % 2)]).astype(np.float32)
        return bank, unary, np.ones(unary.shape, bool), np.ones((20, 24), bool)

    def test_spatial_cost_removes_checkerboard_donor_seams(self):
        bank, unary, allowed, eligible = self.fields()
        original = np.argmin(unary, axis=0)
        labels, _ = coherent.refine_labels(bank, unary, allowed, eligible)
        edges = lambda a: int((a[1:] != a[:-1]).sum() + (a[:, 1:] != a[:, :-1]).sum())
        self.assertGreater(edges(original), 800)
        self.assertLess(edges(labels), 40)

    def test_temporal_cost_stabilizes_labels_but_cannot_supply_new_rgb(self):
        bank, unary, allowed, eligible = self.fields()
        labels, _ = coherent.refine_labels(bank, unary, allowed, eligible,
            prior=np.full((20, 24, 3), 103., np.float32), prior_valid=eligible)
        np.testing.assert_array_equal(labels, 0)
        self.assertTrue(np.all(coherent._gather(bank, labels) == 100))

    def test_forbidden_candidate_cannot_be_resurrected_by_either_penalty(self):
        bank, unary, allowed, eligible = self.fields()
        allowed[0] = False
        unary[0] = -100
        labels, _ = coherent.refine_labels(bank, unary, allowed, eligible,
            prior=np.full((20, 24, 3), 100., np.float32), prior_valid=eligible)
        np.testing.assert_array_equal(labels, 1)

    def test_strong_observed_context_wins_over_temporal_cost(self):
        bank, unary, allowed, eligible = self.fields()
        unary[0] = 0
        unary[1] = 5
        labels, _ = coherent.refine_labels(bank, unary, allowed, eligible,
            prior=np.full((20, 24, 3), 120., np.float32), prior_valid=eligible)
        np.testing.assert_array_equal(labels, 0)

    def test_prior_needs_actual_contribution_and_respects_scene_edge(self):
        rgb = np.full((3, 32, 40, 3), 100., np.float32)
        blocked = np.zeros((3, 32, 40), bool)
        output = np.full((3, 32, 40, 4), 70, np.uint8)
        used = np.zeros(blocked.shape, bool)
        base = coherent._grid(32, 40)
        zero = np.zeros((32, 40, 2), np.float32)
        quality = np.ones((32, 40), bool)
        models = {'one': ({(1, 0): zero}, {(1, 0): quality})}
        _, valid = coherent.temporal_prior(1, rgb, blocked, output, used, models, base)
        self.assertFalse(valid.any())
        used[0, 8:24, 8:28] = True
        prior, valid = coherent.temporal_prior(1, rgb, blocked, output, used, models, base)
        self.assertTrue(valid[12:20, 12:24].all())
        self.assertTrue(np.all(prior[valid] == 70))
        _, valid = coherent.temporal_prior(2, rgb, blocked, output, used, models, base)
        self.assertFalse(valid.any())

    def fixture(self):
        y, x = np.indices((48, 64))
        truth = np.empty((6, 48, 64, 4), np.uint8)
        truth[:, :, :, 0] = (x * 3 + y) % 120 + 60
        truth[:, :, :, 1] = (x + y * 2) % 100 + 70
        truth[:, :, :, 2] = (x * 2 + y * 3) % 80 + 80
        truth[:, :, :, 3] = 255
        selected = np.zeros(truth.shape[:3], bool)
        for i in range(6):
            selected[i, 16:28, 8 + 7*i:20 + 7*i] = True
        source = truth.copy()
        source[selected, :3] = [255, 0, 250]
        fallback = source.copy()
        fallback[selected, :3] = 10
        zero = np.zeros((48, 64, 2), np.float32)
        quality = np.ones((48, 64), bool)
        edges = {(a, b): zero for a in range(6) for b in (a - 1, a + 1) if 0 <= b < 6}
        models = {'one': (edges, {key: quality for key in edges})}
        return truth, source, selected, fallback, models

    def test_observed_texture_recovers_exact_interior_and_preserves_rgba(self):
        truth, source, selected, fallback, models = self.fixture()
        output, used, _ = coherent.propagate(source, selected, selected, fallback, models, min_donors=2)
        self.assertGreater(int(used.sum()), 400)
        np.testing.assert_array_equal(output[~selected], source[~selected])
        np.testing.assert_array_equal(output[:, :, :, 3], source[:, :, :, 3])
        np.testing.assert_array_equal(output[2, 20:24, 26:30], truth[2, 20:24, 26:30])

    def test_two_models_do_not_manufacture_distinct_observations(self):
        truth, source, selected, fallback, models = self.fixture()
        source = source[:2]
        selected = selected[:2]
        fallback = fallback[:2]
        edges = {(0, 1): np.zeros((48, 64, 2), np.float32), (1, 0): np.zeros((48, 64, 2), np.float32)}
        qualities = {key: np.ones((48, 64), bool) for key in edges}
        output, used, _ = coherent.propagate(source, selected, selected, fallback,
            {'a': (edges, qualities), 'b': (edges, qualities)}, min_donors=2)
        self.assertFalse(used.any())
        np.testing.assert_array_equal(output, fallback)

    def test_hidden_rgb_cannot_enter_reconstructed_output(self):
        _, source, selected, fallback, models = self.fixture()
        first, used, _ = coherent.propagate(source, selected, selected, fallback, models, min_donors=2)
        source[selected, :3] = [2, 250, 7]
        second, used2, _ = coherent.propagate(source, selected, selected, fallback, models, min_donors=2)
        np.testing.assert_array_equal(first, second)
        np.testing.assert_array_equal(used, used2)

    def test_a_single_forbidden_bilinear_corner_rejects_the_reference(self):
        source = np.full((3, 36, 40, 4), 60, np.uint8)
        source[:, :, :, 3] = 255
        selected = np.zeros(source.shape[:3], bool)
        selected[0, 8:28, 8:28] = True
        forbidden = selected.copy()
        forbidden[1:, 16, 16] = True
        source[forbidden, :3] = [255, 0, 255]
        fallback = source.copy()
        fallback[selected, :3] = 50
        positive = np.full((36, 40, 2), 1 / 32, np.float32)
        flows = {(0, 1): positive, (1, 2): positive,
                 (1, 0): -positive, (2, 1): -positive}
        models = {'one': (flows, {key: np.ones((36, 40), bool) for key in flows})}
        output, used, _ = coherent.propagate(source, forbidden, selected, fallback, models, min_donors=2)
        np.testing.assert_array_equal(output[0, 15, 15, :3], [50, 50, 50])
        self.assertFalse(used[0, 15, 15])
        np.testing.assert_array_equal(output[0, 12, 12, :3], [60, 60, 60])

    def test_array_budget_rejected_before_any_native_estimation(self):
        _, source, selected, fallback, _ = self.fixture()
        with patch.object(coherent, 'estimate_camera') as camera, patch.object(coherent, 'estimate') as flow:
            with self.assertRaisesRegex(ValueError, 'BUDGET'):
                coherent.run(source, selected, selected, fallback, budget=1000)
            camera.assert_not_called()
            flow.assert_not_called()

    def test_cancel_reaches_label_sweeps(self):
        bank, unary, allowed, eligible = self.fields()
        def stop(*_):
            raise RuntimeError('cancelled-after-donors')
        with self.assertRaisesRegex(RuntimeError, 'cancelled-after-donors'):
            coherent.refine_labels(bank, unary, allowed, eligible, checkpoint=stop)

    def test_invalid_candidates_and_prior_are_rejected(self):
        bank, unary, allowed, eligible = self.fields()
        bank[0, 1, 1] = np.nan
        with self.assertRaisesRegex(ValueError, 'LABEL_CONTRACT'):
            coherent.refine_labels(bank, unary, allowed, eligible)
        bank[0, 1, 1] = 100
        with self.assertRaisesRegex(ValueError, 'PRIOR_CONTRACT'):
            coherent.refine_labels(bank, unary, allowed, eligible, prior=bank[0])
        allowed[:, 1, 1] = False
        with self.assertRaisesRegex(ValueError, 'WITHOUT_DONOR'):
            coherent.refine_labels(bank, unary, allowed, eligible)

    def test_repeatability_and_zero_cost_equal_color_control(self):
        bank, unary, allowed, eligible = self.fields()
        bank[:] = 90
        first, _ = coherent.refine_labels(bank, unary, allowed, eligible)
        second, _ = coherent.refine_labels(bank, unary, allowed, eligible)
        np.testing.assert_array_equal(first, np.argmin(unary, axis=0))
        np.testing.assert_array_equal(first, second)

    def test_visible_crossvalidation_rejects_regression_and_insufficient_support(self):
        bank, _, _, eligible = self.fields()
        labels = np.zeros(eligible.shape, np.int64)
        source = np.full((20, 24, 3), 100., np.float32)
        gate, _ = coherent.observed_gate(source, eligible, bank, labels, labels+1, eligible)
        self.assertFalse(gate.any())
        source[:] = 120
        known = np.zeros_like(eligible)
        known[8, 8] = True
        gate, _ = coherent.observed_gate(source, known, bank, labels, labels+1, eligible)
        self.assertFalse(gate.any())

    def test_visible_gate_accepts_true_visible_gain_without_reading_hidden_rgb(self):
        bank, _, _, eligible = self.fields()
        labels = np.zeros(eligible.shape, np.int64)
        source = np.full((20, 24, 3), 120., np.float32)
        known = eligible.copy()
        known[6:14, 6:18] = False
        first, _ = coherent.observed_gate(source, known, bank, labels, labels+1, eligible)
        self.assertTrue(first[8:12, 8:16].all())
        source[~known] = [255, 1, 173]
        second, _ = coherent.observed_gate(source, known, bank, labels, labels+1, eligible)
        np.testing.assert_array_equal(first, second)

    def test_active_rectangle_is_exactly_equivalent_to_full_raster_refinement(self):
        bank, unary, allowed, eligible = self.fields()
        eligible[:] = False
        eligible[3:17, 6:20] = True
        prior = np.full((20, 24, 3), 104., np.float32)
        full, _ = coherent.refine_labels(bank, unary, allowed, eligible, prior=prior, prior_valid=eligible)
        crop, _ = coherent.refine_region(bank, unary, allowed, eligible, prior=prior, prior_valid=eligible)
        np.testing.assert_array_equal(crop, full)

    def test_temporal_state_contains_raw_observed_color_and_no_feathered_fallback(self):
        truth, source, selected, fallback, models = self.fixture()
        with patch.object(coherent, 'temporal_prior', wraps=coherent.temporal_prior) as prior:
            output, used, _ = coherent.propagate(source, selected, selected, fallback, models, min_donors=2)
        history = prior.call_args_list[1].args[3]
        self.assertTrue(used[0, 16, 8])
        np.testing.assert_array_equal(history[0, 16, 8], truth[0, 16, 8, :3])
        self.assertFalse(np.array_equal(output[0, 16, 8, :3], truth[0, 16, 8, :3]))

    def test_validation_of_a_better_surface_cannot_enable_a_worse_motion_group(self):
        bank = np.empty((2, 32, 40, 3), np.float32)
        bank[0] = 100
        bank[1] = 120
        source = np.full((32, 40, 3), 100., np.float32)
        source[16:] = 120
        groups = np.zeros((32, 40), np.int8)
        groups[16:] = 1
        known = np.ones(groups.shape, bool)
        labels = np.zeros(groups.shape, np.int64)
        gate, _ = coherent.observed_gate(source, known, bank, labels, labels+1, known, groups=groups)
        self.assertFalse(gate[:16].any())
        self.assertTrue(gate[16:].all())

    def test_motion_groups_fit_visible_correspondences_and_abstain_on_hidden_outliers(self):
        height, width = 40, 48
        known = np.ones((height, width), bool)
        known[10:30, 16:28] = False
        zero = np.zeros((height, width, 2), np.float32)
        dense = zero.copy()
        dense[20:, :, 0] = 3
        quality = np.ones((height, width), bool)
        models = {'camera': ({(0, 1): zero}, {(0, 1): quality}),
                  'dense': ({(0, 1): dense}, {(0, 1): quality})}
        groups, first = coherent.motion_groups(0, known, models)
        self.assertEqual(first['status'], 'two-residual-motion-groups')
        self.assertEqual(len(np.unique(groups[groups >= 0])), 2)
        self.assertNotEqual(groups[4, 4], groups[36, 4])
        dense[~known] = 1000
        revised, second = coherent.motion_groups(0, known, models)
        np.testing.assert_array_equal(first['centers'], second['centers'])
        self.assertTrue(np.all(revised[~known] == -1))
