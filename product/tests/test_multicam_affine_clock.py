"""Clock truth is specified before fitting, independently of the returned model."""
from __future__ import annotations
import copy
import hashlib
import importlib
import json
import unittest

import numpy as np

from ai_ad_editor.errors import AppError
from ai_ad_editor.multicam import build_switch_segments


def features(rate=1.001, offset=.42, seconds=300., *, gain=1., bias=0., bad_window=False):
    rng = np.random.default_rng(873921)
    count = int(seconds * 50)
    # Smooth nonperiodic modulation resembles a sampled energy envelope.
    base = np.convolve(rng.normal(size=count + 80), np.hanning(13), mode='valid')[:count]
    base /= np.std(base)
    source = np.arange(int((seconds * rate + max(0., offset) + 1.) * 50)) / 50
    candidate = np.interp((source - offset) / rate * 50, np.arange(count), base, left=0., right=0.)
    candidate = candidate * gain + bias
    if bad_window:
        mask = (source >= 120.) & (source <= 150.)
        candidate[mask] = rng.normal(size=int(mask.sum())) * 5
    return base.astype(np.float32), candidate.astype(np.float32)


def estimate(reference, candidate, **options):
    module = importlib.import_module('ai_ad_editor.multicam_clock')
    return module.estimate_affine_clock(reference, candidate, max_offset_seconds=2., **options)


def seal(model):
    body = copy.deepcopy(model)
    payload = json.dumps(body, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    body['calibration_sha256'] = 'sha256:' + hashlib.sha256(payload).hexdigest()
    return body


def report(rate=1.01, offset=.2, *, source_start=0., source_end=400., valid=(0., 300.)):
    source_sha = 'sha256:' + hashlib.sha256(b'camera-fixture').hexdigest()
    reference_sha = 'sha256:' + hashlib.sha256(b'reference-fixture').hexdigest()
    clock = seal({
        'protocol': 'multicam-affine-clock-v1', 'kind': 'affine', 'status': 'calibrated',
        'source_asset_id': 'camera', 'reference_asset_id': 'reference',
        'source_sha256': source_sha, 'reference_sha256': reference_sha,
        'offset_seconds': offset, 'source_per_reference': rate,
        'drift_ppm': (rate - 1.) * 1e6,
        'inverse': {'reference_per_source': 1. / rate, 'offset_seconds': -offset / rate},
        'valid_reference_range': {'start_seconds': valid[0], 'end_seconds': valid[1]}})
    return {'sync_version': '0.5.0', 'reference_asset_id': 'reference',
        'parameters': {'clock_model': 'affine'},
        'sources': [{'asset_id': 'reference'}, {'asset_id': 'camera'}],
        'offsets': [
            {'asset_id': 'reference', 'relative_delay_seconds': 0.,
             'evidence': {'duration_seconds': 300., 'sha256': reference_sha,
                          'video_coverage': {'start_seconds': 0., 'end_seconds': 300.}}},
            {'asset_id': 'camera', 'relative_delay_seconds': offset, 'clock_model': clock,
             'evidence': {'duration_seconds': 400., 'sha256': source_sha,
                          'video_coverage': {'start_seconds': source_start, 'end_seconds': source_end}}}]}


def segments(sync=None, left=100., right=110., **options):
    return build_switch_segments(report() if sync is None else sync,
        start_seconds=0., end_seconds=300.,
        switch_plan=[{'start_seconds': left, 'end_seconds': right, 'camera_asset_id': 'camera'}], **options)


class AffineClockFitTests(unittest.TestCase):
    def fit(self, rate, offset=.42, **options):
        reference, candidate = features(rate, offset, **options)
        model = estimate(reference, candidate)
        self.assertEqual(model['status'], 'calibrated')
        self.assertEqual(model['protocol'], 'multicam-affine-clock-v1')
        self.assertGreaterEqual(sum(row['accepted'] for row in model['anchors']), 5)
        self.assertAlmostEqual(model['source_per_reference'], rate, delta=3e-5)
        self.assertAlmostEqual(model['offset_seconds'], offset, delta=.008)
        for second in (15., 150., 285.):
            predicted = model['offset_seconds'] + model['source_per_reference'] * second
            self.assertAlmostEqual(predicted, offset + rate * second, delta=.012)
        return model

    def test_positive_thousand_ppm_preserves_start_middle_and_end_events(self):
        self.fit(1.001)

    def test_negative_drift_and_negative_offset_have_correct_direction(self):
        self.fit(.9982, -.34)

    def test_small_hundred_ppm_is_observed_over_ten_minutes(self):
        self.fit(1.0001, .08, seconds=600.)

    def test_zero_drift_does_not_invent_rate_correction(self):
        self.fit(1., .6)

    def test_gain_and_constant_envelope_bias_do_not_change_the_clock(self):
        self.fit(1.001, gain=3.7, bias=.8)

    def test_one_corrupt_interval_is_rejected_without_moving_clean_events(self):
        model = self.fit(1.001, bad_window=True)
        self.assertTrue(any(not row['accepted'] for row in model['anchors']))

    def test_inverse_reconstructs_reference_seconds(self):
        model = self.fit(1.001)
        inverse = model['inverse']
        for second in (0., 60., 299.):
            source = model['offset_seconds'] + model['source_per_reference'] * second
            self.assertAlmostEqual(source * inverse['reference_per_source'] + inverse['offset_seconds'], second, places=8)

    def test_periodic_ambiguous_audio_cannot_be_applied_as_calibration(self):
        values = np.sin(np.arange(15000) * (2 * np.pi / 50)).astype(np.float32)
        with self.assertRaises(AppError):
            estimate(values, values.copy())

    def test_flat_or_too_short_signals_do_not_fall_back_to_offset(self):
        for left, right in ((np.zeros(15000), np.zeros(15000)), (np.arange(300.), np.arange(300.))):
            with self.subTest(size=len(left)), self.assertRaises(AppError):
                estimate(left, right)

    def test_clock_outside_explicit_drift_budget_is_rejected(self):
        left, right = features(1.012)
        with self.assertRaises(AppError):
            estimate(left, right, max_drift_ppm=5000.)

    def test_piecewise_clock_does_not_pass_as_a_single_affine_clock(self):
        left, _ = features()
        reference_time = np.arange(left.size) / 50
        source_time = .4 + reference_time * 1.0002 + np.maximum(0., reference_time - 150.) * .003
        candidate = np.interp(np.arange(15100) / 50, source_time, left, left=0., right=0.)
        with self.assertRaises(AppError):
            estimate(left, candidate)

    def test_invalid_finite_and_window_budgets_are_rejected(self):
        left, right = features()
        for options in ({'max_drift_ppm': float('nan')}, {'max_drift_ppm': True},
                        {'max_drift_ppm': 20001.}, {'window_seconds': 0.},
                        {'window_seconds': float('inf')}, {'anchor_count': 2}, {'anchor_count': 3.5}):
            with self.subTest(options=options), self.assertRaises(AppError):
                estimate(left, right, **options)

    def test_repeated_fit_is_deterministic_and_does_not_mutate_features(self):
        left, right = features()
        before = left.copy(), right.copy()
        self.assertEqual(estimate(left, right), estimate(left, right))
        np.testing.assert_array_equal(left, before[0])
        np.testing.assert_array_equal(right, before[1])


class AffineClockPlanTests(unittest.TestCase):
    def test_positive_rate_changes_both_source_endpoints_and_clip_speed(self):
        rows, _ = segments()
        self.assertEqual((rows[0]['source_in_seconds'], rows[0]['source_out_seconds']), (101.2, 111.3))
        self.assertEqual((rows[0]['duration_seconds'], rows[0]['speed']), (10., 1.01))

    def test_negative_drift_is_not_misreported_as_missing_source(self):
        rows, warnings = segments(report(.99))
        self.assertEqual(rows[0]['speed'], .99)
        self.assertNotIn('MULTICAM_SOURCE_SLOWED', [row['code'] for row in warnings])

    def test_trim_uses_inverse_native_bounds_and_retains_calibrated_rate(self):
        rows, _ = segments(report(source_start=2.22, source_end=9.29), left=0., right=10.,
                           source_shortfall='trim', timeline_start_seconds=5.)
        row = rows[0]
        self.assertEqual((row['timeline_start_seconds'], row['duration_seconds']), (7., 7.))
        self.assertEqual((row['source_in_seconds'], row['source_out_seconds'], row['speed']), (2.22, 9.29, 1.01))

    def test_default_refuses_the_uncovered_calibrated_source_tail(self):
        with self.assertRaises(AppError) as caught:
            segments(report(source_end=110.8))
        self.assertEqual(caught.exception.code, 'MULTICAM_SOURCE_SHORTFALL')

    def test_explicit_stretch_still_warns_that_event_sync_is_changed(self):
        rows, warnings = segments(report(source_end=9.), left=0., right=10., source_shortfall='stretch')
        self.assertEqual(rows[0]['source_out_seconds'], 9.)
        self.assertIn('MULTICAM_SOURCE_CLOCK_CHANGED', [row['code'] for row in warnings])
        self.assertIn('MULTICAM_SOURCE_SLOWED', [row['code'] for row in warnings])

    def test_unobserved_extrapolation_requires_explicit_choice(self):
        with self.assertRaises(AppError) as caught:
            segments(report(valid=(0., 90.)))
        self.assertEqual(caught.exception.code, 'MULTICAM_CLOCK_EXTRAPOLATION')

    def test_explicit_extrapolation_keeps_rate_and_records_warning(self):
        rows, warnings = segments(report(valid=(0., 90.)), allow_clock_extrapolation=True)
        self.assertEqual(rows[0]['speed'], 1.01)
        self.assertIn('MULTICAM_CLOCK_EXTRAPOLATION', [row['code'] for row in warnings])

    def test_modified_clock_coefficient_is_not_silently_accepted(self):
        sync = report()
        sync['offsets'][1]['clock_model']['source_per_reference'] = 1.002
        with self.assertRaises(AppError):
            segments(sync)

    def test_calibration_for_another_source_or_reference_is_rejected(self):
        for key in ('source_asset_id', 'reference_asset_id', 'source_sha256', 'reference_sha256'):
            sync = report()
            clock = sync['offsets'][1]['clock_model']
            clock.pop('calibration_sha256')
            clock[key] = 'unrelated'
            sync['offsets'][1]['clock_model'] = seal(clock)
            with self.subTest(key=key), self.assertRaises(AppError):
                segments(sync)

    def test_invalid_rate_and_inverse_are_rejected_even_with_matching_digest(self):
        for value in (True, 0., -1., float('inf')):
            sync = report()
            clock = sync['offsets'][1]['clock_model']
            clock.pop('calibration_sha256')
            clock['source_per_reference'] = value
            if np.isfinite(value):
                sync['offsets'][1]['clock_model'] = seal(clock)
            with self.subTest(value=value), self.assertRaises(AppError):
                segments(sync)

    def test_planning_keeps_original_report_unchanged(self):
        sync = report()
        before = copy.deepcopy(sync)
        segments(sync)
        self.assertEqual(sync, before)

    def test_legacy_constant_offset_control_still_maps_the_same_source(self):
        sync = report()
        sync['parameters'] = {}
        sync['offsets'][1].pop('clock_model')
        rows, _ = segments(sync)
        self.assertEqual((rows[0]['source_in_seconds'], rows[0]['source_out_seconds'], rows[0]['speed']), (100.2, 110.2, 1.))


class ClockModelBindingTests(unittest.TestCase):
    def mutate(self, callback):
        sync = report()
        model = sync['offsets'][1]['clock_model']
        model.pop('calibration_sha256')
        callback(sync, model)
        sync['offsets'][1]['clock_model'] = seal(model)
        return sync

    def refused(self, sync):
        with self.assertRaises(AppError) as caught:
            segments(sync)
        self.assertEqual(caught.exception.code, 'MULTICAM_CLOCK_INVALID')

    def test_missing_null_or_empty_source_identity_cannot_match_itself(self):
        for value in (None, '', 'absent'):
            def change(sync, model):
                if value == 'absent':
                    model.pop('source_sha256');sync['offsets'][1]['evidence'].pop('sha256')
                else:
                    model['source_sha256'] = value;sync['offsets'][1]['evidence']['sha256'] = value
            with self.subTest(value=value):
                self.refused(self.mutate(change))

    def test_equal_malformed_digest_strings_are_not_source_evidence(self):
        for value in ('camera', 'sha256:short', 'sha512:'+'a'*64):
            def change(sync, model):
                model['source_sha256'] = value;sync['offsets'][1]['evidence']['sha256'] = value
            with self.subTest(value=value):
                self.refused(self.mutate(change))

    def test_missing_reference_digest_cannot_match_an_unbound_reference(self):
        def change(sync, model):
            model.pop('reference_sha256');sync['offsets'][0]['evidence'].pop('sha256')
        self.refused(self.mutate(change))

    def test_declared_drift_must_agree_with_the_actual_rate(self):
        self.refused(self.mutate(lambda sync, model: model.update(drift_ppm=42.)))

    def test_legacy_zero_time_projection_must_agree_with_model_offset(self):
        sync = report();sync['offsets'][1]['relative_delay_seconds'] = .3
        self.refused(sync)

    def test_observed_range_cannot_extend_beyond_the_reference_media(self):
        self.refused(self.mutate(lambda sync, model: model['valid_reference_range'].update(end_seconds=301.)))

    def test_observed_source_range_cannot_exceed_source_media_duration(self):
        sync = report();sync['offsets'][1]['evidence']['duration_seconds'] = 200.
        self.refused(sync)

    def test_inverse_offset_disagreement_remains_a_rejection_control(self):
        self.refused(self.mutate(lambda sync, model: model['inverse'].update(offset_seconds=123.)))


if __name__ == '__main__':
    unittest.main()
