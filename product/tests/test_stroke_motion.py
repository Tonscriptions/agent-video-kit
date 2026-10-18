from __future__ import annotations

import copy
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock
import zipfile

from ai_ad_editor import stroke_motion as stroke
from ai_ad_editor import html_motion as html
from ai_ad_editor.errors import AppError
from ai_ad_editor.project import create_project, load_project
from test_html_motion import cli


def authored():
    return {'version':stroke.ENGINE,'width':96,'height':64,'fps':{'num':4,'den':1},
        'duration_tick':90000,'stroke_width':4,'color':'#36c987','characters':[
            {'text':'A','start_tick':0,'end_tick':30000,'strokes':[[[10,40],[30,10],[50,40]],[[20,30],[40,30]]]},
            {'text':' ','start_tick':30000,'end_tick':45000,'strokes':[]},
            {'text':'字','start_tick':60000,'end_tick':90000,'strokes':[[[60,10],[80,40]]]}
        ]}


class StrokePlanTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='stroke-unit-')
        self.addCleanup(self.temp.cleanup)
        self.root,self.project=create_project(Path(self.temp.name)/'project')
        self.path=Path(self.temp.name)/'plan.json'
        self.value=authored()
        self.write()

    def write(self):
        self.path.write_text(json.dumps(self.value,ensure_ascii=False),encoding='utf-8')

    def prepare(self):return stroke.prepare(self.value,90000)

    def reject(self,expected='STROKE_PLAN_INVALID'):
        with self.assertRaises(AppError) as result:self.prepare()
        self.assertEqual(result.exception.code,expected)

    def test_length_matches_independent_geometry_and_spaces(self):
        spec,geo,report=self.prepare()
        total=2*(20**2+30**2)**0.5+20+(20**2+30**2)**0.5
        self.assertAlmostEqual(geo['stroke']['total'],total)
        self.assertEqual(geo['stroke']['charRange'][1],[total-(20**2+30**2)**0.5]*2)
        self.assertEqual(report['text'],'A 字')
        self.assertEqual(report['points'],7)
        self.assertFalse(report['automatic_alignment'])

    def test_pack_deterministic_with_original_input_and_licenses(self):
        a,plan=stroke.build_source(self.root,self.project,str(self.path))
        b,_=stroke.build_source(self.root,self.project,str(self.path))
        self.assertEqual(a,b)
        with zipfile.ZipFile(io.BytesIO(a)) as z:
            self.assertEqual(z.read('authored-plan.json'),self.path.read_bytes())
            self.assertEqual(z.read('openfilm_stroke.mjs'),Path(stroke.__file__).with_name('openfilm_stroke.mjs').read_bytes())
            self.assertIn('PDOOM_VIDEO_LICENSE.txt',z.namelist())
            self.assertNotIn(b'fetch(',z.read('openfilm_stroke.mjs'))
        self.assertEqual(plan['stroke']['input_sha256'],html.digest(self.path.read_bytes()))

    def test_unknown_keys_fail(self):self.value['audio_url']='https://invalid';self.reject()
    def test_boolean_coordinate_fails(self):self.value['characters'][0]['strokes'][0][0][0]=True;self.reject()
    def test_nonfinite_fails(self):self.value['characters'][0]['strokes'][0][0][0]=float('nan');self.reject()
    def test_large_integer_fails(self):self.value['characters'][0]['strokes'][0][0][0]=10**2000;self.reject()
    def test_line_cap_outside_fails(self):self.value['characters'][0]['strokes'][0][0][0]=1;self.reject()
    def test_zero_length_fails(self):self.value['characters'][0]['strokes']=[[[10,10],[10,10]]];self.reject()
    def test_missing_glyph_fails(self):self.value['characters'][0]['strokes']=[];self.reject()
    def test_multi_codepoint_fails(self):self.value['characters'][0]['text']='AB';self.reject()
    def test_surrogate_fails(self):self.value['characters'][0]['text']='\ud800';self.reject()
    def test_overlapping_times_fail(self):self.value['characters'][1]['start_tick']=1;self.reject()
    def test_duration_overrun_fails(self):self.value['characters'][-1]['end_tick']=90001;self.reject()
    def test_only_space_fails(self):self.value['characters']=self.value['characters'][1:2];self.reject()
    def test_css_injection_color_fails(self):self.value['color']='red; background:url(https://invalid)';self.reject()
    def test_character_budget_fails(self):self.value['characters']*=100;self.reject()
    def test_point_work_budget_fails(self):
        self.value['fps']={'num':120,'den':1};self.value['duration_tick']=900000
        self.value['characters'][0]['strokes']=[[[10,10],[40,40]]*1000]*4
        self.reject('STROKE_PLAN_BUDGET')

    def test_duplicate_json_keys_and_nonfinite_raw_rejected(self):
        for data in (b'{"version":1,"version":2}',b'{"x":NaN}',b'{"x":Infinity}'):
            self.path.write_bytes(data)
            with self.assertRaises(AppError):stroke.build_source(self.root,self.project,str(self.path))

    def test_text_cannot_escape_into_executable_page(self):
        self.value['characters'][0]['text']='<'
        self.write();content,_=stroke.build_source(self.root,self.project,str(self.path))
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            self.assertEqual(z.read('index.html'),stroke.PAGE)
            self.assertIn(b'"text": "<"',z.read('authored-plan.json'))

    def test_dry_run_does_not_write_project_or_source(self):
        before=(self.root/'project.json').read_bytes()
        code,result=cli('motion','stroke-source','--project',self.root,'--input',self.path,'--asset-id','title','--dry-run')
        self.assertEqual(code,0,result);self.assertEqual(result['command'],'motion.stroke-source')
        self.assertEqual((self.root/'project.json').read_bytes(),before)
        self.assertFalse(list((self.root/'assets').rglob('*.zip')))

    def test_registration_rights_idempotency_and_original_inspection(self):
        args=('motion','stroke-source','--project',self.root,'--input',self.path,'--asset-id','title','--idempotency-key','title-one')
        code,one=cli(*args);self.assertEqual(code,0,one)
        code,two=cli(*args);self.assertEqual(code,0,two)
        self.assertEqual(two['warnings'][-1]['code'],'IDEMPOTENT_REPLAY')
        p=load_project(self.root)[1];self.assertEqual(len(p['assets']),1)
        self.assertEqual(html.inspect_source(self.root,p,'title')['data']['authored-plan.json'],self.path.read_bytes())
        ledger=json.loads((self.root/'rights-ledger.json').read_bytes())
        self.assertEqual(ledger['records'][0]['verification_status'],'unverified')
        self.assertEqual(ledger['records'][0]['permitted_uses'],['internal'])
        code,result=cli('motion','stroke-source','--project',self.root,'--input',self.path,'--asset-id','title')
        self.assertEqual(code,2,result)

    def test_failed_save_rolls_back_metadata_and_new_zip(self):
        before=(self.root/'project.json').read_bytes();ledger=(self.root/'rights-ledger.json').read_bytes()
        with mock.patch('ai_ad_editor.cli.save_ledger',side_effect=AppError('TEST_FAILURE','forced',exit_code=2)):
            code,result=cli('motion','stroke-source','--project',self.root,'--input',self.path,'--asset-id','title')
        self.assertEqual(code,2,result)
        self.assertEqual((self.root/'project.json').read_bytes(),before)
        self.assertEqual((self.root/'rights-ledger.json').read_bytes(),ledger)
        self.assertFalse(list((self.root/'assets').rglob('*.zip')))


@unittest.skipUnless(os.environ.get('AI_AD_EDITOR_TEST_HTML_RUNTIME'),'explicit native HTML runtime required')
class StrokeOriginalCoreTests(unittest.TestCase):
    def test_original_core_against_independent_line_endpoint_oracle(self):
        runtime=json.loads(Path(os.environ['AI_AD_EDITOR_TEST_HTML_RUNTIME']).read_bytes())
        module=Path(stroke.__file__).with_name('openfilm_stroke.mjs').as_uri()
        # No Canvas or production length compiler in this independent 3-4-5 oracle.
        code='''import {drawStrokeText,writtenLength} from MODULE;
const s={strokes:[[{x:0,y:0},{x:3,y:4}],[{x:10,y:0},{x:10,y:5}]],
lens:[[0,5],[0,5]],startLen:[0,5],charRange:[[0,5],[5,5],[5,10]]};
const ts=[[0,1],[1,1.5],[2,3]], order=[3,0,.5,2.5,1.5,2,.5];
const result=order.map(t=>{const lines=[];const c={beginPath(){},stroke(){},moveTo(x,y){lines.push(['M',x,y])},lineTo(x,y){lines.push(['L',x,y])}};
const length=writtenLength(s,ts,t);return {t,length,head:drawStrokeText(c,s,length),lines}});
console.log(JSON.stringify(result));'''.replace('MODULE',json.dumps(module))
        result=subprocess.run([runtime['node'],'--input-type=module','-e',code],capture_output=True,timeout=30,check=True)
        rows=json.loads(result.stdout)
        self.assertEqual([r['length'] for r in rows],[10,0,2.5,7.5,5,5,2.5])
        self.assertEqual(rows[2]['head']['x'],1.5);self.assertEqual(rows[2]['head']['y'],2)
        self.assertEqual(rows[3]['head']['x'],10);self.assertEqual(rows[3]['head']['y'],2.5)
        self.assertEqual(rows[2],rows[-1]);self.assertIsNone(rows[1]['head'])
