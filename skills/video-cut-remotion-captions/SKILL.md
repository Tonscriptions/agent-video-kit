---
name: video-cut-remotion-captions
description: Transcribing, displaying and animating captions
metadata:
  upstream_fields:
    version: 4.0.534
  video_cut_source:
    repository: remotion-dev/skills
    commit: 32b241b97f4e0e4ab61fe9a41b05e6e64503f8c5
    path: skills/remotion-captions
    original_name: remotion-captions
---

Read [local installation rules](references/local-installation.md) before running the upstream workflow.

All captions must be processed in JSON. The captions must use the [`Caption`](https://www.remotion.dev/docs/captions/caption.md) type which is the following:

```ts
import type { Caption } from "@remotion/captions";
```

This is the definition:

```ts
type Caption = {
  text: string;
  startMs: number;
  endMs: number;
  timestampMs: number | null;
  confidence: number | null;
  pageBreakAfter?: boolean;
};
```

## Generating captions

To transcribe video and audio files to generate captions, load the [transcribe-captions.md](transcribe-captions.md) file for more instructions.

## Displaying captions

To display captions in your video, load the [display-captions.md](display-captions.md) file for more instructions.

## Importing captions

To import captions from a .srt file, load the [import-srt-captions.md](import-srt-captions.md) file for more instructions.

## Post-creation

After you're done, load this skill: Remotion Best Practices

If not alreay done, open the Remotion Studio, unless instructed otherwise.
