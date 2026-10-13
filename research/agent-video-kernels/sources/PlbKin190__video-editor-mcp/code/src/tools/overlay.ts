import { z } from 'zod';
import { mediaPath, outputPath, seconds } from '../guard.js';
import { frameSchema, overlaySchema, shotSchema } from '../composition.js';
import { boundedVideo } from '../ffmpeg.js';
import { renderShot } from '../engine.js';
import { defineTool } from './types.js';
export const overlayTool = defineTool('overlay', 'Burn typed text or a local raster image into a video during a time window.',
  z.object({ input: mediaPath, output: outputPath, start: seconds.default(0),
    overlay: overlaySchema, frame: frameSchema.default({}) }).strict(), async ({ input, output, start, overlay, frame }, job) => {
    await job.workspace.resolve(output, true);
    const info = await boundedVideo(await job.stage(input), job);
    const length = info.duration - start;
    await renderShot(shotSchema.parse({ source: input, start, duration: length, overlays: [overlay] }), frame, job, 'result.mp4');
    await job.publish('result.mp4', output);
    return { output };
  });
