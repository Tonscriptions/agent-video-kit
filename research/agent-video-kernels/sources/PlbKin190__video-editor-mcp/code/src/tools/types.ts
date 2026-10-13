import type { z } from 'zod';
import type { Job } from '../workspace.js';

export interface Tool {
  name: string;
  description: string;
  schema: z.ZodType<unknown>;
  run: (input: unknown, job: Job) => Promise<unknown>;
}
export function defineTool<S extends z.ZodTypeAny>(name: string, description: string, schema: S,
  run: (input: z.output<S>, job: Job) => Promise<unknown>): Tool {
  return { name, description, schema, run: (input, job) => run(schema.parse(input), job) };
}
