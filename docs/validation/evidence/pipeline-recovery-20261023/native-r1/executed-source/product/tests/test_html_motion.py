from __future__ import annotations

import contextlib
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from unittest import mock
import zipfile

from ai_ad_editor import html_motion as html
from ai_ad_editor.cli import main
from ai_ad_editor.errors import AppError
from ai_ad_editor.media import ffmpeg_path
from ai_ad_editor.project import create_project, load_project, save_project, project_transaction
from ai_ad_editor.utils import atomic_write_json

TPS = 90000


def spec(**patch):
    return {'entry':'index.html','width':96,'height':64,'fps':{'num':4,'den':1},
            'duration_tick':TPS,'files':['index.html'],'variables':[],**patch}


def cli(*args):
    out=io.StringIO()
    with contextlib.redirect_stdout(out):
        code=main([str(a) for a in args])
    return code,json.loads(out.getvalue())


class HTMLSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='html-unit-')
        self.addCleanup(self.temp.cleanup)
        self.root,self.project=create_project(Path(self.temp.name)/'project')
        self.source=Path(self.temp.name)/'source';self.source.mkdir()
        self.page=self.source/'index.html';self.page.write_text('<script>window.film={frame(){}}</script>',encoding='utf-8')
        self.input=self.source/'manifest.json';atomic_write_json(self.input,spec())

    def reject(self, code, fn, *args):
        with self.assertRaises(AppError) as caught:
            fn(*args)
        self.assertEqual(caught.exception.code,code)

    def bundle(self, value=None):
        atomic_write_json(self.input,value or spec())
        return html.build_source(self.root,self.project,self.input)

    def registered(self):
        code,result=cli('motion','html-source','--project',self.root,'--input',self.input,'--asset-id','source')
        self.assertEqual(code,0,result)
        self.project=load_project(self.root)[1]
        return self.project['assets'][0]

    def test_source_zip_is_reproducible_and_retains_code(self):
        a,plan=self.bundle();b,_=self.bundle()
        self.assertEqual(a,b)
        with zipfile.ZipFile(io.BytesIO(a)) as archive:
            self.assertEqual(archive.read('index.html'),self.page.read_bytes())
            self.assertNotIn('asset_id',archive.read('motion.json').decode())
        self.assertEqual(plan['frame_count'],4)

    def test_dry_run_no_asset_or_bundle(self):
        before=(self.root/'project.json').read_bytes()
        code,result=cli('motion','html-source','--project',self.root,'--input',self.input,'--asset-id','source','--dry-run')
        self.assertEqual(code,0,result)
        self.assertEqual(result['status'],'planned')
        self.assertEqual((self.root/'project.json').read_bytes(),before)
        self.assertFalse(list((self.root/'assets').rglob('*.zip')))

    def test_source_idempotency_replays_without_new_asset(self):
        argv=('motion','html-source','--project',self.root,'--input',self.input,'--asset-id','source','--idempotency-key','one')
        first=cli(*argv);second=cli(*argv)
        self.assertEqual(first[0],0,first)
        self.assertEqual(second[0],0,second)
        self.assertEqual(len(load_project(self.root)[1]['assets']),1)
        self.assertEqual(second[1]['warnings'][-1]['code'],'IDEMPOTENT_REPLAY')

    def test_inspect_hash_and_page_bytes(self):
        asset=self.registered()
        observed=html.inspect_source(self.root,self.project,'source')
        self.assertEqual(observed['data']['index.html'],self.page.read_bytes())
        self.assertEqual(observed['asset']['sha256'],asset['sha256'])

    def test_mutated_zip_rejected(self):
        asset=self.registered();path=self.root/asset['uri']
        path.write_bytes(path.read_bytes()+b'changed')
        self.reject('HTML_SOURCE_CHANGED',html.inspect_source,self.root,self.project,'source')

    def test_archive_extra_member_rejected_even_with_updated_outer_hash(self):
        asset=self.registered();path=self.root/asset['uri']
        with zipfile.ZipFile(path,'a') as archive:archive.writestr('extra.js','alert(1)')
        asset['sha256']=html.digest(path.read_bytes())
        self.reject('HTML_SOURCE_INVALID',html.inspect_source,self.root,self.project,'source')

    def test_source_rights_default_unverified(self):
        self.registered()
        ledger=json.loads((self.root/'rights-ledger.json').read_text(encoding='utf-8'))
        self.assertEqual(ledger['records'][0]['verification_status'],'unverified')
        self.assertEqual(ledger['records'][0]['permitted_uses'],['internal'])

    def test_traversal_rejected(self):
        self.reject('HTML_RESOURCE_INVALID',self.bundle,spec(files=['../private.js']))

    def test_case_alias_rejected(self):
        (self.source/'index.HTML').write_bytes(self.page.read_bytes())
        self.reject('HTML_RESOURCE_INVALID',self.bundle,spec(files=['index.html','index.HTML']))

    def test_absolute_network_reference_rejected(self):
        self.reject('HTML_RESOURCE_INVALID',self.bundle,spec(entry='https://example.invalid/index.html'))

    def test_unlisted_entry_rejected(self):
        self.reject('HTML_RESOURCE_INVALID',self.bundle,spec(entry='other.html'))

    def test_unregistered_image_rejected(self):
        self.reject('HTML_RESOURCE_INVALID',self.bundle,spec(resources=[{'path':'image.png','asset_id':'missing'}]))

    def test_binary_files_require_registered_resource(self):
        self.reject('HTML_RESOURCE_INVALID',self.bundle,spec(files=['unlicensed.ttf']))

    def test_reserved_device_path_rejected(self):
        self.reject('HTML_RESOURCE_INVALID',html._relative,'aux.js')

    def test_linked_directory_rejected(self):
        linked=self.source/'linked';target=self.source/'target';target.mkdir()
        (target/'script.js').write_text('export const a=1',encoding='utf-8')
        # Windows directory junction requires no developer-mode symlink grant.
        subprocess.run(['cmd.exe','/c','mklink','/J',str(linked),str(target)],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.addCleanup(lambda:os.rmdir(linked) if linked.exists() else None)
        self.reject('HTML_RESOURCE_INVALID',self.bundle,spec(files=['index.html','linked/script.js']))

    def test_fractional_frame_duration_rejected(self):
        self.reject('HTML_FRAME_BUDGET',html.validate_spec,spec(duration_tick=TPS-1),TPS)

    def test_boolean_dimension_rejected(self):
        self.reject('HTML_MANIFEST_INVALID',html.validate_spec,spec(width=True),TPS)

    def test_excessive_frame_work_rejected(self):
        self.reject('HTML_FRAME_BUDGET',html.validate_spec,spec(width=4096,height=4096,duration_tick=TPS*100),TPS)

    def test_unknown_manifest_field_rejected(self):
        self.reject('HTML_MANIFEST_INVALID',html.validate_spec,spec(network_allow=['anything']),TPS)

    def test_typed_parameters_and_defaults(self):
        value=spec(variables=[{'name':'brand','type':'color','default':'#123456'},
            {'name':'size','type':'integer','min':1,'max':20,'required':True}])
        validated,_=html.validate_spec(value,TPS)
        self.assertEqual(html.parameters(validated,{'size':3}),{'brand':'#123456','size':3})

    def test_unknown_parameter_rejected(self):
        self.reject('HTML_VARIABLE_INVALID',html.parameters,spec(),{'typo':1})

    def test_boolean_is_not_integer_parameter(self):
        value=spec(variables=[{'name':'n','type':'integer'}])
        self.reject('HTML_VARIABLE_INVALID',html.parameters,value,{'n':True})

    def test_nan_parameter_rejected(self):
        value=spec(variables=[{'name':'n','type':'number'}])
        self.reject('HTML_VARIABLE_INVALID',html.parameters,value,{'n':float('nan')})

    def test_asset_variable_requires_source_resource_version(self):
        self.reject('HTML_VARIABLE_INVALID',html.validate_spec,spec(variables=[{'name':'image','type':'asset'}]),TPS)

    def test_missing_required_parameter_rejected(self):
        self.reject('HTML_VARIABLE_INVALID',html.parameters,spec(variables=[{'name':'text','type':'string','required':True}]),{})

    def test_parameter_names_cannot_collide_with_portable_asset_references(self):
        self.reject('HTML_VARIABLE_INVALID',html.validate_spec,spec(variables=[{'name':'source_asset_id','type':'string'}]),TPS)

    def test_mutable_browser_diagnostic_does_not_hide_distribution_changes(self):
        folder=Path(self.temp.name)/'browser';folder.mkdir()
        (folder/'engine.dll').write_bytes(b'fixed executable input')
        (folder/'debug.log').write_text('first run',encoding='utf-8')
        first=html._tree(folder,browser=True)
        (folder/'debug.log').write_text('another run and timeout diagnostic',encoding='utf-8')
        self.assertEqual(first,html._tree(folder,browser=True))
        (folder/'engine.dll').write_bytes(b'changed executable input')
        self.assertNotEqual(first,html._tree(folder,browser=True))

    def test_runtime_registration_participates_in_project_metadata_rollback(self):
        path=self.root/'config/html-motion-runtime.json'
        atomic_write_json(path,{'version':'original'})
        original=path.read_bytes()
        with self.assertRaisesRegex(RuntimeError,'injected'):
            with project_transaction(self.root,command='motion.html-register'):
                atomic_write_json(path,{'version':'changed'})
                raise RuntimeError('injected')
        self.assertEqual(path.read_bytes(),original)


@unittest.skipUnless(os.environ.get('AI_AD_EDITOR_TEST_HTML_RUNTIME'), 'explicit existing native HTML toolchain not configured')
    def preflight_failure(self, *, elapsed=5, cancelled=False, strict=False, dry_run=False):
        self.registered()
        original={name:(self.root/name).read_bytes() for name in ('project.json','rights-ledger.json')}
        clock=[0.0]; flag=self.root/'cancel'
        def prepared(*args):
            clock[0]=0.0 if strict else elapsed
            if cancelled:flag.write_text('explicit cancellation',encoding='utf8')
            return {'layout_check':'strict' if strict else 'off'}
        def inspected(root,plan,path,**kwargs):
            clock[0]=elapsed
            value={'status':'succeeded','test_double':True}
            atomic_write_json(path,value)
            return value
        options=['--timeout-seconds','4']
        if cancelled:options+=['--cancel-file',str(flag)]
        if dry_run:options+=['--dry-run']
        with mock.patch.object(html,'prepare_render',side_effect=prepared), \
             mock.patch.object(html,'public_plan',return_value={'source_asset_id':'source'}), \
             mock.patch.object(html,'inspect_layout',side_effect=inspected), \
             mock.patch.object(html,'render_frames',side_effect=AssertionError('render Job must not start')) as render, \
             mock.patch('ai_ad_editor.cli.create_snapshot') as snapshot, \
             mock.patch('time.monotonic',side_effect=lambda:clock[0]):
            code,result=cli('motion','html-render','--project',self.root,
                '--source-asset-id','source','--asset-id','rendered',*options)
        render.assert_not_called();snapshot.assert_not_called()
        self.assertTrue(all((self.root/name).read_bytes()==data for name,data in original.items()))
        if dry_run:
            self.assertEqual(code,0,result)
            self.assertEqual(result['status'],'planned')
            self.assertFalse(list((self.root/'validation').glob('html-*.json')))
            return None
        error=result['errors'][0]
        self.assertEqual(code,8 if cancelled else 6,result)
        self.assertEqual(error['code'],'CANCELLED' if cancelled else 'HTML_TIMEOUT')
        self.assertTrue(error['path'],result)
        report=json.loads(Path(error['path']).read_text('utf8'))
        self.assertEqual(report['phase'],'before-render-job')
        self.assertFalse(report['render_processes_started'])
        self.assertEqual(report['error'],error)
        self.assertFalse(report['cleanup']['native_job'])
        self.assertTrue(report['cleanup']['not_started'])
        self.assertTrue(report['cleanup']['all_children_reaped'])
        self.assertEqual(report['cleanup']['seen_pids'],[])
        self.assertEqual(report['cleanup']['active_after_cleanup'],[])
        return report

    def test_preparation_deadline_persists_truthful_zero_process_report(self):
        report=self.preflight_failure()
        self.assertIsNone(report['layout_report'])

    def test_preparation_cancel_wins_when_total_deadline_also_expires(self):
        self.preflight_failure(cancelled=True)

    def test_preparation_cancel_before_deadline_persists_report(self):
        self.preflight_failure(elapsed=.25,cancelled=True)

    def test_completed_layout_consumes_same_total_render_deadline(self):
        report=self.preflight_failure(strict=True)
        self.assertEqual(json.loads(Path(report['layout_report']).read_text('utf8')),
                         {'status':'succeeded','test_double':True})

    def test_preparation_dry_run_remains_readonly_without_failure_report(self):
        self.preflight_failure(dry_run=True)


class HTMLNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.configuration=json.loads(Path(os.environ['AI_AD_EDITOR_TEST_HTML_RUNTIME']).read_text(encoding='utf-8'))
        cls.runtime=html.prepare_runtime(Path.cwd(),cls.configuration)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='html-native-')
        self.addCleanup(self.temp.cleanup)
        self.root,self.project=create_project(Path(self.temp.name)/'project')
        atomic_write_json(self.root/'config/html-motion-runtime.json',self.runtime)
        self.source=Path(self.temp.name)/'source';self.source.mkdir()

    def source_asset(self, script='', manifest=None):
        page='''<!doctype html><html><head><style>*{margin:0}body{background:transparent}</style></head><body>
        <canvas id="canvas" width="96" height="64"></canvas><script>
        const ctx=canvas.getContext('2d');window.film={frame(t,p){ctx.clearRect(0,0,96,64);
          ctx.fillStyle=p.color;ctx.fillRect(8+Math.round(t*8),12,12,10);}};
        '''+script+'</script></body></html>'
        (self.source/'index.html').write_text(page,encoding='utf-8')
        value=manifest or spec(variables=[{'name':'color','type':'color','default':'#ff0000'}])
        atomic_write_json(self.source/'manifest.json',value)
        code,result=cli('motion','html-source','--project',self.root,'--input',self.source/'manifest.json','--asset-id','source')
        self.assertEqual(code,0,result)

    def render(self,*extra):
        return cli('motion','html-render','--project',self.root,'--source-asset-id','source','--asset-id','rendered',*extra)

    def report(self,result):
        path=result.get('data',{}).get('report') or result['errors'][0]['path']
        report=json.loads(Path(path).read_text(encoding='utf-8'))
        self.assertTrue(report['cleanup']['all_children_reaped'],report)
        self.assertEqual(report['cleanup']['active_after_cleanup'],[])
        return report

    def test_actual_alpha_frames_match_independent_rectangles_and_two_orders(self):
        self.source_asset()
        code,result=self.render()
        self.assertEqual(code,0,result)
        report=self.report(result)
        self.assertEqual(report['worker']['cleanup']['pages_closed'],3)
        self.assertTrue(report['worker']['all_frame_orders_equal'])
        self.assertGreaterEqual(len(report['cleanup']['seen_pids']),3)
        self.assertEqual(result['data']['asset']['probe']['duration_tick'],TPS)
        video=self.root/result['data']['asset']['uri']
        raw=subprocess.check_output([ffmpeg_path(),'-v','error','-i',str(video),'-f','rawvideo','-pix_fmt','rgba','pipe:1'])
        expected=bytearray(96*64*4*4)
        for frame in range(4):
            for y in range(12,22):
                for x in range(8+frame*2,20+frame*2):
                    at=(frame*96*64+y*96+x)*4;expected[at:at+4]=bytes([255,0,0,255])
        self.assertEqual(raw,bytes(expected))

    def test_dry_run_does_not_start_browser(self):
        self.source_asset()
        with mock.patch('ai_ad_editor.html_motion.BrowserProcessJob',side_effect=AssertionError('browser started')):
            code,result=self.render('--dry-run')
        self.assertEqual(code,0,result)
        self.assertFalse(list((self.root/'assets').rglob('*.nut')))

    def test_parameter_rebuild_retains_source_and_changes_actual_pixels(self):
        self.source_asset()
        code,first=self.render();self.assertEqual(code,0,first)
        params=self.source/'params.json';atomic_write_json(params,{'color':'#00ff00'})
        code,second=cli('motion','html-render','--project',self.root,'--from-asset-id','rendered','--params',params,'--asset-id','green')
        self.assertEqual(code,0,second)
        self.assertEqual(second['data']['asset']['html_motion']['source_asset_id'],'source')
        self.assertNotEqual(first['data']['asset']['sha256'],second['data']['asset']['sha256'])
        self.report(second)

    def test_stateful_page_rejected_and_project_rolled_back(self):
        self.source_asset('let calls=0;window.film.frame=()=>{ctx.clearRect(0,0,96,64);ctx.fillStyle="red";ctx.fillRect(++calls,12,12,10)};')
        before=(self.root/'project.json').read_bytes()
        code,result=self.render()
        self.assertEqual(code,6,result)
        self.assertEqual(result['errors'][0]['code'],'HTML_FRAME_NONDETERMINISTIC')
        self.assertEqual((self.root/'project.json').read_bytes(),before)
        self.assertFalse(list((self.root/'assets').rglob('*.nut')))
        self.report(result)

    def test_external_fetch_is_rejected_and_browser_closed(self):
        self.source_asset("fetch('https://example.invalid/no-network').catch(()=>{});")
        code,result=self.render()
        self.assertEqual(code,6,result)
        self.assertEqual(result['errors'][0]['code'],'HTML_PAGE_ERROR')
        self.report(result)

    def test_websocket_is_rejected_even_if_page_catches_exception(self):
        self.source_asset("try{new WebSocket('ws://127.0.0.1:9')}catch{}")
        code,result=self.render()
        self.assertEqual(code,6,result)
        self.assertEqual(result['errors'][0]['code'],'HTML_FEATURE_DENIED')
        self.report(result)

    def test_infinite_frame_timeout_kills_all_native_descendants(self):
        self.source_asset('window.film.frame=()=>{while(true){}};')
        before=(self.root/'project.json').read_bytes()
        code,result=self.render('--timeout-seconds','4')
        self.assertEqual(code,6,result)
        self.assertEqual(result['errors'][0]['code'],'HTML_TIMEOUT')
        self.assertEqual((self.root/'project.json').read_bytes(),before)
        report=self.report(result)
        if report['cleanup'].get('not_started'):
            self.assertEqual(report['phase'],'before-render-job')
            self.assertEqual(report['cleanup']['seen_pids'],[])
        else:
            self.assertGreaterEqual(len(report['cleanup']['seen_pids']),3)

    def test_infinite_frame_after_preparation_kills_actual_native_descendants(self):
        from ai_ad_editor.cli import build_parser
        self.source_asset('window.film.frame=()=>{while(true){}};')
        before=(self.root/'project.json').read_bytes()
        args=build_parser().parse_args(['motion','html-render','--project',str(self.root),
            '--source-asset-id','source','--asset-id','rendered','--timeout-seconds','10'])
        # The separate cold CLI test includes preparation in its four-second
        # total deadline. This test specifically requires a real running Job.
        plan=html.prepare_render(self.root,load_project(self.root)[1],args)
        with mock.patch.object(html,'prepare_render',return_value=plan):
            code,result=self.render('--timeout-seconds','10')
        self.assertEqual(code,6,result)
        self.assertEqual(result['errors'][0]['code'],'HTML_TIMEOUT')
        self.assertEqual((self.root/'project.json').read_bytes(),before)
        report=self.report(result)
        self.assertFalse(report['cleanup'].get('not_started',False))
        self.assertGreaterEqual(len(report['cleanup']['seen_pids']),3)

    def test_twelve_fps_retains_every_frame_after_native_timeline_composition(self):
        # Millisecond Matroska timestamps + existing upward CFR sampling used
        # to repeat preceding HTML frames at indices 2/5/8/11. NUT keeps the
        # rational input clock. Check output pixels, not only timestamps.
        value=spec(fps={'num':12,'den':1},variables=[{'name':'color','type':'color','default':'#ff0000'}])
        self.source_asset('window.film.frame=(t,p)=>{ctx.clearRect(0,0,96,64);ctx.fillStyle=p.color;ctx.fillRect(8+Math.round(t*12),12,12,10)};',value)
        project=load_project(self.root)[1]
        project['settings']['canvas'].update(width=96,height=64)
        project['settings']['timebase']['display_fps']={'num':12,'den':1}
        save_project(self.root,project)
        code,result=self.render('--apply','--track-id','track_video_1')
        self.assertEqual(code,0,result)
        self.assertTrue(self.report(result)['encoded_clock']['all_frames_exact'])
        output=self.root/'renders/timeline.mkv'
        code,result=cli('render','--project',self.root,'--output',output,'--container','mkv','--crf','0','--pixel-format','yuv444p')
        self.assertEqual(code,0,result)
        raw=subprocess.check_output([ffmpeg_path(),'-v','error','-i',str(output),'-an','-f','rawvideo','-pix_fmt','rgb24','pipe:1'])
        self.assertEqual(len(raw),12*96*64*3)
        for i in range(12):
            points=[]
            for y in range(64):
                for x in range(96):
                    at=(i*96*64+y*96+x)*3;r,g,b=raw[at:at+3]
                    if r>200 and g<20 and b<20:points.append((x,y))
            self.assertEqual(len(points),120,i)
            self.assertEqual(min(x for x,y in points),8+i,i)
            self.assertEqual(max(x for x,y in points),19+i,i)

    def test_cancel_after_page_open_kills_all_native_descendants(self):
        self.source_asset('window.film.frame=()=>{while(true){}};')
        flag=self.root/'cancel.flag'
        ready=threading.Event()
        def cancel():
            end=time.monotonic()+25
            while time.monotonic()<end:
                for path in (self.root/'validation').glob('html-motion-*.json'):
                    try:started=json.loads(path.read_text(encoding='utf-8')).get('worker_started')
                    except (OSError,ValueError):continue
                    if started:flag.touch();ready.set();return
                time.sleep(.05)
        thread=threading.Thread(target=cancel,daemon=True);thread.start()
        code,result=self.render('--cancel-file',flag,'--timeout-seconds','30')
        thread.join(timeout=1)
        self.assertTrue(ready.is_set(),'cancellation must occur after actual page open')
        self.assertEqual(code,8,result)
        self.assertEqual(result['errors'][0]['code'],'CANCELLED')
        self.report(result)


if __name__=='__main__':unittest.main()
