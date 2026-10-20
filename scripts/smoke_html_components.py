"""Real offline component CLI, editable transfers, queue, and original CC0 media."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from PIL import Image, ImageDraw
from run_frozen_regression import frozen
from smoke_fragments import grid_font

ROOT = Path(__file__).resolve().parents[1]
W, H, FPS, N, TPS = 384, 216, 10, 20, 90000


def sha(path):
    return 'sha256:' + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rawsha(value):
    return 'sha256:' + hashlib.sha256(value).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')


def public_font(path):
    """Extend the original CC0 fixture grid with an original O outline."""
    from fontTools.ttLib import TTFont
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    grid_font(path)
    font = TTFont(path, recalcTimestamp=False)
    pen = TTGlyphPen(None)
    for y, line in enumerate(('01110', '10001', '10001', '10001', '10001', '10001', '01110')):
        for x, bit in enumerate(line):
            if bit == '1':
                left, bottom = 40+100*x, 100*(6-y)
                pen.moveTo((left, bottom)); pen.lineTo((left+90, bottom)); pen.lineTo((left+90, bottom+90))
                pen.lineTo((left, bottom+90)); pen.closePath()
    font.setGlyphOrder([*font.getGlyphOrder(), 'O'])
    font['glyf']['O'] = pen.glyph()
    font['hmtx']['O'] = (600, 0)
    for table in font['cmap'].tables:
        if table.isUnicode():
            table.cmap[ord('O')] = 'O'
    font.save(path); font.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('work', 'evidence', 'assets', 'html-runtime'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--installed', type=Path)
    args = parser.parse_args()
    work, evidence, public = (getattr(args, k).resolve() for k in ('work', 'evidence', 'assets'))
    assert work.is_relative_to(ROOT/'product/.runtime') and evidence.is_relative_to(ROOT/'docs') and public.is_relative_to(ROOT/'docs/assets')
    assert not any(p.exists() for p in (work, evidence, public))
    for p in (work, evidence, public):
        p.mkdir(parents=True)
    (evidence/'executed-smoke.py.txt').write_bytes(Path(__file__).read_bytes())
    record = {'status': 'running', 'started_at_utc': datetime.now(timezone.utc).isoformat(),
              'generator_sha256': sha(__file__), 'frozen_before': frozen(), 'calls': [], 'checks': [],
              'network': False, 'virtualization': False, 'new_model_inference': 0,
              'continuous_playback_reviewed': False, 'audio_reviewed': False, 'audio_streams': 0,
              'natural_quality_accepted': False, 'full_capcut_parity': False}

    def save():
        write(evidence/'verification.json', record)

    def check(name, passed, **details):
        record['checks'].append({'name': name, 'ok': bool(passed), **details}); save()
        assert passed, name

    def run(label, command, *, cli=False, expected=0):
        command = list(map(str, command))
        env = dict(os.environ)
        temp = ROOT/'product/.runtime/temp'; temp.mkdir(parents=True, exist_ok=True)
        env.update(TEMP=str(temp), TMP=str(temp), TMPDIR=str(temp), PYTHONDONTWRITEBYTECODE='1',
                   AI_AD_EDITOR_RUNTIME_DIR=str(ROOT/'product/.runtime'))
        start = time.monotonic()
        result = subprocess.run(command, cwd=work, env=env, capture_output=True, timeout=900)
        (evidence/(label+'.stderr.log')).write_bytes(result.stderr)
        if not label.startswith('decode-'):
            (evidence/(label+'.stdout.log')).write_bytes(result.stdout)
        record['calls'].append({'label': label, 'command': command, 'exit_code': result.returncode,
            'expected_exit_code': expected, 'seconds': time.monotonic()-start, 'cli': cli,
            'stdout_bytes': len(result.stdout), 'stdout_sha256': rawsha(result.stdout), 'stderr_sha256': rawsha(result.stderr)})
        save()
        assert result.returncode == expected, (label, result.stdout[-5000:].decode('utf8', 'replace'), result.stderr[-1500:].decode('utf8', 'replace'))
        return result.stdout

    if args.installed:
        prefix = [sys.executable, '-I', '-S', '-B', '-X', 'utf8', args.installed.resolve()/'run.py']
    else:
        bootstrap = 'import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.cli import main;raise SystemExit(main())'
        prefix = [sys.executable, '-E', '-B', '-X', 'utf8', '-c', bootstrap, ROOT/'product/src']

    def cli(label, *argv, expected=0):
        return json.loads(run(label, [*prefix, *argv], cli=True, expected=expected))

    ffmpeg = shutil.which('ffmpeg'); ffprobe = shutil.which('ffprobe')
    assert ffmpeg and ffprobe

    def ff(label, *argv):
        return run(label, [ffmpeg, '-hide_banner', '-y', '-v', 'error', '-filter_complex_threads', '1', *argv])

    def decode(label, path):
        return ff('decode-'+label, '-i', path, '-an', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-threads', '1', 'pipe:1')

    def asset(project, aid):
        return next(a for a in json.loads((project/'project.json').read_bytes())['assets'] if a['id'] == aid)

    def report(label, result):
        value = json.loads(Path(result['data']['report']).read_bytes())
        write(evidence/(label+'-browser.json'), value)
        check(label+'-browser-cleanup', value['cleanup']['all_children_reaped'] and value['cleanup']['active_after_cleanup'] == [])
        return value

    def configure(project):
        value = json.loads((project/'project.json').read_bytes())
        value['settings']['canvas'].update(width=W, height=H)
        value['settings']['timebase']['display_fps'] = {'num': FPS, 'den': 1}
        write(project/'project.json', value)
        cli(project.name+'-register', 'motion', 'html-register', '--project', project, '--input', args.html_runtime.resolve())

    try:
        template = public/'template'; template.mkdir()
        public_font(template/'font.ttf')
        for name, color in [('product-original', '#fb923c'), ('product-blue', '#38bdf8')]:
            image = Image.new('RGBA', (64, 80)); draw = ImageDraw.Draw(image)
            draw.rounded_rectangle((18, 0, 46, 12), radius=3, fill='#cbd5e1')
            draw.rounded_rectangle((8, 10, 56, 78), radius=9, fill=color)
            draw.rectangle((14, 34, 50, 58), fill='#13243b')
            draw.line((20, 40, 44, 40), fill='white', width=2)
            image.save(template/(name+'.png'))
        (template/'index.html').write_text('''<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="style.css">
          <div id="bar"></div><h1 id="title">EDIT VIDEO</h1><p id="cta">CTA</p><img id="product" src="product.png">
          <div id="badge" hidden="original"></div><div id="moving"></div><script type="module" src="scene.mjs"></script>''', encoding='utf8')
        (template/'style.css').write_text('''@font-face{font-family:AgentGrid;src:url(font.ttf)}
          :root{--brand:#fb923c;--bar-size:96px;--outline:#cbd5e1}*{margin:0;box-sizing:border-box}
          html,body{width:384px;height:216px;background:#101829;overflow:hidden}
          #bar{position:absolute;left:24px;top:24px;width:var(--bar-size);height:12px;background:var(--brand)}
          #title{position:absolute;left:24px;top:72px;color:white;font:26px AgentGrid}
          #cta{position:absolute;left:24px;top:142px;color:var(--brand);font:20px AgentGrid}
          #product{position:absolute;left:284px;top:68px;width:64px;height:80px}
          #badge{position:absolute;left:284px;top:24px;width:64px;height:16px;background:#22c55e}
          #moving{position:absolute;left:180px;top:190px;width:12px;height:12px;background:var(--outline)}''', encoding='utf8')
        (template/'scene.mjs').write_text('''const title=document.getElementById('title'),moving=document.getElementById('moving');
          window.film={ready:document.fonts.ready,frame(t){title.textContent=t<1?'EDIT VIDEO':'EDIT 2';
          moving.style.left=(180+Math.round(t*16))+'px';moving.hidden=Math.round(t*8)%2===0;}};''', encoding='utf8')
        fields = [
            {'id': 'headline', 'name': '广告标题', 'type': 'text', 'at': '#title', 'schema': {'maxLength': 24}},
            {'id': 'badge', 'name': '展示标签', 'type': 'boolean', 'at': '#badge'},
            {'id': 'moving', 'name': '展示动效', 'type': 'boolean', 'at': '#moving'},
            {'id': 'bar', 'name': '进度长度', 'type': 'var', 'var': '--bar-size', 'unit': 'px', 'schema': {'type': 'number', 'minimum': 0, 'maximum': 120}},
            {'id': 'brand', 'name': '品牌颜色', 'type': 'var', 'var': '--brand', 'schema': {'enum': ['#fb923c', '#38bdf8']}},
            {'id': 'product', 'name': '产品图片', 'type': 'image', 'kind': 'img', 'at': '#product',
             'default': {'asset_id': 'product-original'}, 'schema': {'enum': [{'asset_id': 'product-original'}, {'asset_id': 'product-blue'}]}},
        ]
        manifest = {'entry': 'index.html', 'width': W, 'height': H, 'fps': {'num': FPS, 'den': 1}, 'duration_tick': 2*TPS,
                    'files': ['index.html', 'style.css', 'scene.mjs'], 'variables': [], 'component_fields': fields,
                    'resources': [{'path': 'font.ttf', 'asset_id': 'font'}, {'path': 'product.png', 'asset_id': 'product-original'},
                                  {'path': 'product-blue.png', 'asset_id': 'product-blue'}]}
        write(template/'manifest.json', manifest)
        write(public/'values.json', {'headline': 'VIDEO 2', 'badge': True, 'moving': True, 'bar': 48,
                                    'brand': '#38bdf8', 'product': {'asset_id': 'product-blue'}})
        write(public/'partial-reset.json', {'headline': None, 'bar': None})
        renamed = copy.deepcopy(fields); renamed[0]['name'] = '活动主标题'
        write(public/'renamed-fields.json', renamed)
        write(public/'ordinary-overrides.json', {'variables': {'--bar-size': '80px'}, 'texts': [{'at': '#cta', 'value': 'CTA 2'}]})
        write(public/'provenance.json', {'license_spdx': 'CC0-1.0', 'source': 'Original procedural product art, grid glyphs and HTML/CSS/JS',
            'generator_sha256': sha(__file__), 'font_generator_sha256': sha(ROOT/'scripts/smoke_fragments.py'),
            'width': W, 'height': H, 'fps': FPS, 'frames': N, 'seconds': 2, 'audio_streams': 0, 'new_model_inference': 0})
        project = work/'project'; cli('init', 'project', 'init', project); configure(project)
        rights = ['--license-spdx', 'CC0-1.0', '--verification-status', 'verified', '--permitted-use', 'commercial_ad',
                  '--creator', 'agent-video-kit', '--evidence', public/'provenance.json']
        for aid, name in [('font', 'font.ttf'), ('product-original', 'product-original.png'), ('product-blue', 'product-blue.png')]:
            cli('ingest-'+aid, 'media', 'ingest', '--project', project, '--input', template/name, '--asset-id', aid, *rights)
        source = cli('source', 'motion', 'html-source', '--project', project, '--input', template/'manifest.json', '--asset-id', 'source', '--license-spdx', 'CC0-1.0')
        source_zip = project/source['data']['asset']['uri']; original_zip_sha = sha(source_zip)
        initial_fields = cli('fields-source', 'motion', 'html-fields', '--project', project, '--source-asset-id', 'source')
        check('typed-discovery-six-fields', len(initial_fields['data']['fields']) == 6 and initial_fields['data']['schema']['properties']['bar']['x-unit'] == 'px')
        before = (project/'project.json').read_bytes()
        cli('plan', 'motion', 'html-render', '--project', project, '--source-asset-id', 'source', '--asset-id', 'planned',
            '--component-values', public/'values.json', '--dry-run')
        check('dry-run-project-unchanged', before == (project/'project.json').read_bytes())
        base = cli('base', 'motion', 'html-render', '--project', project, '--source-asset-id', 'source', '--asset-id', 'base',
                   '--overrides', public/'ordinary-overrides.json', '--layout-check', 'strict')
        report('base', base)
        changed = cli('changed', 'motion', 'html-render', '--project', project, '--from-asset-id', 'base', '--asset-id', 'changed',
            '--component-values', public/'values.json', '--apply', '--track-id', 'track_video_1')
        changed_report = report('changed', changed)
        inherited = cli('inherited', 'motion', 'html-render', '--project', project, '--from-asset-id', 'changed', '--asset-id', 'inherited')
        report('inherited', inherited)
        rename = cli('rename', 'motion', 'html-render', '--project', project, '--from-asset-id', 'changed', '--asset-id', 'renamed',
                     '--component-fields', public/'renamed-fields.json')
        report('rename', rename)
        partial = cli('partial', 'motion', 'html-render', '--project', project, '--from-asset-id', 'changed', '--asset-id', 'partial',
                      '--component-values', public/'partial-reset.json')
        report('partial', partial)
        reset = cli('reset', 'motion', 'html-render', '--project', project, '--from-asset-id', 'changed', '--asset-id', 'reset', '--reset-components')
        report('reset', reset)
        write(public/'empty-title.json', {'headline': ''})
        empty = cli('empty', 'motion', 'html-render', '--project', project, '--from-asset-id', 'changed', '--asset-id', 'empty',
                    '--component-values', public/'empty-title.json')
        empty_report = report('empty', empty)
        check('empty-text-is-actual-empty-control', not any(x['at'] == '#title' for x in empty_report['worker']['effective_template_controls']['texts']))
        pixels = {}
        for name in ('base', 'changed', 'inherited', 'renamed', 'partial', 'reset', 'empty'):
            pixels[name] = decode(name, project/asset(project, name)['uri'])
            check(name+'-exact-frame-storage', len(pixels[name]) == W*H*N*4, rgba_sha256=rawsha(pixels[name]), frames=N)
        check('inherit-and-stable-id-rename-pixel-identical', pixels['changed'] == pixels['inherited'] == pixels['renamed'])
        check('reset-retains-ordinary-overrides-and-original-animation', pixels['base'] == pixels['reset'])
        check('source-original-zip-preserved', sha(source_zip) == original_zip_sha)
        effective = changed_report['worker']['effective_template_controls']
        check('component-title-and-nontarget-manual-text', any(t['value'] == 'VIDEO 2' for t in effective['texts']) and any(t['value'] == 'CTA 2' for t in effective['texts']))
        blue = Image.open(template/'product-blue.png').convert('RGBA'); background = Image.new('RGBA', blue.size, '#101829')
        expected_product = Image.alpha_composite(background, blue).tobytes()
        independent = True
        for frame in range(N):
            picture = Image.frombytes('RGBA', (W, H), pixels['changed'][frame*W*H*4:(frame+1)*W*H*4])
            independent &= picture.crop((284, 68, 348, 148)).tobytes() == expected_product
            independent &= picture.getpixel((300, 28)) == (34, 197, 94, 255)
            independent &= picture.getpixel((26, 26)) == (56, 189, 248, 255)
            independent &= picture.getpixel((90, 26)) == (16, 24, 41, 255)
            x = 180 + round(frame/FPS*16)
            independent &= picture.getpixel((x+4, 194)) == (203, 213, 225, 255)
        check('all-frames-independent-product-image-color-width-and-visibility-pixels', independent, frames=N)
        package = work/'project.zip'; restored = work/'restored'
        cli('package-export', 'convert', 'export', '--project', project, '--output', package, '--target-format', 'package')
        cli('package-import', 'convert', 'import', '--input', package, '--output', restored); configure(restored)
        rebuilt = cli('package-rebuild', 'motion', 'html-render', '--project', restored, '--from-asset-id', 'changed', '--asset-id', 'rebuilt')
        report('package-rebuild', rebuilt)
        check('package-editable-rebuild-exact-rgba', decode('package', restored/rebuilt['data']['asset']['uri']) == pixels['changed'])
        library = work/'library'; request = work/'fragment.json'
        write(request, {'id': 'component-card', 'version': 1, 'sequence_id': 'seq_main', 'clip_ids': [changed['data']['generated_clip']['id']]})
        cli('fragment-save', 'fragment', 'save', '--project', project, '--library', library, '--input', request)
        recipient = work/'recipient'; cli('recipient-init', 'project', 'init', recipient); configure(recipient)
        write(request, {'id': 'component-card', 'version': 1, 'sequence_id': 'seq_main', 'track_id': 'track_video_1', 'at_tick': 0, 'instance_id': 'copy'})
        cli('fragment-apply', 'fragment', 'apply', '--project', recipient, '--library', library, '--input', request)
        transferred = next(a for a in json.loads((recipient/'project.json').read_bytes())['assets'] if 'html_motion' in a)
        remapped = next(v['value']['asset_id'] for v in transferred['html_motion']['component_values'] if v['field_id'] == 'product')
        check('fragment-image-default-choices-and-explicit-id-mapped', remapped != 'product-blue' and
            transferred['html_motion']['component_fields'][-1]['default']['asset_id'] != 'product-original', image_asset_id=remapped)
        rebuilt = cli('fragment-rebuild', 'motion', 'html-render', '--project', recipient, '--from-asset-id', transferred['id'], '--asset-id', 'rebuilt')
        report('fragment-rebuild', rebuilt)
        check('fragment-editable-rebuild-exact-rgba', decode('fragment', recipient/rebuilt['data']['asset']['uri']) == pixels['changed'])
        author = copy.deepcopy(json.loads((project/'project.json').read_bytes())['sequences'])
        replacement = cli('replace-one-clip', 'motion', 'html-render', '--project', project, '--from-asset-id', 'changed', '--asset-id', 'replacement',
            '--replace-clip-id', changed['data']['generated_clip']['id'], '--component-fields', public/'renamed-fields.json')
        report('replace-one-clip', replacement)
        current = json.loads((project/'project.json').read_bytes())['sequences']
        expected_author = copy.deepcopy(author)
        for sequence in expected_author:
            for track in sequence['tracks']:
                for clip in track['clips']:
                    if clip['id'] == changed['data']['generated_clip']['id']: clip['asset_id'] = 'replacement'
        check('single-clip-reference-only-change', current == expected_author)
        jobs = work/'queue.json'
        write(jobs, {'jobs': [{'job_id': 'component_a', 'output': 'renders/a.mp4'}, {'job_id': 'component_b', 'output': 'renders/b.mp4'}]})
        cli('enqueue', 'queue', 'enqueue', '--project', project, '--input', jobs)
        cli('queue-run', 'queue', 'run', '--project', project, '--max-jobs', '2')
        check('queue-two-real-renders-decode-equal', decode('queue-a', project/'renders/a.mp4') == decode('queue-b', project/'renders/b.mp4'))
        check('queue-preserves-component-author-graph', json.loads((project/'project.json').read_bytes())['sequences'] == expected_author)
        for name, values, error in [('unknown', {'unknown': 'x'}, 'HTML_COMPONENT_INVALID'), ('range', {'bar': 1000}, 'HTML_COMPONENT_INVALID'),
                                    ('url', {'product': 'https://example.invalid/x.png'}, 'HTML_COMPONENT_INVALID')]:
            path = work/(name+'.json'); write(path, values)
            project_before, rights_before = (project/'project.json').read_bytes(), (project/'rights-ledger.json').read_bytes()
            failed = cli('reject-'+name, 'motion', 'html-render', '--project', project, '--from-asset-id', 'changed', '--asset-id', 'bad-'+name,
                '--component-values', path, expected=2)
            check('reject-'+name+'-no-half-project', failed['errors'][0]['code'] == error and
                project_before == (project/'project.json').read_bytes() and rights_before == (project/'rights-ledger.json').read_bytes())
        cli('final-policy', 'policy', 'audit', '--project', project)
        media = []
        for name, aid in [('original', 'base'), ('edited', 'changed'), ('restored', 'reset')]:
            shutil.copyfile(project/asset(project, aid)['uri'], public/(name+'-alpha.nut'))
            ff('movie-'+name, '-i', public/(name+'-alpha.nut'), '-an', '-c:v', 'libx264', '-crf', '18', '-preset', 'medium', '-pix_fmt', 'yuv420p', public/(name+'.mp4'))
        contact = []
        for index in range(N):
            row = Image.new('RGB', (W*3, H))
            for column, name in enumerate(('base', 'changed', 'reset')):
                row.paste(Image.frombytes('RGBA', (W, H), pixels[name][index*W*H*4:(index+1)*W*H*4]).convert('RGB'), (column*W, 0))
            contact.append(row)
        contact[0].save(public/'comparison.gif', save_all=True, append_images=contact[1:], duration=100, loop=0, optimize=False, disposal=2)
        contact[4].save(public/'comparison.png')
        for path in sorted(public.iterdir()):
            if path.suffix not in {'.nut', '.mp4', '.gif'}:
                continue
            probe = json.loads(run('probe-'+path.name, [ffprobe, '-v', 'error', '-show_streams', '-show_frames', '-show_format', '-of', 'json', path]))
            write(evidence/('probe-'+path.name+'.json'), probe)
            frames = [f for f in probe['frames'] if f['media_type'] == 'video']
            streams = [s for s in probe['streams'] if s['codec_type'] == 'video']
            check('encoded-clock-'+path.name, len(frames) == N and not any(s['codec_type'] == 'audio' for s in probe['streams']) and
                all(abs(float(f.get('best_effort_timestamp_time', f.get('pts_time', -1))) - i/FPS) < 0.000001 for i, f in enumerate(frames)),
                frames=len(frames), width=streams[0]['width'], height=streams[0]['height'], fps=streams[0]['avg_frame_rate'])
            media.append({'path': path.relative_to(ROOT).as_posix(), 'bytes': path.stat().st_size, 'sha256': sha(path), 'frames': N, 'fps': FPS})
        write(public/'files.json', {p.relative_to(public).as_posix(): {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in public.rglob('*') if p.is_file()})
        record.update(status='passed', media=media, frames_per_case=N, canvas=[W, H],
                      decoded_case_hashes={name: rawsha(value) for name, value in pixels.items()},
                      source_zip_sha256=original_zip_sha, installed=bool(args.installed),
                      successful_cli=sum(c['cli'] and c['exit_code'] == 0 for c in record['calls']),
                      rejected_cli=sum(c['cli'] and c['exit_code'] != 0 for c in record['calls']),
                      source_resource_files={p.relative_to(template).as_posix(): sha(p) for p in template.rglob('*') if p.is_file()})
    except BaseException as exc:
        record.update(status='failed', error={'type': type(exc).__name__, 'message': str(exc)})
        raise
    finally:
        record.update(frozen_after=frozen(), finished_at_utc=datetime.now(timezone.utc).isoformat())
        record['frozen_equal'] = record['frozen_before'] == record['frozen_after']; save()
    assert record['frozen_equal']
    print(json.dumps({'status': record['status'], 'cli_calls': sum(c['cli'] for c in record['calls']),
                      'checks': len(record['checks']), 'frames_per_case': N, 'public_media': len(media)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
