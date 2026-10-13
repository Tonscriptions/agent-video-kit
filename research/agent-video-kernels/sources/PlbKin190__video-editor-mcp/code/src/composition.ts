import { z } from 'zod';
import { config } from './config.js';
import { seconds, duration, mediaPath, dimension, fpsSchema, textSchema } from './guard.js';

export const frameSchema = z.object({
  ratio: z.enum(['16:9', '9:16', '1:1']).default('16:9'),
  width: dimension.optional(), height: dimension.optional(),
  fit: z.enum(['pad', 'crop']).default('pad'),
  fps: fpsSchema.default(30),
  crop: z.object({ width: dimension, height: dimension,
    x: z.number().int().min(0).max(4096), y: z.number().int().min(0).max(4096) }).strict().optional()
}).strict().refine(f => (f.width === undefined) === (f.height === undefined), 'Supply both dimensions');
export type Frame = z.infer<typeof frameSchema>;
export function dimensions(frame: Frame): [number, number] {
  if (frame.width !== undefined && frame.height !== undefined) return [frame.width, frame.height];
  return frame.ratio === '9:16' ? [720, 1280] : frame.ratio === '1:1' ? [720, 720] : [1280, 720];
}
const placement = {
  x: z.number().int().min(0).max(1920).default(40),
  y: z.number().int().min(0).max(1920).default(40),
  start: seconds.default(0), end: duration
};
export const overlaySchema = z.discriminatedUnion('kind', [
  z.object({ kind: z.literal('text'), text: textSchema,
    fontSize: z.number().int().min(8).max(200).default(48),
    color: z.enum(['white', 'black', 'yellow', 'red']).default('white'), ...placement }).strict(),
  z.object({ kind: z.literal('image'), source: mediaPath,
    width: dimension.default(160), ...placement }).strict()
]);
export type Overlay = z.infer<typeof overlaySchema>;
export const audioTrackSchema = z.object({
  source: mediaPath, start: seconds.default(0),
  volume: z.number().finite().min(0).max(2).default(1),
  fadeIn: seconds.default(0), fadeOut: seconds.default(0)
}).strict();
export type AudioTrack = z.infer<typeof audioTrackSchema>;
export const shotSchema = z.object({
  source: mediaPath, start: seconds.default(0), duration,
  overlays: z.array(overlaySchema).max(8).default([]),
  audio: audioTrackSchema.optional(),
  sourceVolume: z.number().finite().min(0).max(2).default(1)
}).strict();
export type Shot = z.infer<typeof shotSchema>;
export const compositionSchema = z.object({
  frame: frameSchema.default({}),
  shots: z.array(shotSchema).min(1).max(config.maxShots),
  music: audioTrackSchema.optional(),
  normalize: z.boolean().default(true),
  targetLufs: z.number().finite().min(-30).max(-10).default(-16)
}).strict().superRefine((c, ctx) => {
  if (c.shots.reduce((sum, s) => sum + s.duration, 0) > config.maxDuration)
    ctx.addIssue({ code: 'custom', message: 'Composition duration limit' });
  for (const shot of c.shots) {
    if (shot.overlays.some(o => o.end <= o.start || o.end > shot.duration))
      ctx.addIssue({ code: 'custom', message: 'Invalid overlay window' });
  }
});
export type Composition = z.infer<typeof compositionSchema>;
