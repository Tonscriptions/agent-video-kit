import path from 'node:path';
import { constants } from 'node:fs';
import { mkdir, realpath, lstat, open, mkdtemp, rm, link } from 'node:fs/promises';
import { config } from './config.js';
import { checkSize } from './guard.js';

export function validateRelative(name: string): string[] {
  // Deliberately narrow portable names also exclude protocols and filter syntax.
  if (path.isAbsolute(name) || !/^[a-zA-Z0-9_-][a-zA-Z0-9_./-]*$/.test(name)) throw new Error('Path rejected');
  const parts = name.split('/');
  if (parts.some(p => p === '..' || p === '.' || p === '' || p.startsWith('.'))) throw new Error('Path rejected');
  return parts;
}

export class Workspace {
  private constructor(readonly root: string) {}
  static async create(directory = config.workspace): Promise<Workspace> {
    await mkdir(directory, { recursive: true, mode: 0o700 });
    return new Workspace(await realpath(directory));
  }
  async resolve(name: string, output = false): Promise<string> {
    const parts = validateRelative(name);
    let current = this.root;
    for (let i = 0; i < parts.length; i++) {
      current = path.join(current, parts[i]);
      const last = i === parts.length - 1;
      try {
        const info = await lstat(current);
        if (info.isSymbolicLink()) throw new Error('Link rejected');
        const canonical = await realpath(current);
        const relative = path.relative(this.root, canonical);
        if (relative.startsWith('..') || path.isAbsolute(relative)) throw new Error('Outside workspace');
        if (!last && !info.isDirectory()) throw new Error('Not a directory');
        if (last && (output || !info.isFile() || info.nlink !== 1)) throw new Error('Invalid file');
      } catch (error: unknown) {
        if (output && last && (error as NodeJS.ErrnoException).code === 'ENOENT') return current;
        throw error;
      }
    }
    return current;
  }
  async job(): Promise<Job> {
    return new Job(this, await mkdtemp(path.join(this.root, '.job-')));
  }
}

const formats: Record<string, string> = {
  '.mp4': 'mov', '.mov': 'mov', '.m4a': 'mov', '.mkv': 'matroska',
  '.webm': 'matroska', '.wav': 'wav', '.mp3': 'mp3', '.flac': 'flac',
  '.png': 'png_pipe', '.jpg': 'jpeg_pipe', '.jpeg': 'jpeg_pipe'
};
export class Job {
  private counter = 0;
  readonly deadline = Date.now() + config.timeoutMs;
  constructor(readonly workspace: Workspace, readonly directory: string) {}
  async stage(name: string): Promise<{ file: string; format: string }> {
    const format = formats[path.extname(name).toLowerCase()];
    if (!format) throw new Error('Unsupported media');
    const source = await this.workspace.resolve(name);
    const handle = await open(source, constants.O_RDONLY | constants.O_NOFOLLOW);
    const file = `input-${this.counter++}${path.extname(name).toLowerCase()}`;
    try {
      const info = await handle.stat();
      if (!info.isFile() || info.nlink !== 1) throw new Error('Invalid input');
      checkSize(info.size);
      // Snapshot into a server-only directory. ffmpeg never opens client names.
      const target = await open(path.join(this.directory, file), 'wx', 0o600);
      try {
        const buffer = Buffer.alloc(65536);
        let total = 0;
        for (;;) {
          const { bytesRead } = await handle.read(buffer);
          if (bytesRead === 0) break;
          total += bytesRead;
          checkSize(total);
          if (Date.now() > this.deadline) throw new Error('Deadline');
          await target.write(buffer.subarray(0, bytesRead));
        }
      } finally { await target.close(); }
    } finally { await handle.close(); }
    return { file, format };
  }
  async publish(file: string, output: string): Promise<void> {
    const target = await this.workspace.resolve(output, true);
    const info = await lstat(path.join(this.directory, file));
    checkSize(info.size);
    // Hard-link publication is atomic and cannot overwrite an existing file.
    await link(path.join(this.directory, file), target);
  }
  async close(): Promise<void> { await rm(this.directory, { recursive: true, force: true }); }
}
