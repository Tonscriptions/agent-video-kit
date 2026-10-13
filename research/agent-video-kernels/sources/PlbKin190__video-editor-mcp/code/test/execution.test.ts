import test from 'node:test';
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { mkdtemp, rm } from 'node:fs/promises';
import { Workspace } from '../src/workspace.js';
import { execute, ffmpeg, probe, verify } from '../src/ffmpeg.js';
import { renderComposition } from '../src/engine.js';
import { compositionSchema } from '../src/composition.js';

const available = await promisify(execFile)('ffmpeg', ['-version']).then(() => true, () => false);
// drawtext needs an ffmpeg built with libfreetype. Homebrew's default build and
// several distribution packages ship without it, so the text case is skipped
// there rather than failing: the Docker image in this repository does have it.
const drawtext = available && await promisify(execFile)('ffmpeg', ['-hide_banner', '-filters'])
  .then(({ stdout }) => / drawtext /.test(stdout), () => false);

test('execution timeout kills ffmpeg and rejects', { skip: !available }, async () => {
  const directory = await mkdtemp('execution-test-');
  const workspace = await Workspace.create(directory);
  const job = await workspace.job();
  try {
    Object.defineProperty(job, 'deadline', { value: Date.now() + 150 });
    await assert.rejects(execute('ffmpeg', ['-nostdin', '-re', '-f', 'lavfi', '-i',
      'anullsrc=r=48000:cl=stereo', '-f', 'null', '-'], job));
  } finally { await job.close(); await rm(directory, { recursive: true, force: true }); }
});

test('synthetic composition preserves literal drawtext and produces bounded video/audio', { skip: !drawtext && 'ffmpeg built without drawtext (no libfreetype)' }, async () => {
  const directory = await mkdtemp('render-test-');
  const workspace = await Workspace.create(directory);
  const job = await workspace.job();
  try {
    await ffmpeg(['-f', 'lavfi', '-i', 'testsrc2=size=320x240:rate=30:duration=1',
      '-f', 'lavfi', '-i', 'sine=frequency=440:duration=1', '-c:v', 'libx264', '-threads', '1',
      '-c:a', 'aac', '-t', '1', 'source.mp4'], job, 'source.mp4');
    await job.publish('source.mp4', 'source.mp4');
  } finally { await job.close(); }
  const renderJob = await workspace.job();
  try {
    const composition = compositionSchema.parse({ frame: { width: 320, height: 240 }, shots: [{
      source: 'source.mp4', duration: 1, overlays: [{ kind: 'text',
        text: "Title: ' \\ %{pts} [v];", fontSize: 16, end: 1 }
      ]
    }] });
    const result = await renderComposition(composition, renderJob);
    await verify(result.file, 1, renderJob);
    const info = await probe({ file: result.file, format: 'mov' }, renderJob);
    assert.ok(info.tracks.some(t => t.type === 'audio'));
    assert.ok(info.tracks.some(t => t.width === 320 && t.height === 240));
    await renderJob.publish(result.file, 'final.mp4');
    await assert.rejects(renderJob.publish(result.file, 'final.mp4'));
  } finally { await renderJob.close(); await rm(directory, { recursive: true, force: true }); }
});
