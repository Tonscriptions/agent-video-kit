import path from 'node:path';
import { writeFile } from 'node:fs/promises';
import type { Job } from './workspace.js';
import { textBytes, checkDuration, checkShots } from './guard.js';
import { dimensions, type Frame, type Shot, type AudioTrack, type Composition } from './composition.js';
import { inputArgs, ffmpeg, boundedVideo, probe, codecs, outputArgs, verify, type Input } from './ffmpeg.js';

export function frameFilter(frame: Frame): string {
  const [w, h] = dimensions(frame);
  const crop = frame.crop ? `crop=${frame.crop.width}:${frame.crop.height}:${frame.crop.x}:${frame.crop.y},` : '';
  const sizing = frame.fit === 'pad'
    ? `scale=${w}:${h}:force_original_aspect_ratio=decrease,pad=${w}:${h}:(ow-iw)/2:(oh-ih)/2:black`
    : `scale=${w}:${h}:force_original_aspect_ratio=increase,crop=${w}:${h}`;
  return `${crop}${sizing},setsar=1,fps=${frame.fps},format=yuv420p`;
}
export function audioFilter(track: Pick<AudioTrack, 'start' | 'volume' | 'fadeIn' | 'fadeOut'>, length: number): string {
  if (track.fadeIn > length || track.fadeOut > length) throw new Error('Invalid fade');
  let result = `atrim=start=${track.start}:duration=${length},asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo,volume=${track.volume},apad,atrim=duration=${length}`;
  if (track.fadeIn > 0) result += `,afade=t=in:st=0:d=${track.fadeIn}`;
  if (track.fadeOut > 0) result += `,afade=t=out:st=${length - track.fadeOut}:d=${track.fadeOut}`;
  return result;
}
export async function stageAudio(track: AudioTrack, job: Job): Promise<Input> {
  const input = await job.stage(track.source);
  const info = await probe(input, job);
  if (!info.tracks.some(t => t.type === 'audio') || info.duration === null || track.start >= info.duration) throw new Error('Audio required');
  return input;
}

export async function renderShot(shot: Shot, frame: Frame, job: Job, file: string): Promise<void> {
  checkDuration(shot.duration);
  const input = await job.stage(shot.source);
  const info = await boundedVideo(input, job);
  if (shot.start + shot.duration > info.duration + 0.05) throw new Error('Trim exceeds source');
  const args = inputArgs(input);
  const filters: string[] = [`[0:v:0]trim=start=${shot.start}:duration=${shot.duration},setpts=PTS-STARTPTS,${frameFilter(frame)}[v0]`];
  let inputIndex = 1;
  let video = 'v0';
  for (let i = 0; i < shot.overlays.length; i++) {
    const overlay = shot.overlays[i];
    if (overlay.end <= overlay.start || overlay.end > shot.duration) throw new Error('Overlay window');
    const next = `v${i + 1}`;
    const enable = `enable='between(t,${overlay.start},${overlay.end})'`;
    if (overlay.kind === 'text') {
      // Generated basename only; text never enters the filter parser, including
      // quotes, colons, backslashes and %{...} expansion syntax.
      const textFile = `title-${file.replace(/[^a-z0-9]/g, '')}-${i}.txt`;
      await writeFile(path.join(job.directory, textFile), textBytes(overlay.text), { flag: 'wx', mode: 0o600 });
      filters.push(`[${video}]drawtext=font=DejaVuSans:textfile=${textFile}:expansion=none:fontsize=${overlay.fontSize}:fontcolor=${overlay.color}:x=${overlay.x}:y=${overlay.y}:box=1:boxcolor=black@0.5:${enable}[${next}]`);
    } else {
      if (!/\.(png|jpg|jpeg)$/i.test(overlay.source)) throw new Error('Raster image required');
      const image = await job.stage(overlay.source);
      args.push(...inputArgs(image));
      filters.push(`[${inputIndex++}:v:0]scale=${overlay.width}:-2[image${i}]`);
      filters.push(`[${video}][image${i}]overlay=x=${overlay.x}:y=${overlay.y}:eof_action=repeat:${enable}[${next}]`);
    }
    video = next;
  }
  let audio: string;
  let track: Pick<AudioTrack, 'start' | 'volume' | 'fadeIn' | 'fadeOut'>;
  if (shot.audio) {
    args.push(...inputArgs(await stageAudio(shot.audio, job)));
    audio = `${inputIndex++}:a:0`;
    track = shot.audio;
  } else if (info.tracks.some(t => t.type === 'audio')) {
    audio = '0:a:0';
    track = { start: shot.start, volume: shot.sourceVolume, fadeIn: 0, fadeOut: 0 };
  } else {
    args.push('-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo');
    audio = `${inputIndex++}:a:0`;
    track = { start: 0, volume: 1, fadeIn: 0, fadeOut: 0 };
  }
  filters.push(`[${audio}]${audioFilter(track, shot.duration)}[a]`);
  args.push('-filter_complex', filters.join(';'), '-map', `[${video}]`, '-map', '[a]', ...codecs, ...outputArgs(shot.duration, file));
  await ffmpeg(args, job, file);
  await verify(file, shot.duration, job);
}

export async function renderComposition(composition: Composition, job: Job): Promise<{ file: string; duration: number }> {
  checkShots(composition.shots.length);
  const length = composition.shots.reduce((sum, s) => sum + s.duration, 0);
  checkDuration(length);
  const args: string[] = [];
  for (let i = 0; i < composition.shots.length; i++) {
    const file = `shot-${i}.mp4`;
    await renderShot(composition.shots[i], composition.frame, job, file);
    args.push(...inputArgs({ file, format: 'mov' }));
  }
  const filters: string[] = [];
  // AAC padding is explicitly trimmed before concat to avoid cumulative drift.
  for (let i = 0; i < composition.shots.length; i++) {
    filters.push(`[${i}:v:0]trim=duration=${composition.shots[i].duration},setpts=PTS-STARTPTS[v${i}]`);
    filters.push(`[${i}:a:0]atrim=duration=${composition.shots[i].duration},asetpts=PTS-STARTPTS[a${i}]`);
  }
  const labels = composition.shots.map((_, i) => `[v${i}][a${i}]`).join('');
  filters.push(`${labels}concat=n=${composition.shots.length}:v=1:a=1[v][voice]`);
  let audio = 'voice';
  if (composition.music) {
    args.push(...inputArgs(await stageAudio(composition.music, job)));
    filters.push(`[${composition.shots.length}:a:0]${audioFilter(composition.music, length)}[music]`);
    filters.push('[voice][music]amix=inputs=2:duration=first:normalize=0[mix]');
    audio = 'mix';
  }
  filters.push(`[${audio}]${composition.normalize ? `loudnorm=I=${composition.targetLufs}:TP=-1.5:LRA=11,` : ''}alimiter=limit=0.95:level=0:latency=1[a]`);
  const file = 'result.mp4';
  args.push('-filter_complex', filters.join(';'), '-map', '[v]', '-map', '[a]', ...codecs, ...outputArgs(length, file));
  await ffmpeg(args, job, file);
  await verify(file, length, job);
  return { file, duration: length };
}
