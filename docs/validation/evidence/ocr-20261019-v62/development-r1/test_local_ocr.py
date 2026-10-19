"""Protocol/geometry/transaction checks; native neural evidence is separate."""
from __future__ import annotations
import contextlib
import copy
import io
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ai_ad_editor import local_ocr as ocr
from ai_ad_editor.animation import keyframe_value
from ai_ad_editor.cli import main
from ai_ad_editor.errors import AppError
from ai_ad_editor.ocr_geometry import anchor_plan, bounded_center, ctc_decode
from ai_ad_editor.project import initial_project
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.utils import atomic_write_json


def invoke(*arguments):
    stream=io.StringIO()
    with contextlib.redirect_stdout(stream):
        result=main(list(map(str,arguments)))
    return result,json.loads(stream.getvalue())


def frame(index=0, text='Save'):
    return {'frame_index':index,'pts_seconds':index/8,'boxes':[{'text':text,'confidence':.9,'detection_score':.8,
            'polygon':[[200.,100.],[300.,100.],[300.,120.],[200.,120.]],'bbox':[.3125,100/360,100/640,20/360]}]}


class OcrGeometryTests(unittest.TestCase):
    def setUp(self):
        self.report={'source':{'asset_id':'video','kind':'video','width':640,'height':360},'frames':[frame(8)]}
        self.clip={'id':'clip','asset_id':'video','source_in_tick':0,'duration_tick':270000}

    def plan(self,**options):
        return anchor_plan(self.report,self.clip,(640,360),query='Save',frame_index=8,tps=90000,zoom=1.5,hold_seconds=.5,return_seconds=.5,**options)

    def test_ctc_keeps_repeated_letters_after_blank_and_unmodified_unicode(self):
        text,confidence=ctc_decode([1,1,0,1,2,2,3],[.9]*7,['','好','A',' '])
        self.assertEqual(text,'好好A ');self.assertAlmostEqual(confidence,.9)

    def test_ctc_rejects_out_of_bounds_nan_and_invalid_probability(self):
        for indices,probs in (([2],[.8]),([1],[math.nan]),([1],[1.1]),([1],[])):
            with self.subTest(indices=indices,probs=probs),self.assertRaises(ValueError):
                ctc_decode(indices,probs,['','a'])

    def test_camera_centers_interior_and_clamps_edge_to_source_coverage(self):
        self.assertEqual(bounded_center(.5,.5,2),(.5,.5))
        self.assertEqual(bounded_center(0,1,1.5),(.75,.25))
        for zoom in (1,4.1,math.nan):
            with self.assertRaises(ValueError):bounded_center(.5,.5,zoom)

    def test_anchor_keeps_source_clock_and_explicit_full_frame_return(self):
        plan=self.plan();self.assertEqual(plan['focus_start_tick'],90000)
        self.assertEqual(plan['return_end_tick'],180000)
        output={'keyframes':plan['keyframes']}
        self.assertEqual(keyframe_value(output,('transform.scale',),1,89999),1)
        self.assertEqual(keyframe_value(output,('transform.scale',),1,90000),1.5)
        self.assertEqual(keyframe_value(output,('transform.scale',),1,135000),1.5)
        self.assertAlmostEqual(keyframe_value(output,('transform.scale',),1,157500),1.125)
        self.assertEqual(keyframe_value(output,('transform.scale',),1,180000),1)

    def test_duplicate_text_is_rejected_even_when_confidences_differ(self):
        self.report['frames'][0]['boxes'].append({**frame()['boxes'][0],'confidence':.99})
        with self.assertRaises(AppError) as error:self.plan()
        self.assertEqual(error.exception.code,'OCR_QUERY_AMBIGUOUS')

    def test_unscanned_frame_case_difference_and_missing_text_are_not_guessed(self):
        for replacement,expected in (({'frame_index':2},'OCR_FRAME_NOT_SCANNED'),({'text':'SAVE'},'OCR_QUERY_NOT_FOUND')):
            self.report['frames']=[{**frame(8),**replacement}]
            if 'text' in replacement:self.report['frames'][0]['boxes'][0]['text']=replacement['text']
            with self.assertRaises(AppError) as error:self.plan()
            self.assertEqual(error.exception.code,expected)

    def test_transformed_retimed_and_insufficient_tail_clips_are_rejected(self):
        for patch_value in ({'reverse':True},{'speed':2},{'transform':{'scale':1}},{'crop':{'x':0}},
                            {'presentation_window':{}},{'duration_tick':100000}):
            self.clip.update(patch_value)
            with self.subTest(patch_value=patch_value),self.assertRaises(AppError):self.plan()
            self.clip={'id':'clip','asset_id':'video','source_in_tick':0,'duration_tick':270000}

    def test_source_in_is_subtracted_without_changing_report(self):
        before=copy.deepcopy(self.report);self.clip['source_in_tick']=45000
        self.assertEqual(self.plan()['focus_start_tick'],45000);self.assertEqual(self.report,before)


class LocalOcrTests(unittest.TestCase):
    def setUp(self):
        configure_local_runtime();self.temp=tempfile.TemporaryDirectory(prefix='ocr-protocol-');self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.root=self.base/'中文项目'
        self.assertEqual(invoke('project','init',self.root)[0],0)
        self.models=self.base/'models';self.models.mkdir()
        for name in (ocr.DET,ocr.REC):(self.models/name).write_bytes(b'protocol fixture, not neural inference')
        self.proof=self.base/'evidence.txt';self.proof.write_text('internal fixture',encoding='utf-8')
        self.options=['--project',self.root,'--adapter-id','ocr','--model-path',self.models,
                      '--python-executable',sys.executable,'--evidence',self.proof]
        from PIL import Image
        self.image=self.base/'source.png';Image.new('RGB',(640,360),'white').save(self.image)
        code,result=invoke('media','ingest','--project',self.root,'--input',self.image)
        self.assertEqual(code,0,result);self.asset=result['data']['asset']['id']

    def project(self):return json.loads((self.root/'project.json').read_bytes())
    def metadata(self):return tuple((self.root/name).read_bytes() for name in ('project.json','project.lock.json','rights-ledger.json'))
    def register(self):
        code,result=invoke('ocr','adapter','register',*self.options);self.assertEqual(code,0,result);return result['data']['adapter']
    def scan(self,*extra):
        return invoke('ocr','scan','--project',self.root,'--asset-id',self.asset,'--adapter-id','ocr','--output','validation/text.json',*extra)

    def fake_result(self,root,plan,**kwargs):
        response={'protocol':ocr.PROTOCOL,'engine':ocr.ENGINE,'status':'succeeded','network':'disabled','blocked_network_events':[],
            'request_sha256':ocr.digest(plan),'adapter_sha256':plan['adapter']['sha256'],'source_sha256':plan['source']['sha256'],
            'frames':[frame()], 'device':'cpu','providers':['CPUExecutionProvider'],'detector_forwards':1,'recognizer_forwards':1}
        ocr.validate_response(response,plan)
        return {'report_version':'0.1.0','engine':ocr.ENGINE,'source':plan['source'],'adapter_id':'ocr','adapter_sha256':plan['adapter']['sha256'],
                'rights_dependencies':plan['rights_dependencies'],'request':plan,'response':response,'frames':response['frames'],
                'process_cleanup':{'all_children_reaped':True}}

    def test_register_dry_run_list_inspect_and_duplicate_preserve_metadata(self):
        before=self.metadata();code,result=invoke('ocr','adapter','register',*self.options,'--dry-run')
        self.assertEqual(code,0,result);self.assertEqual(before,self.metadata());adapter=self.register()
        self.assertTrue(ocr.verify_adapter(adapter)['ok']);before=self.metadata()
        for action in ('list','inspect'):
            extra=['--adapter-id','ocr'] if action=='inspect' else []
            self.assertEqual(invoke('ocr','adapter',action,'--project',self.root,*extra)[0],0)
            self.assertEqual(self.metadata(),before)
        self.assertEqual(invoke('ocr','adapter','register',*self.options)[0],2);self.assertEqual(self.metadata(),before)

    def test_registration_missing_model_remote_path_and_thread_budgets_reject(self):
        (self.models/ocr.REC).unlink()
        self.assertNotEqual(invoke('ocr','adapter','register',*self.options)[0],0)
        for extra in (['--threads','0'],['--threads','17'],['--model-path','https://invalid.invalid/model']):
            self.assertNotEqual(invoke('ocr','adapter','register',*self.options,*extra)[0],0)

    def test_registered_model_evidence_and_implementation_hash_changes_fail(self):
        adapter=self.register()
        (self.models/ocr.DET).write_bytes(b'changed')
        self.assertFalse(ocr.verify_adapter(adapter)['ok'])
        altered=copy.deepcopy(adapter);altered['network']='enabled'
        self.assertFalse(ocr.verify_adapter(altered)['ok'])

    def test_scan_dry_run_does_not_call_worker_or_write_report(self):
        self.register();before=self.metadata()
        with patch('ai_ad_editor.local_ocr.execute_scan',side_effect=AssertionError('must not run')):
            code,value=self.scan('--dry-run')
        self.assertEqual(code,0,value);self.assertFalse(value['data']['model_executed'])
        self.assertEqual(before,self.metadata());self.assertFalse((self.root/'validation/text.json').exists())

    def test_scan_protocol_report_bound_to_project_and_tamper_rejected(self):
        self.register()
        with patch('ai_ad_editor.local_ocr.execute_scan',side_effect=self.fake_result):
            code,value=self.scan()
        self.assertEqual(code,0,value)
        path,report=ocr.load_report(self.root,self.project(),'validation/text.json')
        self.assertEqual(report['rights_dependencies'],[self.asset,'ocr_adapter_ocr'])
        changed=copy.deepcopy(report);changed['frames'][0]['boxes'][0]['text']='Forged'
        atomic_write_json(path,ocr.seal_report(changed))
        with self.assertRaises(AppError):ocr.load_report(self.root,self.project(),path)

    def test_scan_failure_and_cancel_keep_metadata_and_no_report(self):
        self.register();before=self.metadata()
        for error in (ocr.fail('OCR_WORKER_FAILED','fixture',exit_code=6),ocr.fail('CANCELLED','fixture',exit_code=8)):
            with patch('ai_ad_editor.local_ocr.execute_scan',side_effect=error):
                code,value=self.scan()
            self.assertNotEqual(code,0);self.assertEqual(before,self.metadata());self.assertFalse((self.root/'validation/text.json').exists())

    def test_scan_output_escape_overwrite_and_source_tamper_reject(self):
        self.register()
        for extra in (['--output','elsewhere.json'],['--end-frame','2'],['--step-frames','0']):
            self.assertNotEqual(self.scan(*extra)[0],0)
        self.image.write_bytes(b'changed source')
        self.assertEqual(self.scan()[0],10)

    def test_worker_response_rejects_clock_box_device_and_network_forgery(self):
        adapter=self.register();p=self.project();asset=next(a for a in p['assets'] if a['id']==self.asset)
        plan=ocr.scan_plan(self.root,asset,adapter)
        value=self.fake_result(self.root,plan)['response']
        variants=[]
        for key,bad in (('network','enabled'),('request_sha256','sha256:wrong'),('providers',['CUDAExecutionProvider']),('blocked_network_events',['socket.connect'])):
            variants.append({**value,key:bad})
        bad=copy.deepcopy(value);bad['frames'][0]['pts_seconds']=.2;variants.append(bad)
        bad=copy.deepcopy(value);bad['frames'][0]['boxes'][0]['bbox'][0]=.9;variants.append(bad)
        bad=copy.deepcopy(value);bad['frames'][0]['boxes'][0]['confidence']=math.nan;variants.append(bad)
        for bad in variants:
            with self.assertRaises(AppError):ocr.validate_response(bad,plan)


if __name__=='__main__':unittest.main()
