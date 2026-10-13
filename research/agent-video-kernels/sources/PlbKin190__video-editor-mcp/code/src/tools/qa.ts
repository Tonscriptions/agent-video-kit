import { z } from 'zod';
import { mediaPath, duration, dimension, fpsSchema } from '../guard.js';
import { boundedVideo, inputArgs, ffmpeg } from '../ffmpeg.js';
import { defineTool } from './types.js';

export function parseBlack(log: string): { start: number; end: number; duration: number }[] {
  return [...log.matchAll(/black_start:([\d.]+)\s+black_end:([\d.]+)\s+black_duration:([\d.]+)/g)]
    .map(m => ({ start: Number(m[1]), end: Number(m[2]), duration: Number(m[3]) }));
}
export function parseSilence(log: string, length: number): { start: number; end: number }[] {
  const windows: { start: number; end: number }[] = [];
  let start: number | undefined;
  for (const match of log.matchAll(/silence_(start|end):\s*([\d.]+)/g)) {
    if (match[1] === 'start') start = Number(match[2]);
    else if (start !== undefined) { windows.push({ start, end: Number(match[2]) }); start = undefined; }
  }
  if (start !== undefined) windows.push({ start, end: length });
  return windows;
}
export const qaTool = defineTool('qa', 'Measure duration, black intervals, silence, integrated LUFS, resolution and FPS. Failed analysis is an error, not a pass.',
  z.object({ input: mediaPath, expectedDuration: duration,
    durationTolerance: z.number().finite().min(0).max(2).default(0.15),
    expectedWidth: dimension.optional(), expectedHeight: dimension.optional(), expectedFps: fpsSchema.optional(),
    targetLufs: z.number().finite().min(-30).max(-10).default(-16),
    lufsTolerance: z.number().finite().min(0).max(10).default(2),
    blackMinDuration: z.number().finite().min(0.01).max(10).default(0.1),
    silenceMinDuration: z.number().finite().min(0.01).max(10).default(0.5),
    silenceDb: z.number().finite().min(-90).max(-10).default(-40)
  }).strict(), async (p, job) => {
    const input = await job.stage(p.input);
    const info = await boundedVideo(input, job);
    const video = info.tracks.find(t => t.type === 'video');
    const hasAudio = info.tracks.some(t => t.type === 'audio');
    const args = [...inputArgs(input), '-map', '0:v:0', '-vf', `blackdetect=d=${p.blackMinDuration}:pic_th=0.98:pix_th=0.10`];
    if (hasAudio) args.push('-map', '0:a:0', '-af', `silencedetect=noise=${p.silenceDb}dB:d=${p.silenceMinDuration},loudnorm=I=${p.targetLufs}:TP=-1.5:LRA=11:print_format=json`);
    args.push('-t', String(info.duration), '-f', 'null', '-');
    const log = await ffmpeg(args, job);
    const black = parseBlack(log);
    const silence = hasAudio ? parseSilence(log, info.duration) : null;
    const rawLufs = log.match(/"input_i"\s*:\s*"([^"]+)"/)?.[1];
    if (hasAudio && rawLufs === undefined) throw new Error('Loudness analysis incomplete');
    const lufs = rawLufs !== undefined && Number.isFinite(Number(rawLufs)) ? Number(rawLufs) : null;
    const checks = {
      duration: Math.abs(info.duration - p.expectedDuration) <= p.durationTolerance,
      resolution: (p.expectedWidth === undefined || video?.width === p.expectedWidth) && (p.expectedHeight === undefined || video?.height === p.expectedHeight),
      fps: p.expectedFps === undefined ? null : video?.fps !== null && video?.fps !== undefined && Math.abs(video.fps - p.expectedFps) < 0.05,
      noBlack: black.length === 0,
      noSilence: hasAudio ? silence?.length === 0 : false,
      loudness: lufs !== null && Math.abs(lufs - p.targetLufs) <= p.lufsTolerance
    };
    return { media: info, black, silence, integratedLufs: lufs,
      loudnessStatus: !hasAudio ? 'no-audio' : lufs === null ? 'below-measurable-range' : 'measured',
      checks, passed: Object.values(checks).every(v => v !== false) };
  });
