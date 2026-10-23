# 100 offline style presets

Use the pinned installed `$avk` launcher from SKILL.md. First read `capabilities`, `look list` and
`look inspect --id ID`. Search supports Chinese, English, IDs and `--category`.

```powershell
& $avk look list --query '黑白'
& $avk look list --category cinema
& $avk look inspect --id t3-kodak-gold-200
& $avk look preview --id t3-kodak-gold-200 --input 'E:/media/frame.png' --output 'E:/work/gold.png' --strength 0.65
& $avk look apply --project 'E:/work/ad' --id t3-kodak-gold-200 --clip-id clip_1 --strength 0.65 --dry-run
& $avk look apply --project 'E:/work/ad' --id t3-kodak-gold-200 --clip-id clip_1 --strength 0.65 --idempotency-key gold-v1
& $avk preview frame --project 'E:/work/ad' --frame 0
& $avk render --project 'E:/work/ad' --output 'E:/work/ad/renders/gold.mp4'
```

- All 100 LUTs, previews and MIT notices are already installed; runtime downloads are unnecessary.
- `look preview` writes a new PNG, using a synthetic reference when `--input` is absent. Use a prepared SDR still.
- `look apply` requires an existing video clip (`--clip-id`, optional `--sequence-id`) or explicit `--global`.
  Global affects every sequence through project settings. It does not refer to the currently selected clip.
- Strength is finite 0–1, default 1. Use the user's requested strength; otherwise compare a few previews.
  Partial strength mixes LUT and identity in encoded RGB, not linear light.
- Default application replaces built-in looks at the first existing preset position. Manual effects survive.
  `--append` intentionally stacks looks. An idempotency key protects retries of the same request.
- Dry run writes no LUT/registry/snapshot. Application copies a LUT and its license/provenance into project assets,
  registers rights, snapshots and validates. Changed project copies fail instead of being overwritten.
- Inspect the final decoded video and warnings. The synthetic preview is not natural-footage acceptance.
- Creative SDR encoded RGB only. Float32, Log/HDR apply is explicitly refused; perform an explicit SDR conversion
  first when appropriate. The upstream creative assets do not specify calibrated camera transfer functions.
- Community film names are upstream labels; no official Leica/CapCut filters or manufacturer endorsement is implied.
  This adds color looks, not spatial grain, glow, beauty, AI effects or complete proprietary feature parity.
- Project-package export carries built-in IDs, LUT registry, LUT bytes and relative license evidence. Other assets'
  rights still need their own review. `render --publish` is a local rights gate and never uploads a video.

Local material-specific suggestions: inspect `t3-kodak-portra-400` for portrait color, `t3-kodak-gold-200` for warm
color, `t3-fuji-velvia-50` for vivid landscapes, `t3-ilford-hp5-plus-400` for B&W, and cinema/creative categories
for deliberate stylization. These are starting points for comparison, not quality guarantees.
