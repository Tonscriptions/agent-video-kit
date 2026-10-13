import { execFile } from 'child_process';
import { promisify } from 'util';
import path from 'path';

const execFileAsync = promisify(execFile);

export interface MediaProbeResult {
  durationMicroseconds: number;
  durationSeconds: number;
  width: number;
  height: number;
  fps: number;
  hasAudio: boolean;
  hasVideo: boolean;
  isImage: boolean;
  codec: string;
}

export class MediaProbe {
  /**
   * Checks whether a file extension corresponds to a standard image.
   */
  public static isImageExtension(filePath: string): boolean {
    const ext = path.extname(filePath).toLowerCase();
    return ['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif'].includes(ext);
  }

  /**
   * Runs ffprobe to extract technical metadata from media files.
   */
  public static async probeFile(filePath: string): Promise<MediaProbeResult> {
    const isImage = this.isImageExtension(filePath);

    try {
      const { stdout } = await execFileAsync('ffprobe', [
        '-v', 'error',
        '-show_entries', 'format=duration:stream=width,height,r_frame_rate,codec_type,codec_name',
        '-of', 'json',
        filePath
      ]);

      const data = JSON.parse(stdout);
      const streams: Array<{
        codec_type: string;
        codec_name?: string;
        width?: number;
        height?: number;
        r_frame_rate?: string;
      }> = data.streams || [];

      const videoStream = streams.find(s => s.codec_type === 'video');
      const audioStream = streams.find(s => s.codec_type === 'audio');

      let durationSec = parseFloat(data.format?.duration || '0');
      if (isNaN(durationSec) || durationSec <= 0) {
        // For static images, ffprobe duration is often 0 or N/A
        durationSec = isImage ? 3.0 : 0;
      }

      let fps = 30.0;
      if (videoStream?.r_frame_rate && videoStream.r_frame_rate.includes('/')) {
        const [num, den] = videoStream.r_frame_rate.split('/').map(Number);
        if (den && den > 0 && num > 0) {
          fps = Math.round((num / den) * 100) / 100;
        }
      }

      return {
        durationMicroseconds: Math.round(durationSec * 1_000_000),
        durationSeconds: durationSec,
        width: videoStream?.width || (isImage ? 1080 : 1920),
        height: videoStream?.height || (isImage ? 1920 : 1080),
        fps,
        hasAudio: !!audioStream,
        hasVideo: !!videoStream,
        isImage,
        codec: videoStream?.codec_name || audioStream?.codec_name || 'unknown'
      };
    } catch (err) {
      // Fallback if ffprobe is unavailable or fails on an image
      if (isImage) {
        return {
          durationMicroseconds: 3_000_000, // 3 seconds default
          durationSeconds: 3.0,
          width: 1080,
          height: 1920,
          fps: 30,
          hasAudio: false,
          hasVideo: true,
          isImage: true,
          codec: 'image'
        };
      }
      throw new Error(`Media probe failed for '${filePath}': ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  /**
   * Formats microseconds into MM:SS.mmm or SS.ms
   */
  public static formatDuration(us: number): string {
    const totalSec = us / 1_000_000;
    const mins = Math.floor(totalSec / 60);
    const secs = (totalSec % 60).toFixed(2);
    if (mins > 0) {
      return `${mins}m ${secs}s`;
    }
    return `${secs}s`;
  }
}
