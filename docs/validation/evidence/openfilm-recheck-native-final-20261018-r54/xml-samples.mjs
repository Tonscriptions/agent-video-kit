
import { pathToFileURL } from 'node:url';
import { join } from 'node:path';
import { writeFileSync } from 'node:fs';
const [source, out] = process.argv.slice(2);
const base = join(source, 'packages/openfilm/studio/server');
const { fcpxmlDocument } = await import(pathToFileURL(join(base, 'fcpxml.mjs')));
const { nleRate } = await import(pathToFileURL(join(base, 'nle.mjs')));
const { filmSubtitleVtt } = await import(pathToFileURL(join(base, 'film-subtitle.mjs')));
for (const fps of [25, 29.97]) {
  const plan = {
    name: 'AVK research <local> & 中文', rate: nleRate(fps), width: 1920, height: 1080, durationFrames: 90,
    files: [
      { id: 'video', name: 'local & shot.mov', path: join(out, 'local & shot.mov'), durationFrames: 300,
        video: { w: 1920, h: 1080, alpha: false, still: false, fps: 25 } },
      { id: 'audio', name: 'local.wav', path: join(out, 'local.wav'), durationFrames: 300,
        audio: { channels: 2, sampleRate: 48000 } },
    ],
    video: [
      { enabled: true, clips: [
        { name: 'A', fileId: 'video', start: 0, end: 30, in: 60, out: 90, enabled: true },
        { name: 'B', fileId: 'video', start: 30, end: 90, in: 15, out: 75, enabled: true },
      ] },
      { enabled: true, clips: [
        { name: 'overlay', fileId: 'video', start: 45, end: 75, in: 5, out: 35, enabled: true },
      ] },
    ],
    audio: [{ enabled: true, sourceTrack: 3, clips: [
      { name: 'voice', fileId: 'audio', start: 15, end: 60, in: 30, out: 75, enabled: true, gain: .5 },
    ] }],
  };
  writeFileSync(join(out, `sample-${fps}.json`), JSON.stringify(plan, null, 2) + '\n');
  writeFileSync(join(out, `sample-${fps}.fcpxml`), fcpxmlDocument(plan, {
    cues: [{ startMs: 1100, durMs: 700, text: 'Hello & <world>\n第二行', speaker: 'Ann' }],
  }));
}
writeFileSync(join(out, 'escaped.vtt'), filmSubtitleVtt([
  { startMs: 0, durMs: 1000, text: 'A & <B> --> C', speaker: 'Ann & <X>' },
]));
process.stdout.write(JSON.stringify({ timelines: 2, media_created: false, frames_rendered: 0 }) + '\n');
