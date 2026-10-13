import { z } from 'zod';
import { mediaPath, outputPath } from '../guard.js';
import { audioTrackSchema } from '../composition.js';
import { boundedVideo, inputArgs, ffmpeg, outputArgs, verify } from '../ffmpeg.js';
import { audioFilter, stageAudio } from '../engine.js';
import { defineTool } from './types.js';
export const audioMixTool = defineTool('audio_mix', 'Mix music under source audio or a separate voice track, with gain, fades and optional loudness normalization.',
  z.object({ input: mediaPath, output: outputPath, voice: audioTrackSchema.optional(), music: audioTrackSchema,
    voiceVolume: z.number().finite().min(0).max(2).default(1), normalize: z.boolean().default(true),
    targetLufs: z.number().finite().min(-30).max(-10).default(-16) }).strict(), async (p, job) => {
    await job.workspace.resolve(p.output, true);
    const input = await job.stage(p.input);
    const info = await boundedVideo(input, job);
    const args = inputArgs(input);
    let voice = '0:a:0';
    let musicIndex = 1;
    if (p.voice) { args.push(...inputArgs(await stageAudio(p.voice, job))); voice = '1:a:0'; musicIndex++; }
    else if (!info.tracks.some(t => t.type === 'audio')) throw new Error('Voice required');
    args.push(...inputArgs(await stageAudio(p.music, job)));
    const voiceTrack = p.voice ?? { start: 0, volume: p.voiceVolume, fadeIn: 0, fadeOut: 0 };
    const filters = [`[${voice}]${audioFilter(voiceTrack, info.duration)}[voice]`,
      `[${musicIndex}:a:0]${audioFilter(p.music, info.duration)}[music]`,
      `[voice][music]amix=inputs=2:duration=first:normalize=0,${p.normalize ? `loudnorm=I=${p.targetLufs}:TP=-1.5:LRA=11,` : ''}alimiter=limit=0.95:level=0:latency=1[a]`];
    const file = 'result.mp4';
    await ffmpeg([...args, '-filter_complex', filters.join(';'), '-map', '0:v:0', '-map', '[a]',
      '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2', ...outputArgs(info.duration, file)], job, file);
    await verify(file, info.duration, job);
    await job.publish(file, p.output);
    return { output: p.output };
  });
