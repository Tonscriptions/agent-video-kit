from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import threading
import unittest
import zlib

from ai_ad_editor import html_motion as html, html_template as template
from ai_ad_editor.errors import AppError
from ai_ad_editor.media import ffmpeg_path
from ai_ad_editor.project import create_project, load_project
from ai_ad_editor.policy import audit_local_tree
from ai_ad_editor.utils import atomic_write_json
from test_html_motion import cli, spec


def png_bytes(color, width=8, height=8):
    def chunk(kind, value):
        return struct.pack('>I',len(value))+kind+value+struct.pack('>I',zlib.crc32(kind+value)&0xffffffff)
    pixels=(b'\0'+bytes(color)*width)*height
    return (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,6,0,0,0))+
            chunk(b'IDAT',zlib.compress(pixels))+chunk(b'IEND',b''))


class TemplateContractTests(unittest.TestCase):
    def reject(self, value):
        with self.assertRaises(AppError) as caught:template.merge_overrides(patch=value)
        self.assertEqual(caught.exception.code,'HTML_OVERRIDE_INVALID')

    def test_units_and_literal_empty_text_are_retained(self):
        result=template.merge_overrides(patch={'variables':{'--size':' 24px ','--ratio':'50%'},
            'texts':[{'at':'#title','value':''},{'at':'.tag','n':2,'value':'<em>literal</em>\n下一行'}]})
        self.assertEqual(result['variables'],{'--size':'24px','--ratio':'50%'})
        self.assertEqual(next(x for x in result['texts'] if x['at']=='#title')['value'],'')

    def test_partial_patch_inherits_and_null_restores_one_target(self):
        previous={'variables':{'--a':'red','--b':'12em'},'texts':[{'at':'.label','value':'all'},{'at':'.label','n':2,'value':'second'}],
            'images':[{'at':'#img','kind':'img','asset_id':'logo'}]}
        saved=copy.deepcopy(previous)
        result=template.merge_overrides(previous,{'variables':{'--a':None},'texts':[{'at':'.label','n':2,'value':None}],
            'images':[{'at':'#img','kind':'img','asset_id':None}]})
        self.assertEqual(result,{'variables':{'--b':'12em'},'texts':[{'at':'.label','value':'all'}],'images':[]})
        self.assertEqual(previous,saved)

    def test_duplicate_target_is_not_silently_last_write_wins(self):
        self.reject({'texts':[{'at':'#title','value':'a'},{'at':'#title','value':'b'}]})

    def test_negative_zero_boolean_and_null_match_numbers_rejected(self):
        for value in (0,-1,True,None,1.5):
            with self.subTest(value=value):self.reject({'texts':[{'at':'.x','n':value,'value':'a'}]})

    def test_css_numbers_require_explicit_units_as_strings(self):
        self.reject({'variables':{'--size':24}})

    def test_network_variables_and_raw_styles_are_rejected(self):
        for value in ({'variables':{'--image':'URL("https://example.invalid/x")'}},
                      {'texts':[{'at':'#x','value':'ok','style':{'color':'red'}}]}, {'script':'alert(1)'}):
            with self.subTest(value=value):self.reject(value)

    def test_invalid_variable_name_and_empty_selector_rejected(self):
        self.reject({'variables':{'color':'red'}})
        self.reject({'texts':[{'at':'','value':'x'}]})

    def test_merged_byte_budget_includes_inherited_changes(self):
        previous={'texts':[{'at':'#a'+str(i),'value':'x'*7000} for i in range(8)]}
        with self.assertRaises(AppError):
            template.merge_overrides(previous,{'texts':[{'at':'#extra','value':'x'*10000}]})
        with self.assertRaises(AppError):
            template.merge_overrides(previous,{'texts':[{'at':'#extra','value':'x'*7000},{'at':'#last','value':'x'*7000}]})

    def test_duplicate_json_keys_rejected_before_browser(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);path=root/'changes.json'
            path.write_text('{"variables":{"--size":"8px","--size":"9px"}}',encoding='utf-8')
            with self.assertRaises(AppError):template.read_patch(root,str(path))

    def test_policy_separates_typed_css_and_words_from_real_addresses(self):
        report={'engine':html.ENGINE,'worker':{'template_controls':{'texts':[{'at':'p:nth-of-type(2)','value':'CTA: BUY'}]}}}
        recipe={'assets':[{'html_motion':{'engine':html.ENGINE,'template_overrides':{
            'texts':[{'at':'p:first-child','value':'Offer: today'}],'variables':{'--words':'Offer: today'}}}}]}
        cases=[(report,True),(recipe,True),
            ({**report,'uri':'unknown:resource'},False),
            ({**report,'engine':'another-engine'},False),
            ({'engine':html.ENGINE,'worker':{'template_controls':{'texts':[{'at':'#x','value':'https:remote'}]}}},False),
            ({'engine':html.ENGINE,'worker':{'template_controls':{'texts':[{'at':'#x','value':'custom://host/path'}]}}},False),
            ({'engine':html.ENGINE,'worker':{'template_controls':{'texts':[{'at':'#x','value':'https://example.invalid/x'}]}}},False),
            ({'engine':html.ENGINE,'worker':{'template_controls':{'texts':[{'at':'#x','value':'api.openai.com'}]}}},False)]
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for value,expected in cases:
                with self.subTest(value=value):
                    atomic_write_json(root/'record.json',value)
                    self.assertEqual(audit_local_tree(root)['ok'],expected)

    def test_undeclared_or_changed_image_never_enters_render_bundle(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);image=root/'logo.png';image.write_bytes(png_bytes((255,0,0,255)))
            changes=template.merge_overrides(patch={'images':[{'at':'#logo','kind':'img','asset_id':'logo'}]})
            with self.assertRaises(AppError):template.attach_resources(root,{'assets':[]},{'files':[],'data':{}},changes)
            asset={'id':'logo','kind':'image','uri':'logo.png','sha256':html.digest(image.read_bytes()),'rights_ref':'logo'}
            image.write_bytes(png_bytes((0,0,255,255)))
            with self.assertRaises(AppError):template.attach_resources(root,{'assets':[asset]},{'files':[],'data':{}},changes)


@unittest.skipUnless(os.environ.get('AI_AD_EDITOR_TEST_HTML_RUNTIME'),'explicit existing native HTML toolchain not configured')
class TemplateNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime=html.prepare_runtime(Path.cwd(),json.loads(Path(os.environ['AI_AD_EDITOR_TEST_HTML_RUNTIME']).read_text(encoding='utf-8')))

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='html-template-native-');self.addCleanup(self.temp.cleanup)
        self.root,_=create_project(Path(self.temp.name)/'project')
        atomic_write_json(self.root/'config/html-motion-runtime.json',self.runtime)
        self.source=Path(self.temp.name)/'source';self.source.mkdir()
        for name,color in [('red',(255,0,0,255)),('blue',(0,0,255,255))]:
            image=self.source/(name+'.png');image.write_bytes(png_bytes(color))
            code,result=cli('media','ingest','--project',self.root,'--input',image,'--asset-id',name)
            self.assertEqual(code,0,result)
        page='''<!doctype html><style>:root{--accent:#ff0000;--box-size:16px;--title-font:"Arial",sans-serif;--label:"Words"}
          *{margin:0}body{background:transparent}#box{position:absolute;top:8px;width:var(--box-size);height:12px;background:var(--accent)}
          #logo{position:absolute;left:56px;top:8px;width:8px;height:8px}p{position:absolute;top:32px;font:10px Arial;color:white}
          #mixed{top:48px}</style><div id="box"></div><img id="logo" src="red.png"><p id="title">OLD<br>SECOND</p>
          <p id="mixed">Keep <em>INLINE</em></p><script>window.film={frame(t){box.style.left=(8+Math.round(t*4))+"px";
          title.firstChild.data="OLD "+Math.round(t*4)}};</script>'''
        (self.source/'index.html').write_text(page,encoding='utf-8')
        atomic_write_json(self.source/'manifest.json',spec(resources=[{'path':'red.png','asset_id':'red'}]))
        code,result=cli('motion','html-source','--project',self.root,'--input',self.source/'manifest.json','--asset-id','source')
        self.assertEqual(code,0,result)
        self.patch=self.source/'changes.json'
        atomic_write_json(self.patch,{'variables':{'--accent':'#00ff00','--box-size':'24px'},
            'texts':[{'at':'#title','value':'NEW\nLINE'},{'at':'#mixed','value':'Changed '}],
            'images':[{'at':'#logo','kind':'img','asset_id':'blue'}]})

    def call(self, action='html-render', asset='changed', *extra):
        argv=['motion',action,'--project',self.root,'--source-asset-id','source']
        if action=='html-render':argv+=['--asset-id',asset]
        return cli(*argv,*extra)

    def report(self,result):
        path=result.get('data',{}).get('report') or result['errors'][0]['path']
        report=json.loads(Path(path).read_text(encoding='utf-8'))
        self.assertTrue(report['cleanup']['all_children_reaped'],report)
        self.assertEqual(report['cleanup']['active_after_cleanup'],[])
        return report

    def rgba(self, asset):
        root,project=load_project(self.root);a=next(x for x in project['assets'] if x['id']==asset)
        result=subprocess.run([ffmpeg_path(),'-v','error','-i',str(root/a['uri']),'-f','rawvideo','-pix_fmt','rgba','-threads','1','pipe:1'],
                              stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
        return result.stdout

    def test_actual_inspection_types_units_and_read_only_project(self):
        before=(self.root/'project.json').read_bytes();ledger=(self.root/'rights-ledger.json').read_bytes()
        code,result=self.call('html-controls','unused','--frame-index','2','--overrides',self.patch)
        self.assertEqual(code,0,result);report=self.report(result)
        fields={v['name']:v for v in report['controls']['vars']}
        self.assertEqual(fields['--box-size']['field'],{'kind':'number','value':16,'unit':'px'})
        self.assertEqual(fields['--accent']['field']['kind'],'color')
        self.assertTrue(fields['--title-font']['font'])
        effective=report['effective_controls']
        self.assertEqual(next(t['value'] for t in effective['texts'] if t['at']=='#title'),'NEW\nLINE')
        self.assertEqual(next(t['value'] for t in effective['texts'] if t['at']=='#mixed'),'Changed ')
        self.assertTrue(any(t['value']=='INLINE' for t in effective['texts']))
        self.assertEqual(report['worker']['cleanup']['pages_closed'],2)
        self.assertEqual((self.root/'project.json').read_bytes(),before)
        self.assertEqual((self.root/'rights-ledger.json').read_bytes(),ledger)

    def test_actual_color_size_image_and_clock_against_independent_pixels(self):
        code,result=self.call('html-render','changed','--overrides',self.patch)
        self.assertEqual(code,0,result);report=self.report(result);rgba=self.rgba('changed')
        self.assertTrue(report['encoded_clock']['all_frames_exact'])
        self.assertEqual(report['worker']['cleanup']['pages_closed'],3)
        self.assertEqual(len(rgba),4*96*64*4)
        for frame in range(4):
            for y in range(8,20):
                for x in range(0,40):
                    expected=bytes((0,255,0,255)) if 8+frame<=x<32+frame else bytes(4)
                    offset=((frame*64+y)*96+x)*4
                    self.assertEqual(rgba[offset:offset+4],expected,(frame,x,y))
            for y in range(8,16):
                for x in range(56,64):
                    offset=((frame*64+y)*96+x)*4
                    self.assertEqual(rgba[offset:offset+4],bytes((0,0,255,255)))
        root,project=load_project(self.root);asset=next(a for a in project['assets'] if a['id']=='changed')
        record=next(r for r in json.loads((root/'rights-ledger.json').read_text(encoding='utf-8'))['records'] if r['asset_id']=='changed')
        self.assertEqual(asset['html_motion']['template_overrides']['images'][0]['asset_id'],'blue')
        self.assertIn('blue',record['derived_from']);self.assertEqual(record['verification_status'],'unverified')

    def test_actual_inherit_then_null_restores_complete_original_animation(self):
        self.assertEqual(self.call('html-render','base')[0],0)
        self.assertEqual(self.call('html-render','changed','--overrides',self.patch)[0],0)
        code,result=cli('motion','html-render','--project',self.root,'--from-asset-id','changed','--asset-id','same')
        self.assertEqual(code,0,result);self.report(result)
        self.assertEqual(self.rgba('same'),self.rgba('changed'))
        atomic_write_json(self.patch,{'variables':{'--accent':None,'--box-size':None},
            'texts':[{'at':'#title','value':None},{'at':'#mixed','value':None}],
            'images':[{'at':'#logo','kind':'img','asset_id':None}]})
        code,result=cli('motion','html-render','--project',self.root,'--from-asset-id','changed','--asset-id','restored','--overrides',self.patch)
        self.assertEqual(code,0,result);self.report(result)
        self.assertEqual(self.rgba('restored'),self.rgba('base'))

    def test_missing_selector_fails_rolls_back_and_closes_tabs(self):
        atomic_write_json(self.patch,{'texts':[{'at':'#absent','value':'No'}]})
        before=(self.root/'project.json').read_bytes();ledger=(self.root/'rights-ledger.json').read_bytes()
        code,result=self.call('html-render','changed','--overrides',self.patch)
        self.assertNotEqual(code,0,result);self.assertEqual(result['errors'][0]['code'],'HTML_OVERRIDE_TARGET_MISSING')
        self.report(result)
        self.assertEqual((self.root/'project.json').read_bytes(),before)
        self.assertEqual((self.root/'rights-ledger.json').read_bytes(),ledger)
        self.assertFalse(list((self.root/'assets').rglob('*.nut')))
        # A Playwright "page.evaluate:" diagnostic is text, not a URI scheme.
        # Keep its traceback while preventing a false remote-reference report.
        code,audit=cli('policy','audit','--project',self.root)
        self.assertEqual(code,0,audit)

    def test_unknown_variable_and_wrong_image_kind_fail_explicitly(self):
        for patch,expected in [({'variables':{'--typo':'red'}},'HTML_OVERRIDE_VARIABLE_MISSING'),
            ({'images':[{'at':'#box','kind':'img','asset_id':'blue'}]},'HTML_OVERRIDE_IMAGE_KIND')]:
            with self.subTest(expected=expected):
                atomic_write_json(self.patch,patch)
                code,result=self.call('html-controls','unused','--overrides',self.patch)
                self.assertNotEqual(code,0,result);self.assertEqual(result['errors'][0]['code'],expected)
                self.report(result)

    def test_actual_background_image_and_one_based_text_target(self):
        page=(self.source/'index.html').read_text(encoding='utf-8').replace('<script>',
            '<div id="poster" style="position:absolute;left:72px;top:8px;width:8px;height:8px;background-image:url(red.png)"></div>'
            '<span class="tag">FIRST</span><span class="tag">OLD SECOND</span><script>')
        (self.source/'index.html').write_text(page,encoding='utf-8')
        code,result=cli('motion','html-source','--project',self.root,'--input',self.source/'manifest.json','--asset-id','source2')
        self.assertEqual(code,0,result)
        literal='<em>literal</em>'
        atomic_write_json(self.patch,{'texts':[{'at':'.tag','n':2,'value':literal}],
            'images':[{'at':'#poster','kind':'bg','asset_id':'blue'}]})
        code,result=cli('motion','html-render','--project',self.root,'--source-asset-id','source2','--asset-id','changed','--overrides',self.patch)
        self.assertEqual(code,0,result);report=self.report(result)
        texts=report['worker']['effective_template_controls']['texts']
        self.assertTrue(any(x['value']=='FIRST' for x in texts));self.assertTrue(any(x['value']==literal for x in texts))
        self.assertFalse(any(x['value']=='OLD SECOND' for x in texts))
        image=next(x for x in report['worker']['effective_template_controls']['images'] if x['at']=='#poster')
        self.assertTrue(image['src'].startswith('local://html-source/__template_images/'))
        rgba=self.rgba('changed')
        for frame in range(4):
            for y in range(8,16):
                for x in range(72,80):
                    offset=((frame*64+y)*96+x)*4
                    self.assertEqual(rgba[offset:offset+4],bytes((0,0,255,255)))
        code,audit=cli('policy','audit','--project',self.root)
        self.assertEqual(code,0,audit)

    def test_invalid_selector_and_complex_text_fail_without_silent_skip(self):
        for selector,expected in [('[','HTML_OVERRIDE_SELECTOR_INVALID'),('body','HTML_OVERRIDE_TEXT_UNSUPPORTED')]:
            with self.subTest(selector=selector):
                atomic_write_json(self.patch,{'texts':[{'at':selector,'value':'Change'}]})
                code,result=self.call('html-controls','unused','--overrides',self.patch)
                self.assertNotEqual(code,0,result);self.assertEqual(result['errors'][0]['code'],expected)
                self.report(result)

    def test_controls_dry_run_starts_no_browser_and_has_no_asset(self):
        before=(self.root/'project.json').read_bytes()
        code,result=self.call('html-controls','unused','--dry-run','--overrides',self.patch)
        self.assertEqual(code,0,result);self.assertEqual(result['status'],'planned')
        self.assertFalse(result['data']['plan']['all_frames_checked_in_two_fresh_context_orders'])
        self.assertEqual((self.root/'project.json').read_bytes(),before)
        self.assertFalse(list((self.root/'validation').glob('html-controls*')))

    def test_cancelled_controls_reaps_native_browser_job(self):
        cancel=self.source/'cancel';timer=threading.Timer(.2,lambda:cancel.write_text('cancel',encoding='utf-8'))
        timer.start();self.addCleanup(timer.join)
        code,result=self.call('html-controls','unused','--cancel-file',cancel)
        self.assertNotEqual(code,0,result)
        report=self.report(result);self.assertEqual(report['status'],'failed')


if __name__=='__main__':unittest.main()
