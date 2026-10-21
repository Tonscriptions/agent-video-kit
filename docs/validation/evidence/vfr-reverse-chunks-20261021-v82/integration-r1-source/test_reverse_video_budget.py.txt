"""Native decoded intervals must reserve graph-wide memory before execution."""
import copy
from pathlib import Path
import unittest
from unittest.mock import patch
from ai_ad_editor.errors import AppError
from ai_ad_editor.render import build_filter_graph
from ai_ad_editor import reverse_video_clock as clock
import test_cfr_boundaries as helpers


class ReverseVideoBudgetTests(unittest.TestCase):
    setUp = helpers.CFRBoundaryTests.setUp
    run_native = helpers.CFRBoundaryTests.run_native
    source = helpers.CFRBoundaryTests.source
    project = helpers.CFRBoundaryTests.project

    def test_actual_native_frame_selection_reports_conservative_buffer_scope(self):
        path, _, _ = self.source()
        p, seq, _ = self.project(path, patch={'reverse': True})
        _, _, metadata, _ = build_filter_graph(self.root, p, seq)
        value = next(row['video_frame_clock']['reverse_frame_intervals']
                     for row in metadata if 'video_frame_clock' in row)
        # The independent source is 25 Hz, 32x18, requested [0,1).
        self.assertEqual(value['selected_frame_count'], 25)
        self.assertEqual(value['estimated_decoded_frame_buffer_bytes'], 25*32*18*16)
        self.assertEqual(value['shared_buffer_bytes_after'], 25*32*18*16)
        self.assertIn('not-process-rss', value['buffer_budget_scope'])

    def test_native_single_buffer_over_budget_plans_read_only_lossless_chunks(self):
        path, _, _ = self.source()
        p, seq, _ = self.project(path, patch={'reverse': True})
        with patch.object(clock, 'MAX_SELECTED_BUFFER_BYTES', 25*32*18*16-1):
            _,_,metadata,_=build_filter_graph(self.root, p, seq)
        job=next(row['reverse_cache'] for row in metadata if 'reverse_cache' in row)
        self.assertEqual([part['frames'] for part in job['recipe']['ranges']],[24,1])
        self.assertLessEqual(job['recipe']['estimated_chunk_frame_bytes'],25*32*18*16-1)
        self.assertFalse(Path(job['output']).exists())
        self.assertFalse((self.root/'cache/reverse-video').exists())

    def test_two_time_disjoint_native_buffers_share_one_graph_budget(self):
        path, _, _ = self.source()
        p, seq, clip = self.project(path, start=0,duration=45000,source_out=45000,patch={'reverse':True})
        other = copy.deepcopy(clip)
        other.update(id='second', timeline_start_tick=60000)
        seq['tracks'][0]['clips'].append(other)
        # The first source uses the shared graph budget. The second is cached,
        # even though the authored instances do not overlap in time.
        with patch.object(clock, 'MAX_SELECTED_BUFFER_BYTES', 13*32*18*16):
            _,_,metadata,_=build_filter_graph(self.root,p,seq)
        values=[row for row in metadata if 'video_frame_clock' in row]
        self.assertNotIn('reverse_cache',values[0])
        self.assertEqual(values[0]['video_frame_clock']['reverse_frame_intervals']['shared_buffer_bytes_after'],13*32*18*16)
        self.assertEqual(values[1]['reverse_cache']['recipe']['frames'],13)
        self.assertFalse((self.root/'cache/reverse-video').exists())

    def test_cancelled_native_index_does_not_spawn_probe(self):
        marker=self.work/'cancel';marker.write_text('cancel',encoding='utf8')
        with patch.object(clock.subprocess,'Popen',side_effect=AssertionError('must not spawn')):
            with self.assertRaises(AppError) as caught:
                clock.probe_frames(Path('unused.nut'),cancel_file=marker)
        self.assertEqual(caught.exception.code,'CANCELLED')


if __name__=='__main__':unittest.main()
