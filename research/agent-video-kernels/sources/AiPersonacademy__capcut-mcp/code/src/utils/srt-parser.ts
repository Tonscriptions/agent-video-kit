import { SubtitleItem } from '../capcut/types.js';

export class SrtParser {
  /**
   * Converts an SRT timecode (e.g., "00:01:23,456" or "00:01:23.456") to seconds.
   */
  public static timecodeToSeconds(tc: string): number {
    const parts = tc.trim().replace(',', '.').split(':');
    if (parts.length === 3) {
      const hours = parseFloat(parts[0]);
      const minutes = parseFloat(parts[1]);
      const seconds = parseFloat(parts[2]);
      return hours * 3600 + minutes * 60 + seconds;
    } else if (parts.length === 2) {
      const minutes = parseFloat(parts[0]);
      const seconds = parseFloat(parts[1]);
      return minutes * 60 + seconds;
    }
    return parseFloat(tc);
  }

  /**
   * Parses an SRT string into an array of SubtitleItem objects.
   */
  public static parse(content: string): SubtitleItem[] {
    const cleanContent = content.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
    const blocks = cleanContent.split(/\n\s*\n/);
    const items: SubtitleItem[] = [];

    for (const block of blocks) {
      const lines = block.trim().split('\n');
      if (lines.length < 2) continue;

      let timeLineIdx = -1;
      for (let i = 0; i < lines.length; i++) {
        if (lines[i].includes('-->')) {
          timeLineIdx = i;
          break;
        }
      }

      if (timeLineIdx === -1) continue;

      const timeLine = lines[timeLineIdx];
      const [startStr, endStr] = timeLine.split('-->').map(s => s.trim());
      const startTimeSeconds = this.timecodeToSeconds(startStr);
      const endTimeSeconds = this.timecodeToSeconds(endStr);

      const text = lines.slice(timeLineIdx + 1).join(' ').trim();
      if (text && !isNaN(startTimeSeconds) && !isNaN(endTimeSeconds)) {
        items.push({
          startTimeSeconds,
          endTimeSeconds,
          text
        });
      }
    }

    return items;
  }
}
