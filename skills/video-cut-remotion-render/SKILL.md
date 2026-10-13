---
name: video-cut-remotion-render
description: Export a Remotion video
metadata:
  upstream_fields:
    version: 4.0.534
  video_cut_source:
    repository: remotion-dev/skills
    commit: 32b241b97f4e0e4ab61fe9a41b05e6e64503f8c5
    path: skills/remotion-render
    original_name: remotion-render
---

Read [local installation rules](references/local-installation.md) before running the upstream workflow.

## General rendering strategy

Render a video using:

```
npx remotion render
```

Full list of options: https://www.remotion.dev/docs/cli/render.md

Render a still using:

```
npx remotion still
```

Full list of options: https://www.remotion.dev/docs/cli/still.md

To render several frames as images in one call, use `render --frames`:

```
npx remotion render [composition-id] out/frames --frames=0,30,90 --image-format=png
```

See https://www.remotion.dev/docs/cli/render.md#--frames for more options.

## Transparent videos

See [Transparent videos](./transparent-videos.md) for rendering out a video with transparency.
