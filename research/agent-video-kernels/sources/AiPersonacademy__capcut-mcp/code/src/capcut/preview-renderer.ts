import { execFile } from 'child_process';
import { promisify } from 'util';
import path from 'path';
import fs from 'fs/promises';
import { existsSync } from 'fs';
import { DraftContent, GeneratePreviewOptions } from './types.js';

const execFileAsync = promisify(execFile);

export class PreviewRenderer {
  /**
   * Generates a fast proxy preview video using ffmpeg from a CapCut draft.
   */
  public static async renderDraft(
    draft: DraftContent,
    projectDir: string,
    options: GeneratePreviewOptions = { projectNameOrId: '' }
  ): Promise<{ outputPath: string; durationSeconds: number }> {
    const width = options.width || draft.canvas_config?.width || 1080;
    const height = options.height || draft.canvas_config?.height || 1920;
    const fps = options.fps || draft.fps || 30;
    const durationSec = Math.max((draft.duration || 0) / 1_000_000, 1.0);

    const outputPath = options.outputPath
      ? path.resolve(options.outputPath)
      : path.join(projectDir, 'preview.mp4');

    const videoSegments: Array<{
      path: string;
      sourceStart: number;
      sourceDuration: number;
      targetStart: number;
      isImage: boolean;
    }> = [];

    const audioSegments: Array<{
      path: string;
      sourceStart: number;
      sourceDuration: number;
      targetStart: number;
      volume: number;
    }> = [];

    // 1. Collect video clips
    for (const track of draft.tracks) {
      if (track.type === 'video') {
        for (const seg of track.segments) {
          const mat = draft.materials.videos.find(v => v.id === seg.material_id);
          if (mat && existsSync(mat.path)) {
            const srcStart = (seg.source_timerange?.start || 0) / 1_000_000;
            const srcDur = (seg.source_timerange?.duration || seg.target_timerange.duration) / 1_000_000;
            const tgtStart = seg.target_timerange.start / 1_000_000;
            videoSegments.push({
              path: mat.path,
              sourceStart: srcStart,
              sourceDuration: srcDur,
              targetStart: tgtStart,
              isImage: mat.type === 'photo'
            });
          }
        }
      } else if (track.type === 'audio') {
        for (const seg of track.segments) {
          const mat = draft.materials.audios.find(a => a.id === seg.material_id);
          if (mat && existsSync(mat.path)) {
            const srcStart = (seg.source_timerange?.start || 0) / 1_000_000;
            const srcDur = (seg.source_timerange?.duration || seg.target_timerange.duration) / 1_000_000;
            const tgtStart = seg.target_timerange.start / 1_000_000;
            audioSegments.push({
              path: mat.path,
              sourceStart: srcStart,
              sourceDuration: srcDur,
              targetStart: tgtStart,
              volume: seg.volume || 1.0
            });
          }
        }
      }
    }

    // Sort video segments by targetStart
    videoSegments.sort((a, b) => a.targetStart - b.targetStart);

    // Build FFmpeg command
    const args: string[] = ['-y'];

    if (videoSegments.length === 0) {
      // No video clips: generate solid color background
      args.push(
        '-f', 'lavfi',
        '-i', `color=c=black:s=${width}x${height}:d=${durationSec}:r=${fps}`
      );

      if (audioSegments.length > 0) {
        let inputIdx = 1;
        for (const aud of audioSegments) {
          args.push('-ss', aud.sourceStart.toString(), '-t', aud.sourceDuration.toString(), '-i', aud.path);
          inputIdx++;
        }
        // Audio filter
        let filterStr = '';
        for (let i = 1; i < inputIdx; i++) {
          const aud = audioSegments[i - 1];
          filterStr += `[${i}:a]volume=${aud.volume},adelay=${Math.round(aud.targetStart * 1000)}|${Math.round(aud.targetStart * 1000)}[a${i}];`;
        }
        const mixInputs = audioSegments.map((_, i) => `[a${i + 1}]`).join('');
        filterStr += `${mixInputs}amix=inputs=${audioSegments.length}:duration=longest[aout]`;

        args.push(
          '-filter_complex', filterStr,
          '-map', '0:v',
          '-map', '[aout]',
          '-c:v', 'libx264',
          '-pix_fmt', 'yuv420p',
          '-c:a', 'aac',
          '-t', durationSec.toString(),
          outputPath
        );
      } else {
        // Pure silent video
        args.push(
          '-f', 'lavfi',
          '-i', 'anullsrc=r=44100:cl=stereo',
          '-c:v', 'libx264',
          '-pix_fmt', 'yuv420p',
          '-c:a', 'aac',
          '-t', durationSec.toString(),
          outputPath
        );
      }
    } else {
      // We have video clips: compose with black background canvas
      args.push(
        '-f', 'lavfi',
        '-i', `color=c=black:s=${width}x${height}:d=${durationSec}:r=${fps}`
      );

      let curInputIdx = 1;
      const filterSteps: string[] = [];

      // Base canvas is [0:v]
      let currentBase = '[0:v]';

      for (let i = 0; i < videoSegments.length; i++) {
        const v = videoSegments[i];
        if (v.isImage) {
          args.push('-loop', '1', '-t', v.sourceDuration.toString(), '-i', v.path);
        } else {
          args.push('-ss', v.sourceStart.toString(), '-t', v.sourceDuration.toString(), '-i', v.path);
        }

        const inputLabel = `[${curInputIdx}:v]`;
        const scaledLabel = `[v_sc_${i}]`;
        const nextBase = i === videoSegments.length - 1 ? '[vout]' : `[base_${i}]`;

        // Scale and pad clip to fit canvas while preserving aspect ratio
        filterSteps.push(
          `${inputLabel}scale=${width}:${height}:force_original_aspect_ratio=decrease,pad=${width}:${height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=${fps}${scaledLabel}`
        );

        const enableExpr = `enable='between(t,${v.targetStart},${v.targetStart + v.sourceDuration})'`;
        filterSteps.push(
          `${currentBase}${scaledLabel}overlay=0:0:${enableExpr}${nextBase}`
        );

        currentBase = nextBase;
        curInputIdx++;
      }

      // Add audio inputs if any
      let hasAudioOut = false;
      if (audioSegments.length > 0) {
        const audioLabels: string[] = [];
        for (let j = 0; j < audioSegments.length; j++) {
          const a = audioSegments[j];
          args.push('-ss', a.sourceStart.toString(), '-t', a.sourceDuration.toString(), '-i', a.path);
          const aIdx = curInputIdx;
          const aLabel = `[a_${j}]`;
          filterSteps.push(
            `[${aIdx}:a]volume=${a.volume},adelay=${Math.round(a.targetStart * 1000)}|${Math.round(a.targetStart * 1000)}${aLabel}`
          );
          audioLabels.push(aLabel);
          curInputIdx++;
        }
        filterSteps.push(
          `${audioLabels.join('')}amix=inputs=${audioSegments.length}:duration=longest[aout]`
        );
        hasAudioOut = true;
      }

      args.push(
        '-filter_complex', filterSteps.join(';'),
        '-map', '[vout]'
      );

      if (hasAudioOut) {
        args.push('-map', '[aout]', '-c:a', 'aac');
      } else {
        args.push('-an');
      }

      args.push(
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-pix_fmt', 'yuv420p',
        '-t', durationSec.toString(),
        outputPath
      );
    }

    try {
      await execFileAsync('ffmpeg', args);
      return {
        outputPath,
        durationSeconds: durationSec
      };
    } catch (err) {
      throw new Error(`FFmpeg preview render failed: ${err instanceof Error ? err.message : String(err)}`);
    }
  }
}
