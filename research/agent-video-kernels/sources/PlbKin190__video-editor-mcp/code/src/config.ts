import { z } from 'zod';

const integer = (fallback: number, min: number, max: number) =>
  z.coerce.number().int().min(min).max(max).default(fallback);

const environment = z.object({
  WORKSPACE_DIR: z.string().min(1).default('workspace'),
  MAX_RENDER_SECONDS: integer(300, 1, 3600),
  MAX_FILE_BYTES: integer(536870912, 1024, 8589934592),
  EXEC_TIMEOUT_MS: integer(180000, 100, 3600000),
  MAX_COMPOSITION_SHOTS: integer(32, 1, 128),
  FFMPEG_THREADS: integer(2, 1, 16),
  MAX_QUEUED_JOBS: integer(8, 1, 64)
}).parse(process.env);

export const config = Object.freeze({
  workspace: environment.WORKSPACE_DIR,
  maxDuration: environment.MAX_RENDER_SECONDS,
  maxBytes: environment.MAX_FILE_BYTES,
  timeoutMs: environment.EXEC_TIMEOUT_MS,
  maxShots: environment.MAX_COMPOSITION_SHOTS,
  threads: environment.FFMPEG_THREADS,
  maxQueued: environment.MAX_QUEUED_JOBS
});
