import { readFile } from 'node:fs/promises';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';

const client = new Client({ name: 'video-editor-demo', version: '0.1.0' });
const transport = new StdioClientTransport({ command: 'docker', args: ['compose', 'run', '--rm', '--no-deps', '-T', 'mcp'], stderr: 'inherit' });
try {
  await client.connect(transport);
  const composition: unknown = JSON.parse(await readFile('examples/composition.json', 'utf8'));
  const health = await client.callTool({ name: 'health', arguments: {} });
  console.log(JSON.stringify(health));
  const render = await client.callTool({ name: 'render', arguments: { composition, output: 'demo.mp4' } });
  console.log(JSON.stringify(render));
  if (render.isError) throw new Error('Render failed');
  console.log(JSON.stringify(await client.callTool({ name: 'qa', arguments: {
    input: 'demo.mp4', expectedDuration: 8, expectedWidth: 720, expectedHeight: 1280, expectedFps: 30, targetLufs: -16
  } })));
} finally { await client.close(); }
