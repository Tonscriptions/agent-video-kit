"""Author-content invariants, real CLI transactions and partner constraints."""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from ai_ad_editor.cli import main
from ai_ad_editor.edit_planner import build_edit_plan
from ai_ad_editor.errors import AppError
from ai_ad_editor.project import create_project, save_project


def clip(cid, a, b, **fields):
    return {'id': cid, 'asset_id': 'media', 'timeline_start_tick': a,
            'duration_tick': b-a, 'source_in_tick': 10, 'source_out_tick': 10+b-a, **fields}


def track(tid, clips, kind='video', order=0, **fields):
    return {'id': tid, 'kind': kind, 'order': order, 'clips': clips, **fields}


def project(tracks=None):
    return {'project': {'id': 'test'}, 'settings': {'timebase': {'ticks_per_second': 10,
            'display_fps': {'num': 10, 'den': 1}}},
            'assets': [{'id': 'media', 'kind': 'video', 'probe': {'duration_seconds': 100}}],
            'sequences': [{'id': 'seq', 'name': 'reorder', 'duration_tick': 100,
                'tracks': tracks or [track('main', [clip('a', 0, 10), clip('b', 10, 20), clip('c', 20, 30), clip('d', 30, 40)])],
                'markers': [{'id': 'marker', 'at_tick': 7}]}]}


def request(ids=('c',), before='a', **fields):
    return {'action': 'reorder', 'clip_ids': list(ids), 'before_clip_id': before, **fields}


def positions(value):
    return {c['id']: (t['id'], c['timeline_start_tick'], c['timeline_start_tick']+c['duration_tick'])
            for s in value['sequences'] for t in s['tracks'] for c in t['clips']}


def invoke(*args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(map(str, args)))
    return code, json.loads(out.getvalue())


class MagneticReorderPlannerTests(unittest.TestCase):
    def plan(self, value, query):
        before = copy.deepcopy(value)
        result = build_edit_plan(value, 'seq', query)
        self.assertEqual(value, before)
        return result

    def rejects(self, value, query, code):
        before = copy.deepcopy(value)
        with self.assertRaises(AppError) as caught:
            build_edit_plan(value, 'seq', query)
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(value, before)

    def test_single_clip_inserts_before_target_without_overwrite(self):
        result, plan = self.plan(project(), request())
        self.assertEqual(plan['after_main_order'], ['c', 'a', 'b', 'd'])
        self.assertEqual(positions(result), {'c': ('main', 0, 10), 'a': ('main', 10, 20),
                                            'b': ('main', 20, 30), 'd': ('main', 30, 40)})
        self.assertEqual(result['sequences'][0]['duration_tick'], 40)
        self.assertEqual(plan['short_tick'], 0)

    def test_noncontiguous_selection_keeps_original_order_and_end_is_explicit(self):
        result, plan = self.plan(project(), request(('d', 'b')))
        self.assertEqual(plan['after_main_order'], ['b', 'd', 'a', 'c'])
        result, plan = self.plan(result, request(('d', 'b'), None))
        self.assertEqual(plan['after_main_order'], ['a', 'c', 'b', 'd'])

    def test_existing_leading_and_internal_gaps_pack_without_media_changes(self):
        value = project([track('main', [clip('a', 3, 13), clip('b', 17, 27), clip('c', 40, 50)])])
        result, plan = self.plan(value, request(('c',), None))
        self.assertEqual(plan['removed_gap_tick'], 20)
        self.assertEqual(positions(result)['b'], ('main', 10, 20))
        for old in value['sequences'][0]['tracks'][0]['clips']:
            new = next(c for c in result['sequences'][0]['tracks'][0]['clips'] if c['id'] == old['id'])
            self.assertEqual({k:v for k,v in old.items() if k != 'timeline_start_tick'},
                             {k:v for k,v in new.items() if k != 'timeline_start_tick'})

    def test_displaced_shots_linked_voice_moves_too(self):
        value = project()
        for c in value['sequences'][0]['tracks'][0]['clips']:
            c['link_id'] = c['id']+'link'
        value['sequences'][0]['tracks'].append(track('voice', [clip('v'+c, i*10, i*10+10, link_id=c+'link')
                                                              for i,c in enumerate('abcd')], 'audio', 1))
        result, _ = self.plan(value, request())
        pos = positions(result)
        for c in 'abcd':
            self.assertEqual(pos['v'+c][1:], pos[c][1:])

    def test_link_expands_main_selection_and_rejects_incompatible_offsets(self):
        value = project()
        value['sequences'][0]['tracks'][0]['clips'][1]['link_id'] = 'block'
        value['sequences'][0]['tracks'][0]['clips'][2]['link_id'] = 'block'
        result, plan = self.plan(value, request(('b',)))
        self.assertEqual(plan['selected_clip_ids'], ['b', 'c'])
        self.assertEqual(plan['after_main_order'], ['b', 'c', 'a', 'd'])
        value['sequences'][0]['tracks'][0]['clips'][2].pop('link_id')
        value['sequences'][0]['tracks'][0]['clips'][3]['link_id'] = 'block'
        self.rejects(value, request(('b',)), 'EDIT_REORDER_LINK_CONFLICT')

    def test_expanded_target_rejects_and_linked_false_is_explicit_opt_out(self):
        value = project()
        for c in value['sequences'][0]['tracks'][0]['clips'][1:3]:
            c['link_id'] = 'block'
        self.rejects(value, request(('b',), 'c'), 'EDIT_REORDER_TARGET_SELECTED')
        result, plan = self.plan(value, request(('b',), 'c', options={'linked': False}))
        self.assertEqual(plan['after_main_order'], ['a', 'b', 'c', 'd'])

    def test_riders_follow_original_host_and_long_bed_stays_anchored(self):
        value = project()
        value['sequences'][0]['tracks'] += [track('titles', [clip('on_c', 22, 27)], 'subtitle', 1),
            track('bed', [clip('music', 0, 40)], 'audio', 2)]
        result, plan = self.plan(value, request(options={'linkage': True}))
        self.assertEqual(positions(result)['on_c'], ('titles', 2, 7))
        self.assertEqual(positions(result)['music'], ('bed', 0, 40))
        self.assertIn('music', plan['anchored_clip_ids'])

    def test_explicit_link_overrides_positional_rider_host(self):
        value = project()
        value['sequences'][0]['tracks'][0]['clips'][2]['link_id'] = 'g'
        value['sequences'][0]['tracks'].append(track('voice', [clip('voice_c', 31, 35, link_id='g')], 'audio', 1))
        result, _ = self.plan(value, request(options={'linkage': True}))
        self.assertEqual(positions(result)['voice_c'], ('voice', 11, 15))

    def test_unlinked_locked_rider_stays_and_locked_link_rejects(self):
        value = project()
        value['sequences'][0]['tracks'].append(track('titles', [clip('on_c', 22, 27)], 'subtitle', 1, locked=True))
        result, _ = self.plan(value, request(options={'linkage': True}))
        self.assertEqual(positions(result)['on_c'], ('titles', 22, 27))
        value['sequences'][0]['tracks'][0]['clips'][2]['link_id'] = 'g'
        value['sequences'][0]['tracks'][1]['clips'][0]['link_id'] = 'g'
        self.rejects(value, request(), 'EDIT_TRACK_LOCKED')

    def test_unmoved_locked_link_member_does_not_block_other_reordering(self):
        value = project()
        value['sequences'][0]['tracks'][0]['clips'][3]['link_id'] = 'g'
        value['sequences'][0]['tracks'].append(track('locked', [clip('held', 30, 40, link_id='g')], 'audio', 1, locked=True))
        result, _ = self.plan(value, request())
        self.assertEqual(positions(result)['held'], ('locked', 30, 40))

    def test_sync_opt_out_and_direct_links_override_opt_out(self):
        value = project()
        value['sequences'][0]['tracks'] += [track('voice', [clip('v', 22, 27)], 'audio', 1),
            track('bed', [clip('music', 0, 40)], 'audio', 2, sync_lock=False)]
        result, _ = self.plan(value, request(options={'sync': True, 'linkage': True}))
        self.assertEqual(positions(result)['v'], ('voice', 2, 7))
        self.assertEqual(positions(result)['music'], ('bed', 0, 40))
        value['sequences'][0]['tracks'][1]['sync_lock'] = False
        value['sequences'][0]['tracks'][1]['clips'][0]['link_id'] = 'g'
        value['sequences'][0]['tracks'][0]['clips'][2]['link_id'] = 'g'
        result, _ = self.plan(value, request(options={'sync': True}))
        self.assertEqual(positions(result)['v'], ('voice', 2, 7))

    def test_sync_crossing_discontinuous_permutation_rejects(self):
        value = project()
        value['sequences'][0]['tracks'].append(track('bed', [clip('music', 0, 40)], 'audio', 1))
        self.rejects(value, request(options={'sync': True}), 'EDIT_REORDER_SYNC_SPAN_UNSUPPORTED')

    def test_sync_crossing_equal_delta_block_is_rigid_and_valid(self):
        value = project()
        value['sequences'][0]['tracks'].append(track('voice', [clip('two_shots', 12, 28)], 'audio', 1))
        result, _ = self.plan(value, request(('b', 'c'), options={'sync': True}))
        self.assertEqual(positions(result)['two_shots'], ('voice', 2, 18))

    def test_gap_host_stays_and_tail_follows_last_shot(self):
        value = project([track('main', [clip('a', 0, 10), clip('b', 20, 30), clip('c', 30, 40)]),
            track('titles', [clip('in_gap', 12, 15), clip('tail', 42, 47)], 'subtitle', 1)])
        result, _ = self.plan(value, request(options={'linkage': True}))
        self.assertEqual(positions(result)['in_gap'], ('titles', 12, 15))
        self.assertEqual(positions(result)['tail'][1:], (12, 17))

    def test_sync_crossing_gap_rejects_without_discarding_content(self):
        value = project([track('main', [clip('a', 0, 10), clip('b', 20, 30), clip('c', 30, 40)]),
            track('voice', [clip('spans_gap', 2, 25)], 'audio', 1)])
        self.rejects(value, request(options={'sync': True}), 'EDIT_REORDER_SYNC_SPAN_UNSUPPORTED')

    def test_negative_link_offset_rejects_atomically(self):
        value = project()
        value['sequences'][0]['tracks'][0]['clips'][2]['link_id'] = 'g'
        value['sequences'][0]['tracks'].append(track('voice', [clip('lead', 15, 25, link_id='g')], 'audio', 1))
        self.rejects(value, request(), 'EDIT_NEGATIVE_TIME')

    def test_collision_uses_compatible_lane_and_preserves_volume(self):
        value = project()
        value['sequences'][0]['tracks'] += [track('voice', [clip('bed', 0, 27), clip('rider', 31, 38)], 'audio', 1, audio={'volume': .25}),
            track('free', [], 'audio', 2, audio={'volume': .25})]
        result, plan = self.plan(value, request(('d',), options={'linkage': True}))
        self.assertEqual(positions(result)['rider'], ('free', 1, 8))
        self.assertEqual(plan['new_track_ids'], [])
        value['sequences'][0]['tracks'].pop()
        result, plan = self.plan(value, request(('d',), options={'linkage': True}))
        self.assertEqual(len(plan['new_tracks']), 1)
        self.assertEqual(plan['new_tracks'][0]['audio'], {'volume': .25})

    def test_effect_and_ducking_bus_collision_are_rejected(self):
        for processing in ({'effects': [{'type': 'compressor'}]}, {'duck_under_voice': True}):
            value = project()
            value['sequences'][0]['tracks'].append(track('voice', [clip('bed', 0, 27), clip('rider', 31, 38)], 'audio', 1, audio=processing))
            self.rejects(value, request(('d',), options={'linkage': True}), 'EDIT_AUDIO_BUS_RELOCATION_UNSUPPORTED')

    def test_side_only_link_group_conflicting_hosts_reject_and_opt_out_stays(self):
        value = project()
        value['sequences'][0]['tracks'].append(track('titles', [clip('rider', 22, 25, link_id='g'),
            clip('tail', 45, 48, link_id='g')], 'subtitle', 1))
        self.rejects(value, request(options={'linkage': True}), 'EDIT_REORDER_LINK_CONFLICT')
        value['sequences'][0]['tracks'][1]['clips'][1].update(timeline_start_tick=12)
        result, _ = self.plan(value, request(options={'linkage': False}))
        self.assertEqual(positions(result)['rider'], ('titles', 22, 25))

    def test_side_only_link_group_moves_gap_member_with_its_rider(self):
        value = project([track('main', [clip('a', 0, 10), clip('b', 20, 30), clip('c', 30, 40)]),
            track('titles', [clip('rider', 2, 5, link_id='g'), clip('in_gap', 12, 15, link_id='g')], 'subtitle', 1)])
        result, _ = self.plan(value, request(options={'linkage': True}))
        self.assertEqual(positions(result)['rider'], ('titles', 12, 15))
        self.assertEqual(positions(result)['in_gap'], ('titles', 22, 25))

    def test_sequence_subtitle_offsets_do_not_drift_after_inverse_reorder(self):
        value = project()
        value['assets'].append({'id': 'srt', 'kind': 'subtitle'})
        value['sequences'][0]['tracks'].append(track('sub', [clip('line', 22, 27, asset_id='srt')], 'subtitle', 1))
        result, plan = self.plan(value, request(options={'linkage': True}))
        c = result['sequences'][0]['tracks'][1]['clips'][0]
        self.assertEqual(c['subtitle']['asset_time_offset_tick'], 20)
        restored, _ = self.plan(result, request(('c',), 'd', options={'linkage': True}))
        self.assertEqual(restored['sequences'][0]['tracks'][1]['clips'][0]['subtitle']['asset_time_offset_tick'], 0)
        self.assertEqual(positions(restored)['line'][1:], (22, 27))

    def test_clip_subtitle_and_presentation_window_keep_author_clock(self):
        value = project()
        value['assets'].append({'id': 'srt', 'kind': 'subtitle'})
        value['sequences'][0]['tracks'].append(track('sub', [clip('line', 22, 27, asset_id='srt',
            subtitle={'asset_time_base':'clip'}, presentation_window={'version':1,'authored_start_tick':20,
                'authored_duration_tick':10,'offset_tick':2})], 'subtitle', 1))
        result, _ = self.plan(value, request(options={'linkage': True}))
        old = value['sequences'][0]['tracks'][1]['clips'][0]
        new = result['sequences'][0]['tracks'][1]['clips'][0]
        self.assertEqual(old['presentation_window'], new['presentation_window'])
        self.assertEqual(old['subtitle'], new['subtitle'])

    def test_complete_author_payload_markers_and_other_sequence_stay(self):
        value = project()
        fields={'reverse': True, 'speed_curve':[{'at_tick':0,'speed':1},{'at_tick':9,'speed':2}],
            'freeze':[{'at_tick':4,'duration_tick':2,'audio_mode':'silence'}],
            'keyframes':[{'property':'transform.opacity','keyframes':[{'at_tick':3,'value':.5,'interpolation':'linear'}]}],
            'presentation_window':{'version':1,'authored_start_tick':20,'authored_duration_tick':20,'offset_tick':2},
            'rights_ref':'original-right'}
        value['sequences'][0]['tracks'][0]['clips'][2].update(fields)
        value['sequences'].append({'id':'child','tracks':[],'duration_tick':1})
        result, _ = self.plan(value, request())
        c=result['sequences'][0]['tracks'][0]['clips'][0]
        for k,v in fields.items(): self.assertEqual(c[k],v)
        self.assertEqual(result['sequences'][1], value['sequences'][1])
        self.assertEqual(result['sequences'][0]['markers'], value['sequences'][0]['markers'])

    def test_bound_source_lane_reference_is_repaired(self):
        value = project()
        value['sequences'][0]['tracks'] += [track('layer', [clip('bed',0,27),clip('rider',31,38)], 'video',1),
            track('target', [clip('label',0,1, tracking_binding={'source_clip_id':'rider','source_track_id':'layer'})], 'subtitle',2)]
        result, plan=self.plan(value,request(('d',),options={'linkage':True}))
        binding=result['sequences'][0]['tracks'][2]['clips'][0]['tracking_binding']
        self.assertEqual(binding['source_track_id'],positions(result)['rider'][0])
        self.assertEqual(plan['rebound_clip_ids'],['label'])
        value['sequences'][0]['tracks'][2]['locked']=True
        self.rejects(value,request(('d',),options={'linkage':True}),'EDIT_BOUND_REFERENCE_LOCKED')

    def test_true_transition_preserves_complete_adjacent_block_and_linked_audio(self):
        value=project()
        for c in value['sequences'][0]['tracks'][0]['clips']: c['link_id']=c['id']+'g'
        value['sequences'][0]['tracks'].append(track('voice',[clip('vb',10,20,link_id='bg'),clip('vc',20,30,link_id='cg')],'audio',1))
        declaration={'id':'cut_bc','type':'dissolve','duration_tick':2,'from_clip_id':'b','to_clip_id':'c',
                     'audio_pairs':[{'from_clip_id':'vb','to_clip_id':'vc'}]}
        value['sequences'][0]['source_transitions']=[declaration]
        result,plan=self.plan(value,request(('b','c')))
        self.assertEqual(result['sequences'][0]['source_transitions'],[declaration])
        self.assertEqual(positions(result)['vb'][1:],(0,10))
        self.assertEqual(plan['removed_transition_ids'],[])

    def test_broken_true_transition_rejects_or_explicitly_drops_only_broken(self):
        value=project()
        declaration={'id':'cut_ab','type':'dissolve','duration_tick':2,'from_clip_id':'a','to_clip_id':'b','audio_pairs':[]}
        broken={'id':'cut_cd','type':'dissolve','duration_tick':2,'from_clip_id':'c','to_clip_id':'d','audio_pairs':[]}
        value['sequences'][0]['source_transitions']=[declaration,broken]
        self.rejects(value,request(('d',),'a'),'EDIT_REORDER_TRANSITION_CONFLICT')
        result,plan=self.plan(value,request(('d',),'a',transition_policy='drop_broken'))
        self.assertEqual(result['sequences'][0]['source_transitions'],[declaration])
        self.assertEqual(plan['removed_transition_ids'],['cut_cd'])
        self.assertEqual(plan['warnings'][0]['code'],'EDIT_REORDER_TRANSITIONS_REMOVED')

    def test_legacy_cross_transition_cannot_silently_retarget_but_fade_stays(self):
        value=project()
        value['sequences'][0]['tracks'][0]['clips'][0].update(transition_out={'type':'dissolve','duration_tick':2},
                                                             transition_in={'type':'fade','duration_tick':1})
        self.rejects(value,request(('b',),'d'),'EDIT_REORDER_TRANSITION_CONFLICT')
        result,plan=self.plan(value,request(('b',),'d',transition_policy='drop_broken'))
        a=next(c for c in result['sequences'][0]['tracks'][0]['clips'] if c['id']=='a')
        self.assertNotIn('transition_out',a)
        self.assertEqual(a['transition_in'],{'type':'fade','duration_tick':1})
        self.assertEqual(plan['dropped_legacy_transition_fields'][0]['field'],'transition_out')

    def test_unknown_fields_duplicate_ids_bad_targets_and_boolean_options_reject(self):
        invalid=[{'action':'reorder','clip_ids':['c']},request(('c','c')),request(before=True),
                 request(before='missing'),request(options={'linked':1}),request(options={'ripple':True}),
                 request(at_tick=1),request(transition_policy='silent')]
        for q in invalid:
            with self.subTest(q=q):
                self.rejects(project(),q,'EDIT_REORDER_TARGET_INVALID' if q.get('before_clip_id')=='missing' else 'EDIT_REQUEST_INVALID')

    def test_locked_main_initial_overlap_and_non_main_selection_reject(self):
        value=project();value['sequences'][0]['tracks'][0]['locked']=True
        self.rejects(value,request(),'EDIT_TRACK_LOCKED')
        value=project();value['sequences'][0]['tracks'][0]['clips'][1]['timeline_start_tick']=5
        self.rejects(value,request(),'EDIT_REORDER_MAIN_OVERLAP')
        value=project();value['sequences'][0]['tracks'].append(track('voice',[clip('v',0,10)],'audio',1))
        self.rejects(value,request(('v',)),'EDIT_REORDER_MAIN_SELECTION_REQUIRED')

    def test_fractional_fps_and_large_tick_grid_do_not_round(self):
        a=2**60+3
        value=project([track('main',[clip('a',a,a+1),clip('b',a+2,a+3),clip('c',a+4,a+5)])])
        value['settings']['timebase']={'ticks_per_second':90000,'display_fps':{'num':30000,'den':1001}}
        result,plan=self.plan(value,request())
        self.assertEqual(positions(result),{'c':('main',0,1),'a':('main',1,2),'b':('main',2,3)})
        self.assertEqual(plan['removed_gap_tick'],a+2)

    def test_explicit_main_configuration_and_empty_video_track(self):
        value=project()
        value['sequences'][0]['tracks'].append(track('other',[clip('e',0,10),clip('f',10,20)],order=5))
        value['sequences'][0]['editing']={'main_track_id':'other'}
        result,plan=self.plan(value,request(('f',),'e'))
        self.assertEqual(plan['after_main_order'],['f','e'])
        self.assertEqual(result['sequences'][0]['tracks'][0],value['sequences'][0]['tracks'][0])
        value=project([track('voice',[],'audio')])
        self.rejects(value,request(),'EDIT_MAIN_TRACK_REQUIRED')

    def test_resource_gate_is_explicit_and_does_not_shrink_selection(self):
        with patch('ai_ad_editor.magnetic_reorder.MAX_CLIPS',2):
            self.rejects(project(),request(),'EDIT_REORDER_RESOURCE_LIMIT')

    def test_planning_starts_no_process_or_network(self):
        with patch('subprocess.Popen', side_effect=AssertionError('unexpected process')), \
                patch('socket.socket', side_effect=AssertionError('unexpected network')):
            result, plan = self.plan(project(), request())
        self.assertEqual(plan['after_main_order'], ['c', 'a', 'b', 'd'])
        self.assertEqual(positions(result)['c'], ('main', 0, 10))

    def test_legacy_shift_collision_contract_is_unchanged_control(self):
        self.rejects(project(),{'action':'shift','clip_ids':['b'],'delta_tick':-5},'EDIT_MAIN_TRACK_COLLISION')

    def test_legacy_gap_closing_still_works_control(self):
        value=project([track('main',[clip('a',1,11),clip('b',13,23)])])
        result,_=self.plan(value,{'action':'close_gaps'})
        self.assertEqual(positions(result),{'a':('main',0,10),'b':('main',10,20)})


class MagneticReorderCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='magnetic-cli-fixture-');cls.addClassCleanup(cls.temp.cleanup)
        cls.fixture,p=create_project(Path(cls.temp.name)/'project',name='magnetic')
        image=Path(cls.temp.name)/'source.png';Image.new('RGB',(32,24),(90,130,200)).save(image)
        code,result=invoke('media','ingest','--project',cls.fixture,'--input',image,'--asset-id','media')
        if code: raise AssertionError(result)
        p=json.loads((cls.fixture/'project.json').read_bytes());p['settings']['canvas'].update(width=32,height=24)
        p['settings']['timebase']['display_fps']={'num':10,'den':1}
        p['sequences'][0].update(duration_tick=270000,tracks=[track('main',[
            clip(c,i*90000,(i+1)*90000,source_in_tick=0,source_out_tick=90000) for i,c in enumerate('abc')])])
        save_project(cls.fixture,p)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='magnetic-cli-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'project';shutil.copytree(self.fixture,self.root)
        self.query=Path(self.temp.name)/'request.json'

    def digest(self):
        return {p.relative_to(self.root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.root.rglob('*') if p.is_file() and '.lock' not in p.name}

    def call(self,q,*options):
        self.query.write_text(json.dumps(q),encoding='utf-8')
        return invoke('timeline','edit','--project',self.root,'--input',self.query,*options)

    def test_dry_run_apply_idempotency_and_stale_plan_gate(self):
        before=self.digest();code,planned=self.call(request(),'--dry-run')
        self.assertEqual(code,0,planned);self.assertEqual(self.digest(),before)
        base=planned['data']['plan']['base_project_sha256']
        code,first=self.call(request(),'--expected-project-sha256',base,'--idempotency-key','reorder')
        self.assertEqual(code,0,first);after=self.digest()
        code,replay=self.call(request(),'--expected-project-sha256',base,'--idempotency-key','reorder')
        self.assertEqual(code,0,replay);self.assertEqual(replay['operation_id'],first['operation_id'])
        self.assertEqual(self.digest(),after)
        code,rejected=self.call(request(),'--expected-project-sha256',base)
        self.assertEqual(code,2,rejected);self.assertEqual(rejected['errors'][0]['code'],'EDIT_PROJECT_CHANGED')
        self.assertEqual(self.digest(),after)

    def test_operation_record_failure_rolls_back_project_and_snapshot(self):
        before=self.digest()
        with patch('ai_ad_editor.cli._operation',side_effect=OSError('reorder operation write fault')):
            with self.assertRaisesRegex(OSError,'reorder operation'):
                self.call(request())
        self.assertEqual(self.digest(),before)

    def test_compose_batch_dry_run_and_late_failure_are_atomic(self):
        q={'operations':[{'op':'linked_edit','edit':request()}]}
        self.query.write_text(json.dumps(q),encoding='utf-8');before=self.digest()
        code,result=invoke('timeline','compose','--project',self.root,'--input',self.query,'--dry-run')
        self.assertEqual(code,0,result);self.assertEqual(self.digest(),before)
        q['operations'].append({'op':'not-a-real-operation'})
        self.query.write_text(json.dumps(q),encoding='utf-8')
        code,result=invoke('timeline','compose','--project',self.root,'--input',self.query)
        self.assertEqual(code,2,result);self.assertEqual(self.digest(),before)
        q['operations'].pop();self.query.write_text(json.dumps(q),encoding='utf-8')
        code,result=invoke('timeline','compose','--project',self.root,'--input',self.query)
        self.assertEqual(code,0,result)
        p=json.loads((self.root/'project.json').read_bytes())
        self.assertEqual([c['id'] for c in p['sequences'][0]['tracks'][0]['clips']],['c','a','b'])

    def test_project_package_roundtrip_keeps_reordered_authors(self):
        code,result=self.call(request());self.assertEqual(code,0,result)
        before=json.loads((self.root/'project.json').read_bytes())
        target=Path(self.temp.name)/'reorder.zip';restored=Path(self.temp.name)/'restored'
        code,result=invoke('convert','export','--project',self.root,'--target-format','package','--output',target)
        self.assertEqual(code,0,result)
        code,result=invoke('convert','import','--input',target,'--output',restored)
        self.assertEqual(code,0,result)
        after=json.loads((restored/'project.json').read_bytes())
        self.assertEqual(before['sequences'],after['sequences'])

    def test_provenance_and_capability_stay_local_only(self):
        code,result=self.call(request());self.assertEqual(code,0,result)
        code,result=invoke('policy','audit','--project',self.root)
        self.assertEqual(code,0,result);self.assertEqual(result['data']['findings'],[])
        code,result=invoke('capabilities')
        self.assertEqual(code,0,result)
        self.assertIn('agent-main-track-reorder-v1',json.dumps(result))
