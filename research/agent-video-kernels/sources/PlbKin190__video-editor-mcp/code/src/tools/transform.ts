import { z } from 'zod';
import { mediaPath, outputPath } from '../guard.js';
import { frameSchema, shotSchema } from '../composition.js';
import { boundedVideo } from '../ffmpeg.js';
import { renderShot } from '../engine.js';
import { defineTool } from './types.js';
export const transformTool = defineTool('transform', 'Resize, crop or pad a video to a ratio or explicit even dimensions.',
  z.object({ input: mediaPath, output: outputPath, frame: frameSchema }).strict(), async ({ input, output, frame }, job) => {
    await job.workspace.resolve(output, true);
    const info = await boundedVideo(await job.stage(input), job);
    await renderShot(shotSchema.parse({ source: input, duration: info.duration }), frame, job, 'result.mp4');
    await job.publish('result.mp4', output);
    return { output };
  });
