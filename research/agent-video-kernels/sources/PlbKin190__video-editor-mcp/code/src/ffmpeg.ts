import { execFile } from 'node:child_process';
import { statSync } from 'node:fs';
import path from 'node:path';
import { z } from 'zod';
import { config } from './config.js';
import { checkDuration } from './guard.js';
import type { Job } from './workspace.js';

export interface Input { file: string; format: string }
export function inputArgs(input: Input): string[] {
  // Force self-contained demuxers: renamed playlists cannot open secondary files.
  return ['-protocol_whitelist', 'file', '-f', input.format, '-threads', String(config.threads), '-i', input.file];
}

export async function execute(binary: 'ffmpeg' | 'ffprobe', args: string[], job: Job, output?: string): Promise<{ stdout: string; stderr: string }> {
  const remaining = job.deadline - Date.now();
  if (remaining <= 0) throw new Error('Deadline');
  return new Promise((resolve, reject) => {
    let violated = false;
    // No shell, no command-string interpolation. Executables are fixed, not client options.
    const child = execFile(binary, args, {
      cwd: job.directory, encoding: 'utf8', timeout: remaining,
      killSignal: 'SIGKILL', maxBuffer: 8 * 1024 * 1024,
      env: { ...process.env, LC_ALL: 'C', AV_LOG_FORCE_NOCOLOR: '1' }
    }, (error, stdout, stderr) => {
      clearInterval(watcher);
      if (stderr) process.stderr.write(stderr);
      if (error || violated) reject(new Error('Media execution failed'));
      else resolve({ stdout, stderr });
    });
    // -fs alone can silently produce a truncated file. Watch, kill, and reject;
    // final stat/probe checks cover short processes that finish between polls.
    const watcher = setInterval(() => {
      if (!output) return;
      try {
        if (statSync(path.join(job.directory, output)).size >= config.maxBytes) {
          violated = true;
          child.kill('SIGKILL');
        }
      } catch { /* Output may not exist yet. */ }
    }, 25);
  });
}

export async function ffmpeg(args: string[], job: Job, output?: string): Promise<string> {
  const base = ['-hide_banner', '-nostdin', '-n', '-loglevel', 'info',
    '-filter_threads', String(config.threads), '-filter_complex_threads', String(config.threads)];
  const { stderr } = await execute('ffmpeg', [...base, ...args], job, output);
  return stderr;
}

const probeSchema = z.object({
  format: z.object({ duration: z.string().optional() }).optional(),
  streams: z.array(z.object({
    index: z.number(), codec_type: z.string().optional(), codec_name: z.string().optional(),
    width: z.number().optional(), height: z.number().optional(),
    avg_frame_rate: z.string().optional(), sample_rate: z.string().optional(), channels: z.number().optional()
  }))
});
export function rational(value: string | undefined): number | null {
  if (!value || !/^\d+\/\d+$/.test(value)) return null;
  const [a, b] = value.split('/').map(Number);
  return b > 0 ? a / b : null;
}
export async function probe(input: Input, job: Job) {
  const { stdout } = await execute('ffprobe', ['-v', 'error', '-protocol_whitelist', 'file',
    '-f', input.format, '-show_entries',
    'format=duration:stream=index,codec_type,codec_name,width,height,avg_frame_rate,sample_rate,channels',
    '-of', 'json', input.file], job);
  const data = probeSchema.parse(JSON.parse(stdout) as unknown);
  const value = Number(data.format?.duration);
  return {
    duration: Number.isFinite(value) && value > 0 ? value : null,
    tracks: data.streams.map(s => ({ index: s.index, type: s.codec_type, codec: s.codec_name,
      width: s.width, height: s.height, fps: rational(s.avg_frame_rate),
      sampleRate: s.sample_rate ? Number(s.sample_rate) : undefined, channels: s.channels }))
  };
}
export type MediaInfo = Awaited<ReturnType<typeof probe>>;
export async function boundedVideo(input: Input, job: Job): Promise<MediaInfo & { duration: number }> {
  const info = await probe(input, job);
  if (info.duration === null || !info.tracks.some(s => s.type === 'video')) throw new Error('Video required');
  checkDuration(info.duration);
  const video = info.tracks.find(s => s.type === 'video');
  if ((video?.width ?? 0) > 4096 || (video?.height ?? 0) > 4096) throw new Error('Input resolution limit');
  return { ...info, duration: info.duration };
}
export const codecs = ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22', '-pix_fmt', 'yuv420p',
  '-threads', String(config.threads), '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2'];
export function outputArgs(duration: number, file: string): string[] {
  checkDuration(duration);
  return ['-t', String(duration), '-fs', String(config.maxBytes), '-map_metadata', '-1',
    '-map_chapters', '-1', '-movflags', '+faststart', '-f', 'mp4', file];
}
export async function verify(file: string, expected: number, job: Job): Promise<MediaInfo> {
  if (statSync(path.join(job.directory, file)).size >= config.maxBytes) throw new Error('Output file limit');
  const info = await probe({ file, format: 'mov' }, job);
  if (info.duration === null || info.duration > config.maxDuration + 0.05 || Math.abs(info.duration - expected) > 0.15) throw new Error('Output duration mismatch');
  return info;
}
