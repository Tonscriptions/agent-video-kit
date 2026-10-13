import { z } from 'zod';
import { config } from '../config.js';
import { mediaPath, outputPath } from '../guard.js';
import { frameSchema, compositionSchema } from '../composition.js';
import { boundedVideo } from '../ffmpeg.js';
import { renderComposition } from '../engine.js';
import { defineTool } from './types.js';
export const concatTool = defineTool('concat', 'Concatenate complete clips with normalized geometry, frame rate and audio; re-encodes.',
  z.object({ inputs: z.array(mediaPath).min(1).max(config.maxShots), output: outputPath, frame: frameSchema.default({}) }).strict(),
  async ({ inputs, output, frame }, job) => {
    await job.workspace.resolve(output, true);
    const shots: { source: string; duration: number }[] = [];
    for (const source of inputs) {
      const info = await boundedVideo(await job.stage(source), job);
      shots.push({ source, duration: info.duration });
    }
    const result = await renderComposition(compositionSchema.parse({ frame, shots, normalize: false }), job);
    await job.publish(result.file, output);
    return { output, duration: result.duration };
  });
