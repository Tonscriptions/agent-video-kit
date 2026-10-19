import http from 'node:http';
import https from 'node:https';
import net from 'node:net';
import tls from 'node:tls';
import cp from 'node:child_process';
import { appendFileSync } from 'node:fs';
import { syncBuiltinESMExports } from 'node:module';
const deny = (what) => (...args) => {
  appendFileSync(process.env.AVK_R09_GUARD_LOG, JSON.stringify({ denied: what }) + '\n');
  throw new Error('R09 source-review guard: ' + what);
};
globalThis.fetch = deny('fetch');
for (const [label, mod, names] of [
  ['http', http, ['request', 'get', 'createServer']],
  ['https', https, ['request', 'get', 'createServer']],
  ['net', net, ['connect', 'createConnection', 'createServer']],
  ['tls', tls, ['connect', 'createServer']],
  ['child_process', cp, ['spawn', 'spawnSync', 'exec', 'execSync', 'execFile', 'execFileSync', 'fork']],
]) for (const name of names) mod[name] = deny(label + '.' + name);
syncBuiltinESMExports();
