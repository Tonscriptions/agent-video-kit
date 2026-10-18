from __future__ import annotations

import copy
import unittest

from ai_ad_editor.mask_edit_geometry import checked, edit_frame, geometry_at, work_estimate


def binding(width=8, height=8, frames=5):
    return {'asset_id': 'mask', 'sha256': 'sha256:'+'1'*64, 'channel': 'alpha',
            'width': width, 'height': height, 'frames': frames, 'fps': '8'}


def operation(kind='rectangle', mode='replace', **overrides):
    key = {'frame': 0, 'box': [.25, .25, .75, .75]}
    if kind in {'polygon', 'brush'}:
        key = {'frame': 0, 'points': [[0., 0.], [1., 0.], [0., 1.]] if kind == 'polygon' else [[.5, .5]]}
    if kind == 'brush':
        key['radius_pixels'] = 2
    out = {'id': 'shape', 'type': kind, 'mode': mode, 'start_frame': 0, 'end_frame': 5,
           'interpolation': 'linear', 'keyframes': [key]}
    out.update(overrides)
    return out


def document(*operations, grid=None, cuts=None, samples=1):
    grid = grid or binding()
    return {'version': '1.0.0', 'coordinate_space': 'normalized-output', 'mask': grid,
            'scene_cut_frames': cuts or [], 'samples_per_axis': samples, 'operations': list(operations)}


def ascii_mask(*rows):
    return bytes(255 if p == '#' else 0 for row in rows for p in row)


class MaskEditGeometryTests(unittest.TestCase):
    def render(self, op, *, frame=0, base=None, samples=1, cuts=None, grid=None):
        grid = grid or binding()
        edits = checked(document(op, grid=grid, cuts=cuts, samples=samples), grid)
        return edit_frame(base if base is not None else bytes(grid['width']*grid['height']), edits, frame)

    def test_rectangle_pixel_center_extent_matches_authored_ascii(self):
        actual, info = self.render(operation())
        self.assertEqual(actual, ascii_mask('........', '........', '..####..', '..####..', '..####..', '..####..', '........', '........'))
        self.assertEqual(info['selected_pixels_gt127'], 16)

    def test_ellipse_and_single_point_brush_match_independent_ascii_circle(self):
        expected = ascii_mask('........', '........', '...##...', '..####..', '..####..', '...##...', '........', '........')
        for kind in ('ellipse', 'brush'):
            with self.subTest(kind=kind):
                self.assertEqual(self.render(operation(kind))[0], expected)

    def test_capsule_brush_endcaps_and_canvas_clipping(self):
        op = operation('brush', keyframes=[{'frame': 0, 'points': [[.25, .5], [.75, .5]], 'radius_pixels': 1}])
        expected = ascii_mask('........', '........', '........', '.######.', '.######.', '........', '........', '........')
        self.assertEqual(self.render(op)[0], expected)
        edge = operation('brush', keyframes=[{'frame': 0, 'points': [[0., 0.]], 'radius_pixels': 1}])
        output, _ = self.render(edge)
        self.assertEqual([i for i, v in enumerate(output) if v], [0])

    def test_polygon_even_odd_matches_hand_authored_triangle(self):
        output, _ = self.render(operation('polygon'))
        expected = ascii_mask('#######.', '######..', '#####...', '####....', '###.....', '##......', '#.......', '........')
        self.assertEqual(output, expected)

    def test_boolean_soft_coverage_order_is_not_binary_thresholded(self):
        grid = binding(2, 2)
        op = operation(keyframes=[{'frame': 0, 'box': [0., 0., 1., 1.]}], opacity=.5)
        base = bytes([0, 64, 128, 255])
        for mode, expected in [('add', [128, 128, 128, 255]), ('subtract', [0, 64, 127, 127]),
                               ('intersect', [0, 64, 128, 128]), ('replace', [128]*4)]:
            with self.subTest(mode=mode):
                op['mode'] = mode
                self.assertEqual(list(self.render(op, grid=grid, base=base)[0]), expected)
        add, subtract = operation(mode='add'), operation(mode='subtract', id='erase')
        first = checked(document(add, subtract), binding())
        second = checked(document(subtract, add), binding())
        self.assertEqual(sum(edit_frame(bytes(64), first, 0)[0]), 0)
        self.assertEqual(sum(edit_frame(bytes(64), second, 0)[0]), 16*255)

    def test_inward_feather_and_opacity_do_not_expand_support(self):
        output, _ = self.render(operation(feather_pixels=2, opacity=.5))
        self.assertEqual(output[2*8+2], 32)
        self.assertEqual(output[3*8+3], 96)
        self.assertEqual(output[1*8+2], 0)
        self.assertEqual(sum(v > 0 for v in output), 16)

    def test_fixed_supersampling_has_explicit_edge_quantization(self):
        output2, _ = self.render(operation('polygon'), samples=2)
        output4, _ = self.render(operation('polygon'), samples=4)
        self.assertEqual(output2[7], 64)
        self.assertEqual(output4[7], 96)
        self.assertEqual(output4[0], 255)
        self.assertEqual(output4[-1], 0)

    def test_linear_keyframes_land_on_independent_pixel_columns(self):
        op = operation(keyframes=[{'frame': 0, 'box': [0., .25, .25, .75]}, {'frame': 4, 'box': [.5, .25, .75, .75]}])
        output, _ = self.render(op, frame=2)
        self.assertEqual(output, ascii_mask('........', '........', '..##....', '..##....', '..##....', '..##....', '........', '........'))
        self.assertEqual(geometry_at(op, 4)['box'], [.5, .25, .75, .75])

    def test_operation_range_leaves_other_frames_and_soft_source_exact(self):
        base = bytes(range(64))
        op = operation(start_frame=1, end_frame=3, keyframes=[{'frame': 1, 'box': [.25, .25, .75, .75]}])
        for frame in (0, 3, 4):
            output, report = self.render(op, base=base, frame=frame)
            self.assertEqual(output, base)
            self.assertEqual(report['active_operations'], [])
            self.assertEqual(report['changed_pixels'], 0)

    def test_scene_cut_holds_previous_geometry_and_requires_reset(self):
        op = operation(keyframes=[{'frame': 0, 'box': [0., 0., .25, .25]}, {'frame': 3, 'box': [.75, .75, 1., 1.]}])
        self.assertEqual(geometry_at(op, 2, cuts=[3])['box'], [0., 0., .25, .25])
        self.assertEqual(geometry_at(op, 3, cuts=[3])['box'], [.75, .75, 1., 1.])
        with self.assertRaisesRegex(ValueError, 'RESET_KEYFRAME'):
            checked(document(op, cuts=[2]), binding())

    def test_hold_allows_topology_changes_but_linear_rejects_them(self):
        keys = [{'frame': 0, 'points': [[0., 0.], [1., 0.], [0., 1.]]},
                {'frame': 2, 'points': [[.25, .25], [.75, .25], [.75, .75], [.25, .75]]}]
        op = operation('polygon', interpolation='hold', keyframes=keys)
        self.assertEqual(self.render(op, frame=2)[0], self.render(operation())[0])
        op['interpolation'] = 'linear'
        with self.assertRaisesRegex(ValueError, 'TOPOLOGY'):
            checked(document(op), binding())

    def test_geometry_contract_rejects_stale_bindings_nonfinite_and_bad_ranges(self):
        originals = []
        v = document(operation()); v['mask']['width'] = True; originals.append(v)
        v = document(operation()); v['unexpected'] = 1; originals.append(v)
        v = document(operation()); v['operations'][0]['keyframes'][0]['box'][0] = float('nan'); originals.append(v)
        v = document(operation()); v['operations'][0]['start_frame'] = True; originals.append(v)
        v = document(operation()); v['operations'][0]['end_frame'] = 6; originals.append(v)
        v = document(operation(), operation()); originals.append(v)
        v = document(operation()); v['samples_per_axis'] = True; originals.append(v)
        for value in originals:
            with self.subTest(value=value), self.assertRaises((ValueError, TypeError)):
                checked(value, binding())

    def test_geometry_budget_and_mid_raster_cancellation(self):
        op = operation('polygon', feather_pixels=3)
        edits = checked(document(op, samples=4), binding())
        self.assertGreater(work_estimate(edits), work_estimate(checked(document(operation()), binding())))
        calls = []
        def checkpoint():
            calls.append(True)
            if len(calls) == 2:
                raise RuntimeError('cancel actual raster')
        with self.assertRaisesRegex(RuntimeError, 'cancel actual raster'):
            edit_frame(bytes(64), edits, 0, checkpoint)
        self.assertEqual(len(calls), 2)


if __name__ == '__main__':
    unittest.main()
