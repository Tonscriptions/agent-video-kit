import { z } from 'zod';
import { statfs } from 'node:fs/promises';
import { execute } from '../ffmpeg.js';
import { config } from '../config.js';
import { defineTool } from './types.js';
export const healthTool = defineTool('health', 'Report ffmpeg/ffprobe versions, available encoders and workspace free space.',
  z.object({}).strict(), async (_input, job) => {
    const version = await execute('ffmpeg', ['-version'], job);
    const probe = await execute('ffprobe', ['-version'], job);
    const encoderList = await execute('ffmpeg', ['-hide_banner', '-encoders'], job);
    const space = await statfs(job.workspace.root);
    const encoders = encoderList.stdout.split('\n').flatMap(line => {
      const match = line.match(/^\s+[VAS][A-Z.]{5}\s+(\S+)/);
      return match && match[1] !== '=' ? [match[1]] : [];
    });
    return { ffmpeg: version.stdout.split('\n')[0], ffprobe: probe.stdout.split('\n')[0], encoders,
      freeBytes: space.bavail * space.bsize,
      limits: { durationSeconds: config.maxDuration, fileBytes: config.maxBytes, timeoutMs: config.timeoutMs, shots: config.maxShots } };
  });
