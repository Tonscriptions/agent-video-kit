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
from types import SimpleNamespace

from ai_ad_editor import html_components as components, html_motion as html
from ai_ad_editor.errors import AppError
from ai_ad_editor.html_template import merge_overrides
from ai_ad_editor.media import ffmpeg_path
from ai_ad_editor.project import create_project, load_project, save_project
from ai_ad_editor.schema_contract import make_validator
from ai_ad_editor.utils import atomic_write_json
from ai_ad_editor.validator import validate_project
from test_html_motion import cli, spec, TPS
from test_html_template import png_bytes


def field(id='headline', field_type='text', **patch):
    value = {'id': id, 'name': id, 'type': field_type, **({'var': '--size'} if field_type == 'var' else {'at': '#title'})}
    if field_type == 'image':
        value['kind'] = 'img'
    return {**value, **patch}


class ComponentContractTests(unittest.TestCase):
    def reject(self, fields):
        with self.assertRaises(AppError):
            components.validate_fields(fields)

    def test_stable_id_display_name_and_distinct_property_kinds(self):
        fields = [field(name='广告标题'), field('visible', 'boolean')]
        self.assertEqual(components.validate_fields(fields), fields)

    def test_duplicate_ids_names_and_same_type_targets_reject(self):
        for other in (field(name='other', at='#other'), field('other'), field('other', at='#other', name='headline')):
            with self.subTest(other=other):
                self.reject([field(), other])

    def test_selector_and_one_based_match_budget(self):
        for patch in ({'at': ''}, {'at': 'x'*513}, {'n': True}, {'n': 0}, {'n': 1025}, {'n': 1e20}, {'n': 1.5}):
            with self.subTest(patch=patch):
                self.reject([field(**patch)])
        self.assertEqual(components.validate_fields([field(n=1024)])[0]['n'], 1024)

    def test_variable_name_schema_and_units_reject_unsafe_extensions(self):
        for value in (field('v', 'var', var='--'), field(schema={'$ref': 'https://example.invalid/schema'}),
                      field('v', 'var', schema={'type': 'number'}, unit='bad'),
                      field('v', 'var', unit='px'), field(type=['text']), field(schema={'type': []})):
            with self.subTest(value=value):
                self.reject([value])

    def test_typed_number_range_enum_and_css_units(self):
        f = field('size', 'var', schema={'type': 'number', 'minimum': -20, 'maximum': -1}, unit='px', default=-12)
        components.validate_fields([f])
        self.assertEqual(components.validate_value(f, -10), -10)
        for value in (True, '12', 0, float('nan'), float('inf'), 10**400):
            with self.subTest(value=str(value)[:20]), self.assertRaises(AppError):
                components.validate_value(f, value)
        self.reject([field('v', 'var', schema={'type': 'integer', 'enum': [1, 1]})])
        self.reject([field('v', 'var', schema={'type': 'integer', 'enum': [True]})])

    def test_boolean_default_means_original_page_not_forced_show(self):
        self.reject([field('show', 'boolean', default=True)])
        self.reject([field('show', 'boolean', default=False)])
        self.assertEqual(components.validate_fields([field('show', 'boolean', default=None)])[0]['default'], None)

    def test_empty_text_zero_and_false_are_explicit_values(self):
        fields = [field(), field('size', 'var', schema={'type': 'number'}), field('show', 'boolean')]
        stored = [{'field_id': 'headline', 'value': ''}, {'field_id': 'size', 'value': 0}, {'field_id': 'show', 'value': False}]
        self.assertEqual(components.read_values(fields, stored), {'headline': '', 'size': 0, 'show': False})

    def test_only_asset_id_object_is_a_component_image_value(self):
        f = field('logo', 'image')
        for value in ('https://example.invalid/a.png', '../outside.png', {'uri': 'blue.png'}, {'asset_id': '../outside'}, {'asset_id': 'blue', 'uri': 'blue.png'}):
            with self.subTest(value=value), self.assertRaises(AppError):
                components.validate_value(f, value)
        self.assertEqual(components.validate_value(f, {'asset_id': 'blue'}), {'asset_id': 'blue'})

    def test_definition_and_saved_value_budgets_include_all_entries(self):
        self.reject([field(str(i), at='#a'+str(i)) for i in range(129)])
        self.reject([field(str(i), at='#a'+str(i), default='x'*7000) for i in range(10)])
        fields = [field(str(i), at='#a'+str(i)) for i in range(10)]
        with self.assertRaises(AppError):
            components.read_values(fields, [{'field_id': str(i), 'value': 'x'*7000} for i in range(10)])

    def test_no_unknown_duplicate_or_null_saved_values(self):
        for stored in ([{'field_id': 'other', 'value': 'x'}], [{'field_id': 'headline', 'value': None}],
                       [{'field_id': 'headline', 'value': 'a'}, {'field_id': 'headline', 'value': 'b'}]):
            with self.subTest(stored=stored), self.assertRaises(AppError):
                components.read_values([field()], stored)

    def test_rename_keeps_value_and_removed_field_requires_explicit_reset(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = {'asset': {'html_source': {'component_fields': [field()]}}}
            previous = {'component_fields': [field()], 'component_values': [{'field_id': 'headline', 'value': 'Saved'}]}
            args = SimpleNamespace(component_fields=str(root/'fields.json'), component_values=None, reset_components=False)
            atomic_write_json(root/'fields.json', [field(name='改名')])
            fields, values, enabled = components.configure(root, source, previous, args)
            self.assertEqual(fields[0]['name'], '改名'); self.assertEqual(values[0]['value'], 'Saved'); self.assertTrue(enabled)
            atomic_write_json(root/'fields.json', [])
            with self.assertRaises(AppError):
                components.configure(root, source, previous, args)
            args.component_values = str(root/'values.json')
            atomic_write_json(root/'values.json', {'headline': None})
            self.assertEqual(components.configure(root, source, previous, args)[1], [])

    def test_patch_unknown_and_duplicate_json_keys_reject(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); path = root/'values.json'
            source = {'asset': {'html_source': {'component_fields': [field()]}}}
            args = SimpleNamespace(component_values=str(path))
            for content in ('{"other":"x"}', '{"headline":"a","headline":"b"}', '{"headline":NaN}', '[]'):
                path.write_text(content, encoding='utf8')
                with self.subTest(content=content), self.assertRaises(AppError):
                    components.configure(root, source, {}, args)

    def test_effective_budget_combines_ordinary_overrides_and_visibility(self):
        ordinary = merge_overrides(patch={'texts': [{'at': '#x'+str(i), 'value': 'x'} for i in range(128)]})
        with self.assertRaises(AppError):
            components.compile_overrides(None, {'assets': []}, {'asset': {'html_source': {}}, 'data': {}, 'files': []},
                ordinary, [field('show', 'boolean')], [{'field_id': 'show', 'value': False}])

    def test_component_policy_keeps_inert_data_and_rejects_real_remote_references(self):
        from ai_ad_editor.policy import audit_local_tree
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for value, expected in (({'engine': {'name': 'local'}}, True),
                    ({'engine': html.ENGINE, 'component_fields': [field(at='p:first-child', default='Offer: today')]}, True),
                    ({'engine': html.ENGINE, 'component_values': [{'field_id': 'caption:short', 'value': 'CTA: today'}]}, True),
                    ({'engine': html.ENGINE, 'component_values': [{'field_id': 'headline', 'value': 'https://example.invalid/x'}]}, False)):
                atomic_write_json(root/'record.json', value)
                self.assertEqual(audit_local_tree(root)['ok'], expected, value)

    def test_source_discovery_needs_no_runtime_and_preserves_original_html_zip(self):
        with tempfile.TemporaryDirectory() as folder:
            root, _ = create_project(Path(folder)/'project'); source = Path(folder)/'source'; source.mkdir()
            page = b'<p id="title">Original</p><script>window.film={frame(){}}</script>'
            (source/'index.html').write_bytes(page)
            atomic_write_json(source/'manifest.json', spec(component_fields=[field()]))
            code, result = cli('motion', 'html-source', '--project', root, '--input', source/'manifest.json', '--asset-id', 'source')
            self.assertEqual(code, 0, result)
            asset = result['data']['asset']; before = (root/'project.json').read_bytes()
            with zipfile.ZipFile(root/asset['uri']) as z:
                self.assertEqual(z.read('index.html'), page)
                self.assertNotIn('component_fields', json.loads(z.read('motion.json'))['spec'])
            with mock.patch.object(html, 'verify_runtime', side_effect=AssertionError('discovery must not use runtime')):
                code, result = cli('motion', 'html-fields', '--project', root, '--source-asset-id', 'source')
            self.assertEqual(code, 0, result); self.assertFalse(result['data']['drawing_executed'])
            from jsonschema import Draft202012Validator
            schema = Draft202012Validator(result['data']['schema'])
            self.assertTrue(schema.is_valid({'headline': ''})); self.assertTrue(schema.is_valid({'headline': None}))
            self.assertFalse(schema.is_valid({'unknown': 'x'})); self.assertFalse(schema.is_valid({'headline': False}))
            self.assertEqual((root/'project.json').read_bytes(), before)

    def test_packaged_schema_and_semantics_reject_ambiguous_component_recipes(self):
        with tempfile.TemporaryDirectory() as folder:
            root, project = create_project(Path(folder)/'project')
            source = {'id': 'source', 'kind': 'generated', 'uri': 'source.zip', 'sha256': 'sha256:'+'0'*64, 'rights_ref': 'source', 'probe': {},
                      'html_source': {'component_fields': [field(), field('other', name='headline', at='#other')]}}
            project['assets'].append(source)
            self.assertTrue(make_validator().is_valid(project))
            report = validate_project(root, project)
            self.assertTrue(any(x['code'] == 'HTML_COMPONENT_INVALID' for x in report['errors']), report)
            source['html_source']['component_fields'][0]['n'] = 1e20
            self.assertFalse(make_validator().is_valid(project))


@unittest.skipUnless(os.environ.get('AI_AD_EDITOR_TEST_HTML_RUNTIME'), 'explicit existing native HTML toolchain not configured')
class ComponentNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = html.prepare_runtime(Path.cwd(), json.loads(Path(os.environ['AI_AD_EDITOR_TEST_HTML_RUNTIME']).read_text(encoding='utf8')))

    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='html-component-native-'); self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name); self.root, _ = create_project(self.folder/'project')
        atomic_write_json(self.root/'config/html-motion-runtime.json', self.runtime)
        self.source = self.folder/'source'; self.source.mkdir()
        evidence = self.source/'provenance.json'; atomic_write_json(evidence, {'source': 'original procedural test pixels', 'license': 'CC0-1.0'})
        for name, color in [('red', (255, 0, 0, 255)), ('blue', (0, 0, 255, 255))]:
            path = self.source/(name+'.png'); path.write_bytes(png_bytes(color))
            code, result = cli('media', 'ingest', '--project', self.root, '--input', path, '--asset-id', name,
                '--license-spdx', 'CC0-1.0', '--verification-status', 'verified', '--permitted-use', 'commercial_ad', '--evidence', evidence)
            self.assertEqual(code, 0, result)
        self.page = '''<!doctype html><style>:root{--size:12px;--accent:#ff0000}*{margin:0}body{background:transparent}
          .box{position:absolute;top:4px;width:12px;height:12px}#shown{left:4px;width:var(--size);background:var(--accent)}
          #hidden{left:24px;background:#00ff00}#css{left:44px;background:#0000ff;display:none!important}
          #visibility{left:64px;background:#ffff00;visibility:hidden!important}#animated{left:80px;background:#ff00ff}
          #logo,#bg{position:absolute;left:4px;top:24px;width:8px;height:8px}#bg{left:24px;background-image:url(red.png)}
          #title{position:absolute;left:4px;top:44px;font:10px Arial;color:white}</style>
          <div id="shown" class="box"></div><div id="hidden" class="box" hidden="original"></div>
          <div id="css" class="box"></div><div id="visibility" class="box"></div><div id="animated" class="box"></div>
          <img id="logo" src="red.png"><div id="bg"></div><p id="title">AUTH</p>
          <script>window.film={frame(t){title.firstChild.data='AUTH'+Math.round(t*4);
          animated.hidden=Math.round(t*4)%2===0;animated.style.visibility='visible';}};</script>'''
        (self.source/'index.html').write_text(self.page, encoding='utf8')
        self.fields = [field(), field('shown', 'boolean', at='#shown'), field('hidden', 'boolean', at='#hidden'),
            field('css', 'boolean', at='#css'), field('visibility', 'boolean', at='#visibility'), field('animated', 'boolean', at='#animated'),
            field('size', 'var', schema={'type': 'number', 'minimum': 0, 'maximum': 20}, unit='px'),
            field('color', 'var', var='--accent', schema={'enum': ['#ff0000', '#00ff00', '#0000ff']}),
            field('logo', 'image', at='#logo', schema={'enum': [{'asset_id': 'red'}, {'asset_id': 'blue'}]}),
            field('background', 'image', at='#bg', kind='bg')]
        atomic_write_json(self.source/'manifest.json', spec(component_fields=self.fields,
            resources=[{'path': name+'.png', 'asset_id': name} for name in ('red', 'blue')]))
        code, result = cli('motion', 'html-source', '--project', self.root, '--input', self.source/'manifest.json', '--asset-id', 'source')
        self.assertEqual(code, 0, result)
        self.values = self.source/'values.json'

    def render(self, asset, values=None, previous=None, *extra):
        argv = ['motion', 'html-render', '--project', self.root, '--asset-id', asset,
                '--from-asset-id' if previous else '--source-asset-id', previous or 'source']
        if values is not None:
            atomic_write_json(self.values, values); argv += ['--component-values', self.values]
        code, result = cli(*argv, *extra)
        self.assertEqual(code, 0, result)
        report = json.loads(Path(result['data']['report']).read_text(encoding='utf8'))
        self.assertTrue(report['cleanup']['all_children_reaped'], report)
        self.assertEqual(report['cleanup']['active_after_cleanup'], [])
        return result, report

    def rgba(self, aid, root=None):
        root, project = load_project(root or self.root); asset = next(a for a in project['assets'] if a['id'] == aid)
        return subprocess.run([ffmpeg_path(), '-v', 'error', '-i', str(root/asset['uri']), '-f', 'rawvideo', '-pix_fmt', 'rgba', '-threads', '1', 'pipe:1'],
                              capture_output=True, check=True).stdout

    def pixel(self, data, frame, x, y=8):
        start = ((frame*64+y)*96+x)*4
        return tuple(data[start:start+4])

    def test_explicit_true_false_and_original_hidden_visibility_pixels_all_frames(self):
        self.render('base')
        self.render('forced', {'shown': False, 'hidden': True, 'css': True, 'visibility': True, 'animated': True})
        base, forced = self.rgba('base'), self.rgba('forced')
        for i in range(4):
            self.assertEqual(self.pixel(base, i, 8), (255, 0, 0, 255))
            self.assertEqual(self.pixel(forced, i, 8), (0, 0, 0, 0))
            for x, color in [(28, (0, 255, 0, 255)), (48, (0, 0, 255, 255)), (68, (255, 255, 0, 255))]:
                self.assertEqual(self.pixel(base, i, x), (0, 0, 0, 0))
                self.assertEqual(self.pixel(forced, i, x), color)
            self.assertEqual(self.pixel(base, i, 84)[3], 255 if i%2 else 0)
            self.assertEqual(self.pixel(forced, i, 84), (255, 0, 255, 255))

    def test_all_reset_restores_original_animation_and_source_bytes(self):
        root, project = load_project(self.root); source = next(a for a in project['assets'] if a['id'] == 'source')
        original = (root/source['uri']).read_bytes()
        self.render('base')
        self.render('changed', {'shown': False, 'hidden': True, 'animated': True, 'headline': '', 'size': 0})
        result, _ = self.render('reset', None, 'changed', '--reset-components')
        self.assertEqual(self.rgba('base'), self.rgba('reset'))
        self.assertEqual(result['data']['asset']['html_motion']['component_values'], [])
        self.assertEqual((root/source['uri']).read_bytes(), original)
        self.assertEqual((self.source/'index.html').read_text(encoding='utf8'), self.page)

    def test_partial_reset_keeps_ordinary_overrides_and_other_component_values(self):
        ordinary = self.source/'ordinary.json'
        atomic_write_json(ordinary, {'variables': {'--size': '18px'}, 'texts': [{'at': '#title', 'value': 'MANUAL'}]})
        self.render('changed', {'headline': '', 'size': 8, 'hidden': True}, None, '--overrides', ordinary)
        result, report = self.render('partial', {'headline': None, 'size': None}, 'changed')
        self.assertEqual(result['data']['asset']['html_motion']['template_overrides']['variables']['--size'], '18px')
        self.assertEqual(result['data']['asset']['html_motion']['component_values'], [{'field_id': 'hidden', 'value': True}])
        text = report['worker']['effective_template_controls']['texts']
        self.assertTrue(any(t['value'] == 'MANUAL' for t in text), text)
        pixels = self.rgba('partial')
        for i in range(4):
            self.assertEqual(self.pixel(pixels, i, 20), (255, 0, 0, 255))
            self.assertEqual(self.pixel(pixels, i, 28), (0, 255, 0, 255))

    def test_empty_text_numeric_units_and_two_image_kinds_actual_output(self):
        result, report = self.render('images', {'headline': '', 'size': 16, 'color': '#00ff00',
            'logo': {'asset_id': 'blue'}, 'background': {'asset_id': 'blue'}})
        self.assertFalse(any(t['at'] == '#title' for t in report['worker']['effective_template_controls']['texts']))
        pixels = self.rgba('images')
        for i in range(4):
            self.assertEqual(self.pixel(pixels, i, 18), (0, 255, 0, 255))
            self.assertEqual(self.pixel(pixels, i, 22), (0, 0, 0, 0))
            self.assertEqual(self.pixel(pixels, i, 8, 28), (0, 0, 255, 255))
            self.assertEqual(self.pixel(pixels, i, 28, 28), (0, 0, 255, 255))
        self.assertEqual(result['data']['asset']['html_motion']['component_values'][0]['field_id'], 'background')
        code, audit = cli('policy', 'audit', '--project', self.root)
        self.assertEqual(code, 0, audit)

    def test_renamed_definition_rebuild_keeps_value_and_machine_schema(self):
        self.render('before', {'headline': 'SAVED', 'size': 10, 'logo': {'asset_id': 'blue'}})
        renamed = copy.deepcopy(self.fields); renamed[0]['name'] = '改名后的广告标题'
        path = self.source/'fields.json'; atomic_write_json(path, renamed)
        self.render('after', None, 'before', '--component-fields', path)
        self.assertEqual(self.rgba('after'), self.rgba('before'))
        code, result = cli('motion', 'html-fields', '--project', self.root, '--from-asset-id', 'after')
        self.assertEqual(code, 0, result)
        props = result['data']['schema']['properties']
        self.assertEqual(props['headline']['title'], '改名后的广告标题')
        self.assertEqual(props['size']['x-unit'], 'px')
        from jsonschema import Draft202012Validator
        schema = Draft202012Validator(result['data']['schema'])
        self.assertTrue(schema.is_valid({'size': 0, 'hidden': False, 'headline': '', 'logo': {'asset_id': 'blue'}}))
        self.assertFalse(schema.is_valid({'size': 21})); self.assertFalse(schema.is_valid({'logo': {'asset_id': 'outside'}}))

    def test_image_rights_and_changed_source_bytes_reject_before_browser(self):
        root, project = load_project(self.root)
        before = (root/'project.json').read_bytes(); ledger_bytes = (root/'rights-ledger.json').read_bytes()
        atomic_write_json(self.values, {'logo': {'asset_id': 'blue'}})
        ledger = json.loads(ledger_bytes)
        for r in ledger['records']:
            if r['asset_id'] == 'blue': r['verification_status'] = 'unverified'
        atomic_write_json(root/'rights-ledger.json', ledger)
        with mock.patch.object(html, 'render_frames', side_effect=AssertionError('rights must reject before drawing')):
            code, result = cli('motion', 'html-render', '--project', root, '--source-asset-id', 'source', '--asset-id', 'bad', '--component-values', self.values)
        self.assertNotEqual(code, 0); self.assertEqual(result['errors'][0]['code'], 'HTML_COMPONENT_RIGHTS_BLOCKED')
        self.assertEqual((root/'project.json').read_bytes(), before)
        (root/'rights-ledger.json').write_bytes(ledger_bytes)
        blue = next(a for a in project['assets'] if a['id'] == 'blue'); (root/blue['uri']).write_bytes(png_bytes((0, 255, 0, 255)))
        code, result = cli('motion', 'html-render', '--project', root, '--source-asset-id', 'source', '--asset-id', 'bad2', '--component-values', self.values, '--dry-run')
        self.assertNotEqual(code, 0); self.assertEqual(result['errors'][0]['code'], 'HTML_RESOURCE_CHANGED')

    def test_invalid_component_selector_fails_without_partial_project(self):
        bad = copy.deepcopy(self.fields); bad[1]['at'] = '#missing'
        path = self.source/'fields.json'; atomic_write_json(path, bad); atomic_write_json(self.values, {'shown': False})
        before = (self.root/'project.json').read_bytes(); rights = (self.root/'rights-ledger.json').read_bytes()
        code, result = cli('motion', 'html-render', '--project', self.root, '--source-asset-id', 'source', '--asset-id', 'bad',
                           '--component-fields', path, '--component-values', self.values)
        self.assertNotEqual(code, 0); self.assertEqual(result['errors'][0]['code'], 'HTML_OVERRIDE_TARGET_MISSING')
        self.assertEqual((self.root/'project.json').read_bytes(), before); self.assertEqual((self.root/'rights-ledger.json').read_bytes(), rights)
        report = json.loads(Path(result['errors'][0]['path']).read_text(encoding='utf8'))
        self.assertTrue(report['cleanup']['all_children_reaped'])

    def test_single_clip_replacement_preserves_author_timing_processing_and_other_clip(self):
        self.render('base')
        root, project = load_project(self.root)
        track = next(t for t in project['sequences'][0]['tracks'] if t['kind'] == 'video')
        clip = {'id': 'selected', 'asset_id': 'base', 'timeline_start_tick': 0, 'duration_tick': TPS//2,
                'source_in_tick': TPS//4, 'source_out_tick': TPS*3//4, 'transform': {'x': 3, 'y': 2},
                'effects': [{'type': 'saturation', 'parameters': {'saturation': 0.8}}]}
        other = {**copy.deepcopy(clip), 'id': 'other', 'timeline_start_tick': TPS//2}
        track['clips'] = [clip, other]; project['sequences'][0]['duration_tick'] = TPS; save_project(root, project)
        before = copy.deepcopy(project['sequences'])
        self.render('replacement', {'headline': 'NEW'}, 'base', '--replace-clip-id', 'selected')
        after = load_project(root)[1]['sequences']; expected = copy.deepcopy(before)
        next(c for t in expected[0]['tracks'] for c in t['clips'] if c['id'] == 'selected')['asset_id'] = 'replacement'
        self.assertEqual(after, expected)

    def test_locked_clip_and_wrong_prior_asset_reject_without_drawing(self):
        self.render('base')
        root, project = load_project(self.root); track = next(t for t in project['sequences'][0]['tracks'] if t['kind'] == 'video')
        track['locked'] = True; track['clips'] = [{'id': 'selected', 'asset_id': 'base', 'timeline_start_tick': 0,
            'duration_tick': TPS, 'source_in_tick': 0, 'source_out_tick': TPS}]; save_project(root, project)
        before = (root/'project.json').read_bytes()
        with mock.patch.object(html, 'render_frames', side_effect=AssertionError('locked target must reject')):
            code, result = cli('motion', 'html-render', '--project', root, '--from-asset-id', 'base', '--asset-id', 'bad', '--replace-clip-id', 'selected')
        self.assertNotEqual(code, 0); self.assertEqual(result['errors'][0]['code'], 'HTML_TRACK_INVALID')
        self.assertEqual((root/'project.json').read_bytes(), before)

    def test_native_package_rebuild_keeps_editable_definitions_values_and_pixels(self):
        self.render('edited', {'headline': '', 'hidden': True, 'logo': {'asset_id': 'blue'}})
        package = self.folder/'project.zip'; restored = self.folder/'restored'
        code, result = cli('convert', 'export', '--project', self.root, '--output', package, '--target-format', 'package')
        self.assertEqual(code, 0, result)
        code, result = cli('convert', 'import', '--input', package, '--output', restored)
        self.assertEqual(code, 0, result)
        atomic_write_json(restored/'config/html-motion-runtime.json', self.runtime)
        code, result = cli('motion', 'html-render', '--project', restored, '--from-asset-id', 'edited', '--asset-id', 'rebuilt')
        self.assertEqual(code, 0, result)
        self.assertEqual(self.rgba('edited'), self.rgba('rebuilt', restored))
        self.assertEqual(result['data']['asset']['html_motion']['component_values'],
                         next(a for a in load_project(self.root)[1]['assets'] if a['id'] == 'edited')['html_motion']['component_values'])

    def test_native_fragment_rewrites_default_choices_and_values_as_local_asset_ids(self):
        fields = copy.deepcopy(self.fields); fields[8]['default'] = {'asset_id': 'red'}
        # A reserved-looking user ID stays inert in the values array.
        fields[0]['id'] = 'asset_id'
        definitions = self.source/'fields.json'; atomic_write_json(definitions, fields)
        result, _ = self.render('edited', {'asset_id': 'SAVED', 'logo': {'asset_id': 'blue'}}, None,
            '--component-fields', definitions, '--apply', '--track-id', 'track_video_1')
        library = self.folder/'library'; request = self.folder/'request.json'
        atomic_write_json(request, {'id': 'card', 'version': 1, 'sequence_id': 'seq_main',
                                   'clip_ids': [result['data']['generated_clip']['id']]})
        code, result = cli('fragment', 'save', '--project', self.root, '--library', library, '--input', request)
        self.assertEqual(code, 0, result)
        recipient, _ = create_project(self.folder/'recipient')
        atomic_write_json(recipient/'config/html-motion-runtime.json', self.runtime)
        atomic_write_json(request, {'id': 'card', 'version': 1, 'sequence_id': 'seq_main',
                                   'track_id': 'track_video_1', 'at_tick': 0, 'instance_id': 'copy'})
        code, result = cli('fragment', 'apply', '--project', recipient, '--library', library, '--input', request)
        self.assertEqual(code, 0, result)
        project = load_project(recipient)[1]; asset = next(a for a in project['assets'] if 'html_motion' in a)
        recipe = asset['html_motion']; ids = {a['id'] for a in project['assets']}
        self.assertTrue(recipe['component_fields'][8]['default']['asset_id'] in ids)
        self.assertNotEqual(recipe['component_fields'][8]['default']['asset_id'], 'red')
        image = next(v['value']['asset_id'] for v in recipe['component_values'] if v['field_id'] == 'logo')
        self.assertIn(image, ids); self.assertNotEqual(image, 'blue')
        self.assertEqual(next(v['value'] for v in recipe['component_values'] if v['field_id'] == 'asset_id'), 'SAVED')
        code, result = cli('motion', 'html-render', '--project', recipient, '--from-asset-id', asset['id'], '--asset-id', 'rebuilt')
        self.assertEqual(code, 0, result)
        self.assertEqual(self.rgba('edited'), self.rgba('rebuilt', recipient))

    def test_component_visibility_is_restored_between_actual_shutter_subframes(self):
        self.render('base', None, None, '--shutter-samples', '3', '--shutter-fraction', '0.5')
        self.render('forced', {'animated': True}, None, '--shutter-samples', '3', '--shutter-fraction', '0.5')
        self.render('restored', None, 'forced', '--reset-components')
        self.assertEqual(self.rgba('base'), self.rgba('restored'))
        forced = self.rgba('forced')
        for i in range(4):
            self.assertEqual(self.pixel(forced, i, 84), (255, 0, 255, 255))


if __name__ == '__main__':
    unittest.main()
