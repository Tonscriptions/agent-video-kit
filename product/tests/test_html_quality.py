from __future__ import annotations
import json,os,shutil,tempfile,unittest
from pathlib import Path
from ai_ad_editor import html_motion as html
from ai_ad_editor.project import create_project,load_project
from ai_ad_editor.utils import atomic_write_json
from ai_ad_editor.policy import audit_local_tree
from test_html_motion import cli,spec,TPS

FONT=Path(__file__).resolve().parents[2]/'docs/assets/html-template-20261018/template/font.ttf'


@unittest.skipUnless(os.environ.get('AI_AD_EDITOR_TEST_HTML_RUNTIME'),'explicit existing native HTML toolchain not configured')
class NativeHTMLQualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime=html.prepare_runtime(Path.cwd(),json.loads(Path(os.environ['AI_AD_EDITOR_TEST_HTML_RUNTIME']).read_text(encoding='utf-8')))

    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='html-quality-native-');self.addCleanup(temp.cleanup)
        self.root,_=create_project(Path(temp.name)/'project');self.folder=Path(temp.name)/'source';self.folder.mkdir()
        atomic_write_json(self.root/'config/html-motion-runtime.json',self.runtime);shutil.copyfile(FONT,self.folder/'font.ttf')
        code,result=cli('media','ingest','--project',self.root,'--input',FONT,'--asset-id','font')
        self.assertEqual(code,0,result)
        self.serial=0

    def source(self,*,css='',text='CTA',wrapper=False,frame='',extra=''):
        self.serial+=1;asset='source'+str(self.serial)
        body='<p id="words">'+text+'</p>'
        if wrapper:body='<div id="box">'+body+'</div>'
        page='''<!doctype html><meta charset="utf-8"><style>@font-face{font-family:Grid;src:url(font.ttf)}
        html,body{margin:0;width:96px;height:64px;overflow:hidden;background:#101829}
        p{margin:0;position:absolute;left:4px;top:8px;font:16px Grid;line-height:20px;color:white}'''+css+'</style>'+body+extra+'''
        <script>window.film={frame(t){'''+frame+'}}</script>'
        (self.folder/'index.html').write_text(page,encoding='utf-8')
        atomic_write_json(self.folder/'manifest.json',spec(resources=[{'path':'font.ttf','asset_id':'font'}]))
        code,result=cli('motion','html-source','--project',self.root,'--input',self.folder/'manifest.json','--asset-id',asset)
        self.assertEqual(code,0,result);return asset

    def quality(self,source,*args,expected=0):
        before=(self.root/'project.json').read_bytes();ledger=(self.root/'rights-ledger.json').read_bytes()
        code,result=cli('motion','html-quality','--project',self.root,'--source-asset-id',source,*args)
        self.assertEqual(code,expected,result)
        self.assertEqual((self.root/'project.json').read_bytes(),before);self.assertEqual((self.root/'rights-ledger.json').read_bytes(),ledger)
        path=Path(result['data']['report'] if code==0 else result['errors'][0]['path'])
        report=json.loads(path.read_text(encoding='utf-8'))
        self.assertTrue(report['cleanup']['all_children_reaped']);self.assertEqual(report['cleanup']['active_after_cleanup'],[])
        return report,result

    def test_all_frames_font_sources_geometry_and_previews(self):
        source=self.source(frame='words.style.left=(4+Math.round(t*4))+"px";')
        report,_=self.quality(source)
        self.assertTrue(report['quality_passed']);self.assertEqual(report['frame_count'],4)
        self.assertTrue(report['all_frame_orders_equal']);self.assertEqual(report['text_ranges_checked'],4)
        self.assertEqual(report['worker']['cleanup']['pages_opened'],2)
        self.assertEqual(report['worker']['cleanup']['pages_closed'],2)
        for f in report['frames']:
            row=f['layout']['rows'][0];self.assertTrue(row['mapping_checked'])
            self.assertEqual(row['platform_fonts'][0]['postScriptName'],'AgentGridCC0-Regular')
        self.assertTrue((self.root/report['frames'][0]['preview']).is_file())

    def test_partial_and_fully_outside_text_are_distinct(self):
        for left,expected in ((86,'TEXT_CLIPPED_FRAME'),(110,'TEXT_OUTSIDE_FRAME')):
            source=self.source(css=f'p{{left:{left}px}}');report,_=self.quality(source,expected=2)
            self.assertIn(expected,{x['code'] for x in report['issues']})
            if left==110:self.assertTrue(all(not f['layout']['upstream_partial_clipping'] for f in report['frames']))

    def test_container_x_and_y_clipping_are_independent(self):
        for axis,css in [('x','#box{position:absolute;left:8px;top:8px;width:8px;height:5px;overflow-x:clip;overflow-y:visible}p{left:0;top:16px}'),
                         ('y','#box{position:absolute;left:8px;top:8px;width:80px;height:5px;overflow-y:clip;overflow-x:visible}p{left:4px;top:8px}')]:
            report,_=self.quality(self.source(css=css,wrapper=True),expected=2)
            issues=[x for x in report['issues'] if 'CONTAINER' in x['code']]
            self.assertTrue(issues);self.assertTrue(all(x['axes']==[axis] for x in issues))

    def test_last_frame_problem_cannot_hide_behind_first_sample(self):
        report,_=self.quality(self.source(frame='words.style.left=t<0.75?"4px":"110px";'),expected=2)
        self.assertEqual({x['frame'] for x in report['issues']},{3})

    def test_body_clip_is_distinct_from_propagated_viewport_overflow(self):
        report,_=self.quality(self.source(css='html{overflow:hidden}body{width:12px;overflow:hidden}p{left:4px}'),expected=2)
        self.assertTrue(any(x['code']=='TEXT_CLIPPED_CONTAINER' for x in report['issues']))
        report,_=self.quality(self.source(css='html{overflow:visible}body{width:12px;height:0;overflow:hidden}p{left:4px}'))
        self.assertTrue(report['quality_passed'])

    def test_source_font_missing_character_and_real_fallback(self):
        report,_=self.quality(self.source(text='B'),expected=2)
        self.assertIn('FONT_GLYPH_MISSING',{x['code'] for x in report['issues']})
        self.assertIn('U+0042',next(x['codepoints'] for x in report['issues'] if x['code']=='FONT_GLYPH_MISSING'))
        self.assertFalse(report['frames'][0]['layout']['rows'][0]['platform_fonts'][0]['isCustomFont'])

    def test_hidden_parent_does_not_create_false_visible_text(self):
        report,_=self.quality(self.source(css='#box{opacity:0}p{left:120px}',text='B',wrapper=True))
        self.assertEqual(report['text_ranges_checked'],0);self.assertTrue(report['quality_passed'])

    def test_rotation_and_canvas_are_explicit_unverified_regions(self):
        for kwargs in ({'css':'p{transform:rotate(15deg)}'},{'extra':'<canvas width="4" height="4"></canvas>'}):
            report,_=self.quality(self.source(**kwargs),expected=2)
            self.assertIn('LAYOUT_UNVERIFIED',{x['code'] for x in report['issues']})

    def test_nested_words_and_literal_colon_remain_policy_compatible(self):
        report,_=self.quality(self.source(text='CTA:<em>EDIT</em>'),expected=2)
        # Colon is absent in the original fixture font, and must be diagnosed.
        self.assertIn('FONT_GLYPH_MISSING',{x['code'] for x in report['issues']})
        self.assertTrue(audit_local_tree(self.root)['ok'])

    def test_strict_render_rejects_before_new_asset_and_preserves_state(self):
        source=self.source(css='p{left:110px}')
        before=(self.root/'project.json').read_bytes();ledger=(self.root/'rights-ledger.json').read_bytes()
        code,result=cli('motion','html-render','--project',self.root,'--source-asset-id',source,'--asset-id','blocked','--layout-check','strict')
        self.assertEqual(code,2,result);self.assertEqual(result['errors'][0]['code'],'HTML_QUALITY_FAILED')
        report_path=Path(result['errors'][0]['path']);self.assertTrue(report_path.is_file())
        report=json.loads(report_path.read_text(encoding='utf-8'))
        self.assertTrue(report['validation_complete']);self.assertEqual(report['status'],'failed')
        self.assertTrue((self.root/report['frames'][0]['preview']).is_file())
        self.assertEqual(before,(self.root/'project.json').read_bytes());self.assertEqual(ledger,(self.root/'rights-ledger.json').read_bytes())
        self.assertFalse(list((self.root/'assets/html-motion').glob('*.nut')))

    def test_strict_success_inherits_and_reruns_gate_on_rebuild(self):
        source=self.source()
        code,first=cli('motion','html-render','--project',self.root,'--source-asset-id',source,'--asset-id','first','--layout-check','strict')
        self.assertEqual(code,0,first);self.assertTrue(first['data']['asset']['html_motion']['layout_evidence']['quality_passed'])
        code,second=cli('motion','html-render','--project',self.root,'--from-asset-id','first','--asset-id','second')
        self.assertEqual(code,0,second);self.assertEqual(second['data']['asset']['html_motion']['layout_check'],'strict')
        self.assertNotEqual(first['data']['layout_report'],second['data']['layout_report'])

    def test_dry_run_has_no_browser_or_report(self):
        source=self.source();code,result=cli('motion','html-quality','--project',self.root,'--source-asset-id',source,'--dry-run')
        self.assertEqual(code,0,result);self.assertEqual(result['status'],'planned')
        self.assertFalse(list((self.root/'validation').glob('html-quality*')))

    def test_cancellation_preserves_read_only_failure_evidence(self):
        source=self.source();marker=self.root/'cancel';marker.write_text('cancel')
        report,result=self.quality(source,'--cancel-file',marker,expected=8)
        self.assertFalse(report['validation_complete']);self.assertEqual(report['status'],'failed')


if __name__=='__main__':unittest.main()
