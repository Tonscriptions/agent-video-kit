import { z } from 'zod';
import { config } from './config.js';

export const seconds = z.number().finite().nonnegative().max(config.maxDuration);
export const duration = seconds.refine(n => n > 0);
export const mediaPath = z.string().min(1).max(240);
export const outputPath = mediaPath.refine(p => p.endsWith('.mp4'));
export const dimension = z.number().int().min(16).max(1920).refine(n => n % 2 === 0);
export const fpsSchema = z.number().int().min(1).max(60);

export function checkDuration(value: number): void {
  if (!Number.isFinite(value) || value <= 0 || value > config.maxDuration) throw new Error('Duration limit');
}
export function checkSize(value: number): void {
  if (!Number.isSafeInteger(value) || value < 1 || value > config.maxBytes) throw new Error('File limit');
}
export function checkShots(count: number): void {
  if (!Number.isInteger(count) || count < 1 || count > config.maxShots) throw new Error('Shot limit');
}
// Text is never a filter expression. These bytes go into a private UTF-8 file;
// drawtext uses expansion=none, so even percent expressions remain literal.
export function textBytes(text: string): Buffer {
  if (text.includes('\0') || Buffer.byteLength(text) > 8192) throw new Error('Text limit');
  return Buffer.from(text, 'utf8');
}
export const textSchema = z.string().min(1).max(2000).refine(s => !s.includes('\0'));
