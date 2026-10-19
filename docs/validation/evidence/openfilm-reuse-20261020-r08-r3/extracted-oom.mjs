import assert from 'node:assert/strict';
const OUT_OF_MEMORY = /malloc of size \d+ failed|cannot allocate memory|out of memory|exit 3221225495\b/i;
function outOfMemory(e, workers) {
  if (!(e instanceof Error) || !OUT_OF_MEMORY.test(e.message)) return e;
  const said = workers > 1
    ? `ffmpeg ran out of memory with ${workers} browsers rendering at once: try fewer, for example --workers ${Math.floor(workers / 2)}`
    : 'ffmpeg ran out of memory: close other apps and try again';
  return new Error(`${said}\n${e.message}`, { cause: e });
}
const cases = [
  ['malloc of size 123 failed', 4, /--workers 2/],
  ['cannot allocate memory', 2, /--workers 1/],
  ['out of memory', 1, /out of memory/],
  ['ffmpeg exit 3221225495', 4, /--workers 2/],
];
for (const [message, workers, expected] of cases) {
  const original = new Error(message), result = outOfMemory(original, workers);
  assert.match(result.message, expected); assert.equal(result.cause, original);
}
for (const value of [new Error('unknown encoder'), new Error('exit 3221225477'), 'out of memory', null]) {
  assert.equal(outOfMemory(value, 4), value);
}
console.log(JSON.stringify({cases: 8, scope: 'exact extracted pure helper; no encoder or browser executed'}));
