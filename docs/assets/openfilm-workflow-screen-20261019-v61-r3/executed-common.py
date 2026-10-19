"""Shared real CLI/media evidence for the three local workflow demonstrations."""
from __future__ import annotations
import contextlib
from datetime import datetime, timezone
import hashlib
import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import wave

from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
TPS, FPS, SR, W, H = 90000, 8, 48000, 640, 360


def digest(raw): return 'sha256:' + hashlib.sha256(raw).hexdigest()
def sha(path): return digest(Path(path).read_bytes())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8', newline='\n')


class Evidence:
    def __init__(self, work, output, generator):
        self.work, self.output = work.resolve(), output.resolve()
        self.work.mkdir(parents=True, exist_ok=False)
        self.output.mkdir(parents=True, exist_ok=False)
        self.before, self.calls = frozen(), []
        self.env = dict(os.environ, PYTHONPATH=str(ROOT/'product/src'), PYTHONDONTWRITEBYTECODE='1',
                        TEMP=str(self.work), TMP=str(self.work), TMPDIR=str(self.work),
                        AI_AD_EDITOR_RUNTIME_DIR=str(self.work/'runtime'))
        self.record = {'status':'running', 'started_at_utc':datetime.now(timezone.utc).isoformat(),
                       'generator_sha256':sha(generator), 'common_sha256':sha(Path(__file__)),
                       'frozen_before':self.before, 'network':'disabled', 'virtualization':False,
                       'new_neural_model_forwards':0, 'natural_quality_accepted':False}
        shutil.copyfile(generator, self.output/'executed-generator.py')
        shutil.copyfile(Path(__file__), self.output/'executed-common.py')
        self.persist()

    def persist(self):
        save(self.output/'verification.json', {**self.record, 'calls':self.calls})

    def command(self, args, *, data=None, expected=0, cli=False):
        args = list(map(str, args)); index = len(self.calls)+1
        result = subprocess.run(args, cwd=ROOT, env=self.env, input=data, capture_output=True, timeout=300)
        stem = f'calls/{index:03}'
        compressed = not cli and len(result.stdout)>256*1024
        stdout, stderr = self.output/(stem+('.stdout.gz' if compressed else '.stdout')), self.output/(stem+'.stderr')
        stdout.parent.mkdir(exist_ok=True)
        stdout.write_bytes(gzip.compress(result.stdout,mtime=0) if compressed else result.stdout); stderr.write_bytes(result.stderr)
        row = {'index':index, 'arguments':args, 'exit_code':result.returncode, 'expected_exit_code':expected,
               'kind':'cli' if cli else 'native', 'stdout':stdout.relative_to(self.output).as_posix(),
               'stderr':stderr.relative_to(self.output).as_posix(), 'stdout_sha256':sha(stdout), 'stderr_sha256':sha(stderr),
               'stdout_encoding':'gzip' if compressed else 'identity', 'stdout_decoded_sha256':digest(result.stdout), 'stdout_decoded_bytes':len(result.stdout)}
        self.calls.append(row); self.persist()
        if result.returncode != expected:
            raise RuntimeError(json.dumps(row, ensure_ascii=False)+'\n'+result.stdout.decode('utf-8','replace')[-3000:]+'\n'+result.stderr.decode('utf-8','replace')[-3000:])
        return json.loads(result.stdout) if cli else result.stdout

    def cli(self, *args, expected=0):
        return self.command([sys.executable,'-B','-X','utf8','-m','ai_ad_editor',*args], expected=expected, cli=True)

    def ffmpeg(self, *args, data=None):
        return self.command(['ffmpeg','-nostdin','-v','error','-n',*args], data=data)

    def project(self, name, seconds):
        root = self.work/name
        self.cli('project','init',root)
        path = root/'project.json'; value = json.loads(path.read_bytes())
        value['settings']['canvas'].update(width=W,height=H)
        value['settings']['timebase']['display_fps'] = {'num':FPS,'den':1}
        value['sequences'][0]['duration_tick'] = round(seconds*TPS)
        # The public Agent Project document is configured before transactional edits.
        save(path,value)
        return root

    def ingest(self, project, path, aid, *, verified=True):
        return self.cli('media','ingest','--project',project,'--input',path,'--asset-id',aid,
                        '--verification-status','verified' if verified else 'unverified',
                        '--permitted-use','commercial_ad' if verified else 'internal',
                        '--license-spdx','CC0-1.0' if verified else 'LicenseRef-UNVERIFIED',
                        '--creator','Agent Video Kit workflow fixture authors',
                        '--source-url','local://original-workflow-fixture', '--evidence',self.output/'provenance.json')

    def compose(self, project, name, operations):
        plan = self.output/(name+'.compose.json'); save(plan,{'operations':operations})
        before = sha(project/'project.json')
        self.cli('timeline','compose','--project',project,'--input',plan,'--dry-run')
        if sha(project/'project.json') != before: raise ValueError('compose dry-run changed project')
        return self.cli('timeline','compose','--project',project,'--input',plan)

    def render(self, project, name, *, publish=True, public_video=True):
        target = project/'renders'/(name+'.mkv')
        result = self.cli('render','--project',project,'--output',target,'--container','mkv',
                          '--pixel-format','yuv444p','--crf','0','--audio-codec','pcm_f32le',
                          *(['--publish'] if publish else []))
        if public_video:shutil.copyfile(target,self.output/target.name)
        shutil.copyfile(result['data']['manifest'],self.output/(name+'.manifest.json'))
        self.cli('quality','check','--project',project,'--input',target)
        self.cli('policy','audit','--project',project)
        return target

    def video(self, path):
        import numpy as np
        raw = self.ffmpeg('-i',path,'-map','0:v:0','-an','-fps_mode','passthrough','-pix_fmt','rgb24','-f','rawvideo','pipe:1')
        return np.frombuffer(raw,np.uint8).reshape(-1,H,W,3)

    def audio(self, path):
        import numpy as np
        raw = self.ffmpeg('-i',path,'-map','0:a:0','-vn','-ar',SR,'-ac',2,'-f','f32le','pipe:1')
        return np.frombuffer(raw,'<f4').reshape(-1,2)

    def preview(self, path, name):
        self.ffmpeg('-i',path,'-an','-c:v','libx264','-crf','17','-pix_fmt','yuv420p',self.output/(name+'.mp4'))
        self.ffmpeg('-i',path,'-an','-vf','fps=8,scale=480:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse',self.output/(name+'.gif'))

    def finish(self, error=None, **measurements):
        after = frozen()
        self.record.update(measurements, status='failed' if error else 'passed_controlled_workflow_media_checks',
                           error=None if error is None else type(error).__name__+': '+str(error),
                           frozen_after=after, frozen_equal=self.before==after,
                           finished_at_utc=datetime.now(timezone.utc).isoformat())
        if self.before != after: self.record.update(status='failed',error='product inputs changed')
        self.record['files'] = [{'path':p.relative_to(self.output).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size}
                                for p in sorted(self.output.rglob('*')) if p.is_file() and p.name!='verification.json']
        self.persist()


def wav(path, pcm):
    with wave.open(str(path),'wb') as output:
        output.setnchannels(2);output.setsampwidth(2);output.setframerate(SR);output.writeframes(pcm.astype('<i2').tobytes())


def font(output):
    from PIL import ImageFont
    root=ROOT/'docs/assets/magnetic-reorder-v53-r5-20261018'
    for name in ('DejaVuSans.ttf','LICENSE_DEJAVU'):shutil.copyfile(root/name,output/name)
    return ImageFont.truetype(str(output/'DejaVuSans.ttf'),24)


def append(aid, cid, track, at, duration, *, source=0, **fields):
    return {'op':'append_clip','asset_id':aid,'id':cid,'track_id':track,
            'timeline_start_tick':at,'duration_tick':duration,
            'source_in_tick':source,'source_out_tick':source+duration,**fields}
