import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import { zodToJsonSchema } from 'zod-to-json-schema';
import { config } from './config.js';
import { Workspace } from './workspace.js';
import { probeTool } from './tools/probe.js';
import { trimTool } from './tools/trim.js';
import { concatTool } from './tools/concat.js';
import { transformTool } from './tools/transform.js';
import { overlayTool } from './tools/overlay.js';
import { audioMixTool } from './tools/audio_mix.js';
import { renderTool } from './tools/render.js';
import { qaTool } from './tools/qa.js';
import { healthTool } from './tools/health.js';

async function main(): Promise<void> {
  const workspace = await Workspace.create();
  const tools = [probeTool, trimTool, concatTool, transformTool, overlayTool, audioMixTool, renderTool, qaTool, healthTool];
  const server = new Server({ name: 'video-editor-mcp', version: '0.1.0' }, { capabilities: { tools: {} } });
  // Low-level dispatch keeps strict validation in our own boundary. Unknown keys
  // are rejected (never stripped before guards), and validation errors stay generic.
  server.setRequestHandler(ListToolsRequestSchema, async () => ({
    tools: tools.map(tool => ({ name: tool.name, description: tool.description,
      inputSchema: { ...zodToJsonSchema(tool.schema, { $refStrategy: 'none' }), type: 'object' as const } }))
  }));
  type ToolResult = { isError?: boolean; content: { type: 'text'; text: string }[] };
  const runTool = async (request: { params: { name: string; arguments?: unknown } }): Promise<ToolResult> => {
    try {
      const tool = tools.find(t => t.name === request.params.name);
      if (!tool) throw new Error('Unknown tool');
      const input = tool.schema.parse(request.params.arguments ?? {});
      const job = await workspace.job();
      try {
        const result = await tool.run(input, job);
        return { content: [{ type: 'text' as const, text: JSON.stringify(result) }] };
      } finally { await job.close(); }
    } catch (error: unknown) {
      console.error('Tool rejected or failed:', error);
      return { isError: true, content: [{ type: 'text' as const, text: 'Operation rejected or failed. Check server stderr.' }] };
    }
  };

  // ffmpeg saturates the CPU, so jobs run one at a time. They are QUEUED, not
  // refused: a client that issues several calls before the first returns is
  // normal, and an error there would just be retried. Only an unreasonable
  // backlog is rejected, so the queue cannot grow without bound.
  let chain: Promise<void> = Promise.resolve();
  let queued = 0;
  server.setRequestHandler(CallToolRequestSchema, async request => {
    if (queued >= config.maxQueued) {
      return { isError: true, content: [{ type: 'text' as const, text: 'Too many queued jobs. Retry later.' }] };
    }
    queued += 1;
    const result = chain.then(() => runTool(request));
    // Swallow on the chain only: the caller still receives `result` itself.
    chain = result.then(() => undefined, () => undefined).finally(() => { queued -= 1; });
    return result;
  });
  await server.connect(new StdioServerTransport());
  console.error('video-editor-mcp ready');
}
main().catch((error: unknown) => { console.error('Startup failed:', error); process.exitCode = 1; });
