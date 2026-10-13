import { z } from 'zod';
import { outputPath } from '../guard.js';
import { compositionSchema } from '../composition.js';
import { renderComposition } from '../engine.js';
import { defineTool } from './types.js';
export const renderTool = defineTool('render', 'Render ordered shots, local overlays, per-shot audio and optional music to MP4.',
  z.object({ composition: compositionSchema, output: outputPath }).strict(), async ({ composition, output }, job) => {
    await job.workspace.resolve(output, true);
    const result = await renderComposition(composition, job);
    await job.publish(result.file, output);
    return { output, duration: result.duration };
  });
