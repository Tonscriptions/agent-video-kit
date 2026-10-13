import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { mkdtemp, mkdir, writeFile, symlink, rm, readFile } from 'node:fs/promises';
import { Workspace, validateRelative } from '../src/workspace.js';
import { textBytes, checkDuration, checkShots, checkSize } from '../src/guard.js';
import { config } from '../src/config.js';
import { compositionSchema } from '../src/composition.js';
import { trimSchema, trimTool } from '../src/tools/trim.js';
import { rational } from '../src/ffmpeg.js';
import { parseBlack, parseSilence } from '../src/tools/qa.js';

test('reject traversal, absolute paths, protocols and special syntax', () => {
  for (const name of ['../escape.mp4', 'sub/../escape.mp4', path.resolve('outside.mp4'), 'C:\\media.mp4',
    'https://example.invalid/a', 'file:clip.mp4', '.job-private/file.mp4', 'sub//clip.mp4', 'a;filter.mp4']) {
    assert.throws(() => validateRelative(name));
  }
  assert.deepEqual(validateRelative('clips/take-01.mp4'), ['clips', 'take-01.mp4']);
});

test('reject input and output symlinks, missing parents and existing outputs', async () => {
  const base = await mkdtemp('guard-test-');
  try {
    const root = path.join(base, 'workspace');
    const outside = path.join(base, 'outside');
    await mkdir(outside);
    await writeFile(path.join(outside, 'clip.mp4'), 'not media');
    const workspace = await Workspace.create(root);
    await symlink(path.resolve(outside), path.join(root, 'link'));
    await symlink(path.resolve(outside, 'clip.mp4'), path.join(root, 'file.mp4'));
    await assert.rejects(workspace.resolve('link/clip.mp4'));
    await assert.rejects(workspace.resolve('link/output.mp4', true));
    await assert.rejects(workspace.resolve('file.mp4'));
    await assert.rejects(workspace.resolve('file.mp4', true));
    await assert.rejects(workspace.resolve('missing/output.mp4', true));
    await writeFile(path.join(root, 'normal.mp4'), 'bytes');
    await assert.rejects(workspace.resolve('normal.mp4', true));
    assert.equal(await workspace.resolve('new.mp4', true), path.join(workspace.root, 'new.mp4'));
    const job = await workspace.job();
    try {
      const input = await job.stage('normal.mp4');
      assert.equal(await readFile(path.join(job.directory, input.file), 'utf8'), 'bytes');
    } finally { await job.close(); }
  } finally { await rm(base, { recursive: true, force: true }); }
});

test('drawtext textfile preserves quotes, colons, backslashes and expressions literally', () => {
  const text = "Editor's title: C:\\clips\\take %{pts} [v];movie=bad";
  assert.equal(textBytes(text).toString('utf8'), text);
  assert.throws(() => textBytes('bad\0text'));
  assert.throws(() => textBytes('x'.repeat(8193)));
});

test('strict schemas reject raw ffmpeg arguments at every level', () => {
  assert.equal(trimSchema.safeParse({ input: 'a.mp4', output: 'b.mp4', start: 0, duration: 1,
    args: ['-filter_complex', 'movie=bad'] }).success, false);
  assert.equal(compositionSchema.safeParse({ shots: [{ source: 'a.mp4', duration: 1, filter: 'null' }] }).success, false);
  assert.equal(compositionSchema.safeParse({ frame: { args: '-y' }, shots: [{ source: 'a.mp4', duration: 1 }] }).success, false);
  assert.equal(compositionSchema.safeParse({ shots: [{ source: 'a.mp4', duration: 1,
    overlays: [{ kind: 'text', text: 'Title', end: 1, x: '0;movie=bad' }] }] }).success, false);
  assert.equal(trimTool.schema.safeParse({ input: 'a.mp4', output: 'b.mp4', start: NaN, duration: 1 }).success, false);
});

test('duration, bytes, shot count and aggregate duration limits', () => {
  assert.throws(() => checkDuration(config.maxDuration + 1));
  assert.throws(() => checkDuration(Infinity));
  assert.throws(() => checkSize(config.maxBytes + 1));
  assert.throws(() => checkShots(config.maxShots + 1));
  checkDuration(config.maxDuration);
  checkSize(config.maxBytes);
  assert.equal(compositionSchema.safeParse({ shots: [
    { source: 'a.mp4', duration: config.maxDuration }, { source: 'b.mp4', duration: 1 }
  ] }).success, false);
  assert.equal(compositionSchema.safeParse({ shots: [{ source: 'a.mp4', duration: 1,
    overlays: [{ kind: 'text', text: 'Title', start: 0, end: 2 }] }] }).success, false);
});

test('frame rate parsing never evaluates expressions; QA preserves trailing silence', () => {
  assert.equal(rational('30000/1001'), 30000 / 1001);
  assert.equal(rational('0/0'), null);
  assert.equal(rational('process.exit()'), null);
  assert.deepEqual(parseBlack('black_start:1 black_end:2 black_duration:1'), [{ start: 1, end: 2, duration: 1 }]);
  assert.deepEqual(parseSilence('silence_start: 2', 4), [{ start: 2, end: 4 }]);
});
