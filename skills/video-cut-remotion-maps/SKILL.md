---
name: video-cut-remotion-maps
description: Remotion Map animation knowledge
metadata:
  upstream_fields:
    version: 4.0.534
  video_cut_source:
    repository: remotion-dev/skills
    commit: 32b241b97f4e0e4ab61fe9a41b05e6e64503f8c5
    path: skills/remotion-maps
    original_name: remotion-maps
---

Read [local installation rules](references/local-installation.md) before running the upstream workflow.

# Remotion Maps

Choose exactly one technique from the intended shot, then load only that technique's `TECHNIQUE.md`.
Every technique directory is self-contained and may be removed without breaking the others.

## [Static map](techniques/static-map/TECHNIQUE.md)

- Requires you grab a satellite image and mount it in a `<Img>` tag, and animate on top

## [Mapbox](techniques/mapbox/TECHNIQUE.md)

- Requires a Mapbox key
- Nicer styles by default
- Map can display a round globe when zoomed out
- Includes nice 3D buildings such as the Eiffel tower

## [MapLibre](techniques/maplibre/TECHNIQUE.md)

- Requires no API key, fully free
- Does not include 3D building

## [MapTiler](techniques/maptiler/TECHNIQUE.md)

- Uses MapTiler
- Annotations can be drawn on top of geographic features: borders, rivers, labels

## [CesiumJS](techniques/cesium/TECHNIQUE.md)

- Flythroughs through terrain and mountains
- "Flight simulator" perspective
