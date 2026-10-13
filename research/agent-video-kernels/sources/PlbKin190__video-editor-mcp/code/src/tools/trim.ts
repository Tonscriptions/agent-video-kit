import { z } from 'zod';
import { mediaPath, outputPath, seconds, duration } from '../guard.js';
import { boundedVideo, inputArgs, codecs, outputArgs, ffmpeg, verify } from '../ffmpeg.js';
import { defineTool } from './types.js';
export const trimSchema = z.object({ input: mediaPath, output: outputPath, start: seconds, duration,
  mode: z.enum(['auto', 'copy', 'accurate']).default('auto') }).strict();
export const trimTool = defineTool('trim', 'Trim video. Auto attempts stream copy, then falls back to encoding; copy is keyframe-aligned.',
  trimSchema, async (params, job) => {
    await job.workspace.resolve(params.output, true);
    const input = await job.stage(params.input);
    const info = await boundedVideo(input, job);
    if (params.start + params.duration > info.duration + 0.05) throw new Error('Trim exceeds source');
    let file = 'encoded.mp4';
    let copied = false;
    if (params.mode !== 'accurate') {
      try {
        await ffmpeg(['-ss', String(params.start), ...inputArgs(input), '-map', '0:v:0', '-map', '0:a:0?',
          '-c', 'copy', ...outputArgs(params.duration, 'copy.mp4')], job, 'copy.mp4');
        await verify('copy.mp4', params.duration, job);
        file = 'copy.mp4'; copied = true;
      } catch (error: unknown) { if (params.mode === 'copy') throw error; }
    }
    if (!copied) {
      await ffmpeg([...inputArgs(input), '-ss', String(params.start), '-map', '0:v:0', '-map', '0:a:0?',
        ...codecs, ...outputArgs(params.duration, file)], job, file);
      await verify(file, params.duration, job);
    }
    await job.publish(file, params.output);
    return { output: params.output, streamCopy: copied, timing: copied ? 'keyframe-aligned' : 'frame-accurate' };
  });
