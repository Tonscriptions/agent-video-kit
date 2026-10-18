"""Persistent operations and full-author synchronization, including real CLI state."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from ai_ad_editor.edit_planner import build_edit_plan, validate_editing
from ai_ad_editor.errors import AppError
from ai_ad_editor.magnetic_mode import validate as validate_magnetic
from ai_ad_editor.project import create_project, save_project
from test_magnetic_reorder import clip, track, project, positions, request, invoke


class MagneticModeTests(unittest.TestCase):
    def plan(self, value, query):
        old = copy.deepcopy(value)
        result = build_edit_plan(value, 'seq', query)
        self.assertEqual(value, old)
        return result

    def rejects(self, value, query, code):
        before = copy.deepcopy(value)
        with self.assertRaises(AppError) as caught:
            build_edit_plan(value, 'seq', query)
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(value, before)

    def bed(self, **fields):
        p = project()
        p['sequences'][0]['tracks'].append(track('bed', [clip('music', 0, 40, **fields)], 'audio', 1))
        return p

    def magnetic(self, value=None):
        p = value or project()
        p['sequences'][0]['editing'] = {'magnetic': True}
        return p

    def test_opt_in_splices_every_source_interval_and_reports_new_clips(self):
        value = self.bed()
        out, plan = self.plan(value, request(options={'sync': True}, sync_span_policy='split'))
        parts = plan['sync_splits'][0]['pieces']
        self.assertEqual([p['original_range_tick'] for p in parts], [[0,10],[10,20],[20,30],[30,40]])
        self.assertEqual([p['after_range_tick'] for p in parts], [[10,20],[20,30],[0,10],[30,40]])
        self.assertEqual(sum(c['duration_tick'] for c in out['sequences'][0]['tracks'][1]['clips']), 40)
        self.assertEqual(len([c for c in plan['changes'] if c['before'] is None]), 3)

    def test_plain_mode_keeps_legacy_rejection(self):
        self.rejects(self.bed(), request(options={'sync': True}), 'EDIT_REORDER_SYNC_SPAN_UNSUPPORTED')

    def test_rigid_equal_delta_body_does_not_split(self):
        value = project()
        value['sequences'][0]['tracks'].append(track('bed', [clip('body', 12, 28)], 'audio', 1))
        _, plan = self.plan(value, request(('b','c'), options={'sync': True}, sync_span_policy='split'))
        self.assertEqual(plan['sync_splits'], [])

    def test_group_members_get_matching_local_links_without_changing_author_fields(self):
        value = self.bed(link_id='group')
        value['sequences'][0]['tracks'].append(track('sub', [clip('caption', 0, 40, link_id='group')], 'subtitle', 2))
        out, plan = self.plan(value, request(options={'sync': True}, sync_span_policy='split'))
        beds, subs = out['sequences'][0]['tracks'][1:]
        self.assertEqual([c['link_id'] for c in beds['clips']], [c['link_id'] for c in subs['clips']])
        self.assertEqual(len(set(c['link_id'] for c in beds['clips'])), 4)
        self.assertEqual(len(plan['sync_splits']), 2)

    def test_reserved_clip_and_link_ids_are_avoided_across_project(self):
        value = self.bed(link_id='group')
        value['assets'] += [{'id':'music_sync_1','kind':'audio'}, {'id':'group_sync_1','kind':'audio'}]
        _, plan = self.plan(value, request(options={'sync': True}, sync_span_policy='split'))
        parts = plan['sync_splits'][0]['pieces']
        self.assertEqual(parts[1]['clip_id'], 'music_sync_1_2')
        self.assertEqual(parts[1]['link_id'], 'group_sync_1_2')

    def test_locked_linked_member_blocks_partition_atomically(self):
        value = self.bed(link_id='group')
        value['sequences'][0]['tracks'].append(track('sub', [clip('caption', 0, 40, link_id='group')], 'subtitle', 2, locked=True))
        self.rejects(value, request(options={'sync':True}, sync_span_policy='split'), 'EDIT_TRACK_LOCKED')

    def test_opt_out_track_is_anchored_even_when_other_tracks_split(self):
        value = self.bed()
        value['sequences'][0]['tracks'].append(track('free', [clip('fixed', 0, 40)], 'audio', 2, sync_lock=False))
        out, _ = self.plan(value, request(options={'sync':True}, sync_span_policy='split'))
        self.assertEqual(positions(out)['fixed'], ('free',0,40))

    def test_direct_main_link_overrides_temporal_partition(self):
        value = self.bed(link_id='g')
        value['sequences'][0]['tracks'][0]['clips'][0]['link_id']='g'
        out, plan = self.plan(value, request(options={'sync':True}, sync_span_policy='split'))
        self.assertEqual(plan['sync_splits'], [])
        self.assertEqual(positions(out)['music'], ('bed',10,50))

    def test_source_window_reverse_curve_freeze_and_nested_payload_stay_unchanged(self):
        fields={'sequence_id':'child','reverse':True,'speed_curve':{'keyframes':[{'at_tick':0,'speed':1}]},
                'freeze':{'at_tick':8,'duration_tick':4},'audio':{'fade_in':.5},
                'presentation_window':{'version':1,'authored_start_tick':7,'authored_duration_tick':60,'offset_tick':5}}
        value=self.bed(**fields)
        original=value['sequences'][0]['tracks'][1]['clips'][0]
        out, _=self.plan(value,request(options={'sync':True},sync_span_policy='split'))
        for i,c in enumerate(out['sequences'][0]['tracks'][1]['clips']):
            self.assertEqual(c['presentation_window'],{'version':1,'authored_start_tick':7,'authored_duration_tick':60,'offset_tick':5+i*10})
            for key in ('source_in_tick','source_out_tick','reverse','speed_curve','freeze','sequence_id','audio'):
                self.assertEqual(c[key],original[key])

    def test_tracking_source_and_target_are_rejected_before_cut(self):
        value=self.bed()
        value['sequences'][0]['tracks'].append(track('labels',[clip('label',0,1,tracking_binding={'source_clip_id':'music'})],'subtitle',2))
        self.rejects(value,request(options={'sync':True},sync_span_policy='split'),'EDIT_REORDER_SYNC_BINDING_UNSUPPORTED')

    def test_cut_reference_and_legacy_transition_do_not_silently_retarget(self):
        value=self.bed()
        value['sequences'][0]['source_transitions']=[{'id':'t','from_clip_id':'a','to_clip_id':'b','audio_pairs':[{'from_clip_id':'music','to_clip_id':'other'}]}]
        self.rejects(value,request(options={'sync':True},sync_span_policy='split'),'EDIT_REORDER_SYNC_TRANSITION_UNSUPPORTED')
        value=self.bed(transition_in={'type':'wipeleft','duration_tick':2})
        self.rejects(value,request(options={'sync':True},sync_span_policy='split'),'CLIP_WINDOW_TRANSITION_CONFLICT')

    def test_expansion_budget_precedes_creation(self):
        with patch('ai_ad_editor.magnetic_reorder.MAX_CLIPS',7):
            self.rejects(self.bed(),request(options={'sync':True},sync_span_policy='split'),'EDIT_REORDER_RESOURCE_LIMIT')

    def test_gap_content_is_kept_at_absolute_time_and_tail_follows_last(self):
        value=project([track('main',[clip('a',0,10),clip('b',20,30),clip('c',30,40)]),
            track('bed',[clip('music',0,45)],'audio',1)])
        out,plan=self.plan(value,request(options={'sync':True},sync_span_policy='split'))
        pieces=plan['sync_splits'][0]['pieces']
        gap=next(p for p in pieces if p['original_range_tick']==[10,20])
        self.assertIsNone(gap['host_clip_id']);self.assertEqual(gap['after_range_tick'],[10,20])
        self.assertEqual(sum(c['duration_tick'] for t in out['sequences'][0]['tracks'][1:] for c in t['clips']),45)

    def test_external_subtitle_author_clock_is_not_double_shifted(self):
        value=self.bed(subtitle={'asset_uri':'assets/sub.srt','asset_time_offset_tick':3})
        out,_=self.plan(value,request(options={'sync':True},sync_span_policy='split'))
        for c in out['sequences'][0]['tracks'][1]['clips']:
            self.assertEqual(c['subtitle']['asset_time_offset_tick'],3)
            self.assertEqual(c['presentation_window']['authored_start_tick'],0)

    def test_enable_disable_and_sync_default_are_persistent(self):
        value=project();value['sequences'][0]['tracks'][0]['clips'][0]['timeline_start_tick']=2
        value['sequences'][0]['tracks'][0]['clips'][0]['duration_tick']=8
        out,plan=self.plan(value,{'action':'magnet','enabled':True})
        self.assertTrue(validate_editing(out['sequences'][0])['sync']);self.assertTrue(plan['magnetic'])
        validate_magnetic(out['sequences'][0]);self.assertEqual(positions(out)['b'][1],8)
        off,_=self.plan(out,{'action':'magnet','enabled':False})
        self.assertFalse(validate_editing(off['sequences'][0])['sync'])

    def test_enabling_contiguous_track_preserves_declared_tail_and_empty_track(self):
        value=project();out,_=self.plan(value,{'action':'magnet','enabled':True})
        self.assertEqual(out['sequences'][0]['duration_tick'],100)
        out['sequences'][0]['tracks'][0]['clips']=[]
        result,_=self.plan(out,{'action':'magnet','enabled':True});validate_magnetic(result['sequences'][0])

    def test_magnetic_shift_snaps_nearest_and_splices_default_sync(self):
        value=self.magnetic(self.bed())
        out,plan=self.plan(value,{'action':'shift','clip_ids':['c'],'delta_tick':-15})
        self.assertEqual(plan['snapped_tick'],0)
        self.assertEqual(plan['steps'][0]['after_main_order'],['c','a','b','d'])
        self.assertEqual(len(plan['steps'][0]['sync_splits']),1)
        validate_magnetic(out['sequences'][0])

    def test_multi_selection_is_stable_and_side_track_move_keeps_normal_semantics(self):
        value=self.magnetic(self.bed());out,plan=self.plan(value,{'action':'shift','clip_ids':['d','b'],'delta_tick':-10})
        self.assertEqual(plan['steps'][0]['after_main_order'],['b','d','a','c'])
        out,plan=self.plan(value,{'action':'shift','clip_ids':['music'],'delta_tick':2})
        self.assertEqual(positions(out)['music'][1],2);self.assertEqual(plan['engine'],'agent-tick-linked-edit-v1')

    def test_magnetic_delete_removes_sync_range_and_keeps_remaining_source_windows(self):
        value=self.magnetic(self.bed());out,_=self.plan(value,{'action':'remove','clip_ids':['b']})
        self.assertEqual([c['id'] for c in out['sequences'][0]['tracks'][0]['clips']],['a','c','d'])
        self.assertEqual(positions(out)['c'][1:],(10,20))
        audio=out['sequences'][0]['tracks'][1]['clips']
        self.assertEqual(sum(c['duration_tick'] for c in audio),30)
        self.assertEqual([c['presentation_window']['offset_tick'] for c in audio],[0,20])
        validate_magnetic(out['sequences'][0])

    def test_magnetic_negative_mixed_and_invalid_requests_are_atomic(self):
        value=self.magnetic(self.bed())
        self.rejects(value,{'action':'shift','clip_ids':['a'],'delta_tick':-1},'EDIT_REQUEST_INVALID')
        self.rejects(value,{'action':'shift','clip_ids':['a','music'],'delta_tick':0},'EDIT_MAGNETIC_MIXED_SELECTION')
        self.rejects(value,{'action':'magnet','enabled':1},'EDIT_REQUEST_INVALID')
        self.rejects(value,request(sync_span_policy=[]),'EDIT_REQUEST_INVALID')


class MagneticModeCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'.runtime')
        self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.root,_=create_project(self.root/'project','magnet');self.path=self.root/'project.json'
        source=Path(self.tmp.name)/'image.png';Image.new('RGB',(64,32),'red').save(source)
        code,result=invoke('media','ingest','--project',self.root,'--input',source,'--asset-id','media')
        self.assertEqual(code,0,result)
        p=json.loads(self.path.read_bytes());p['settings']['timebase']['ticks_per_second']=10
        p['settings']['timebase']['display_fps']={'num':10,'den':1}
        p['sequences']=[project()['sequences'][0]];p['sequences'][0]['duration_tick']=40
        save_project(self.root,p)

    def call(self,query,*,edit=True,extra=(),expected=0):
        path=Path(self.tmp.name)/'input.json';path.write_text(json.dumps(query),encoding='utf-8')
        code,result=invoke('timeline','edit' if edit else 'compose','--project',self.root,'--sequence-id','seq','--input',path,*extra)
        self.assertEqual(code,expected,result);return result

    def state(self):return json.loads(self.path.read_bytes())

    def enable(self):self.call({'action':'magnet','enabled':True})

    def test_dry_run_and_idempotent_mode_commit(self):
        before=self.path.read_bytes();self.call({'action':'magnet','enabled':True},extra=('--dry-run',))
        self.assertEqual(self.path.read_bytes(),before)
        one=self.call({'action':'magnet','enabled':True},extra=('--idempotency-key','magnet-on'))
        before=self.path.read_bytes();two=self.call({'action':'magnet','enabled':True},extra=('--idempotency-key','magnet-on'))
        self.assertEqual(self.path.read_bytes(),before);self.assertEqual(one['operation_id'],two['operation_id'])

    def test_append_snaps_and_inserts_then_remove_and_move_use_mode(self):
        self.enable()
        self.call({'operations':[{'op':'append_clip','track_id':'main','id':'e','asset_id':'media',
            'source_in_tick':0,'source_out_tick':10,'timeline_start_tick':13}]},edit=False)
        self.assertEqual(positions(self.state())['e'][1:],(10,20))
        self.call({'operations':[{'op':'remove_clip','clip_id':'e'},{'op':'slide_clip','clip_id':'c','delta_tick':-20}]},edit=False)
        self.assertEqual(positions(self.state())['c'][1:],(0,10));validate_magnetic(self.state()['sequences'][0])

    def test_trim_extracts_both_edges_and_follows_next_shot(self):
        self.enable();self.call({'operations':[{'op':'trim_clip','clip_id':'b','start_tick':2,'end_tick':8}]},edit=False)
        state=self.state();self.assertEqual(positions(state)['b'][1:],(10,16))
        self.assertEqual(positions(state)['c'][1:],(16,26))
        b=next(c for c in state['sequences'][0]['tracks'][0]['clips'] if c['id']=='b')
        self.assertEqual(b['presentation_window']['offset_tick'],2)

    def test_unsupported_geometry_and_stale_hash_roll_back_whole_transaction(self):
        self.enable();before=self.path.read_bytes()
        self.call({'operations':[{'op':'add_marker','at_tick':1},{'op':'update_clip','clip_id':'a','patch':{'duration_tick':5}}]},edit=False,expected=2)
        self.assertEqual(self.path.read_bytes(),before)
        self.call({'action':'remove','clip_ids':['a']},extra=('--expected-project-sha256','sha256:'+'0'*64),expected=2)
        self.assertEqual(self.path.read_bytes(),before)

    def test_mode_field_types_and_gap_invariant_are_enforced(self):
        before=self.path.read_bytes()
        self.call({'operations':[{'op':'update_sequence','patch':{'editing':{'magnetic':'yes'}}}]},edit=False,expected=2)
        self.assertEqual(before,self.path.read_bytes());self.enable();before=self.path.read_bytes()
        self.call({'operations':[{'op':'update_clip','clip_id':'b','patch':{'timeline_start_tick':12}}]},edit=False,expected=2)
        self.assertEqual(before,self.path.read_bytes())

    def test_partial_fragment_expands_complete_magnetic_sequence_and_applies(self):
        self.enable();self.call({'action':'shift','clip_ids':['c'],'delta_tick':-20})
        query=Path(self.tmp.name)/'fragment.json';library=Path(self.tmp.name)/'library'
        query.write_text(json.dumps({'id':'magnet','version':1,'name':'magnet','sequence_id':'seq','clip_ids':['a']}),encoding='utf-8')
        code,result=invoke('fragment','save','--project',self.root,'--library',library,'--input',query)
        self.assertEqual(code,0,result)
        self.assertEqual(result['data']['fragment']['selection']['included'],['a','b','c','d'])
        target,p=create_project(Path(self.tmp.name)/'target','magnet target')
        p['settings']['timebase']['ticks_per_second']=10;p['settings']['timebase']['display_fps']={'num':10,'den':1};save_project(target,p)
        seq=p['sequences'][0]
        query.write_text(json.dumps({'id':'magnet','version':1,'sequence_id':seq['id'],
            'track_id':seq['tracks'][0]['id'],'at_tick':0,'instance_id':'magnet_instance'}),encoding='utf-8')
        code,result=invoke('fragment','apply','--project',target,'--library',library,'--input',query)
        self.assertEqual(code,0,result)
        after=json.loads((target/'project.json').read_bytes())
        child=next(s for s in after['sequences'] if s.get('editing',{}).get('magnetic'))
        validate_magnetic(child)


if __name__=='__main__':unittest.main()
