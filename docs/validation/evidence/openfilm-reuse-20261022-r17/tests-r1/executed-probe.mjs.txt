// Execute the pinned upstream IPC worker with an explicitly fake renderer and no browser host.
import assert from 'node:assert/strict';
import { fork } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = dirname(fileURLToPath(import.meta.url));
const worker = resolve(root, 'packages/openfilm/studio/server/render-worker.mjs');
const cases = [
  ['success', 'done', 1],
  ['browser_once', 'done', 2],
  ['buffers_once', 'done', 2],
  ['browser_always', 'failed', 2],
  ['missing_file', 'failed', 1],
  ['page_error', 'failed', 1],
  ['busy_loop', 'failed', 1],
  ['encoder', 'failed', 1],
  ['non_error', 'failed', 1],
  ['cancelled', 'failed', 1],
];
const observations = [];
for (const pooled of [false, true]) {
  for (const [scenario, expectedType, expectedAttempts] of cases) {
    const child = fork(worker, pooled ? ['--pool'] : [], {
      cwd: root, execArgv: [], windowsHide: true, silent: true,
      env: { ...process.env, OPENFILM_AUDIT_SCENARIO: scenario },
    });
    const attempts = [], messages = [];
    let stderr = '', stdout = '';
    child.stderr.on('data', d => { stderr += String(d); assert.ok(stderr.length < 65536); });
    child.stdout.on('data', d => { stdout += String(d); assert.ok(stdout.length < 65536); });
    let terminal;
    const exit = new Promise((ok, no) => {
      const timer = setTimeout(() => { child.kill(); no(new Error(`Owned fake worker timed out: ${scenario}`)); }, 12000);
      child.once('error', e => { clearTimeout(timer); no(e); });
      child.once('exit', (code, signal) => { clearTimeout(timer); ok({ code, signal }); });
    });
    child.on('message', message => {
      messages.push(message);
      if (message.type === 'audit-attempt') {
        attempts.push(message.attempt);
        if (scenario === 'cancelled') child.send(pooled ? {type:'cancel',id:'audit'} : {type:'cancel'});
      }
      if (message.type === 'done' || message.type === 'failed') {
        terminal = message;
        if (pooled) child.send({type:'close'});
      }
    });
    try {
      child.send(pooled ? {type:'render',id:'audit',args:['fake'],opts:{}} : {args:['fake'],opts:{}});
      const ended = await exit;
      assert.equal(terminal?.type, expectedType, `${scenario}: ${stderr}`);
      assert.equal(attempts.length, expectedAttempts, scenario);
      assert.deepEqual(attempts, Array.from({length:expectedAttempts}, (_,i) => i + 1));
      assert.equal(ended.code, pooled || expectedType === 'done' ? 0 : 1);
      assert.equal(ended.signal, null);
      assert.equal((stderr.match(/drawn again/g) || []).length, expectedAttempts - 1);
      assert.equal(stdout, '');
      observations.push({mode:pooled?'pool':'single',scenario,terminal,attempts,exit:ended,
        retry_messages:expectedAttempts-1,stderr,messages});
    } finally {
      if (child.exitCode === null && child.signalCode === null) child.kill();
    }
  }
}
console.log(JSON.stringify({status:'passed-pinned-worker-with-fake-renderer',observations,
  upstream_worker_body_modified:false,actual_browser_launched:false,actual_render_executed:false,
  worker_bytes:readFileSync(worker).length}, null, 2));
