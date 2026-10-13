import { z } from 'zod';
import { mediaPath } from '../guard.js';
import { probe } from '../ffmpeg.js';
import { defineTool } from './types.js';
export const probeTool = defineTool('probe', 'Inspect duration, tracks, codecs, resolution and frame rate.',
  z.object({ input: mediaPath }).strict(), async ({ input }, job) => probe(await job.stage(input), job));
