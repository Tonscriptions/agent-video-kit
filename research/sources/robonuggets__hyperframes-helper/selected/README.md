# Hyperframes Helper

A practical kit for building motion-graphics videos with [Hyperframes](https://github.com/heygen-com/hyperframes) — HeyGen's open-source HTML-to-MP4 renderer. Three levels of effort matched to three different goals.

> Made for AI-coding agents (Claude Code, Cursor, etc.) so they can pick up real production patterns instead of reinventing the wheel.

## Why this exists

Hyperframes is brilliant for motion graphics — you write HTML/CSS/GSAP, it renders a deterministic MP4. But there's a gap between "the docs" and "what actually works in production." This kit fills it: a SKILL.md the agent reads first, copy-paste recipes for the patterns you'll actually use, and Python scripts for the silence-cut + retake-cut workflow that turns raw recordings into polished video.

## What's inside

```
hyperframes-helper/
├── .claude/skills/hyperframes-helper/
│   ├── SKILL.md                       ← three-level workflow + 16 lint gotchas
│   └── templates/
│       ├── composition-template.html  ← scaffold for a new composition
│       ├── storyboard-template.html   ← Level 2 storyboard starter
│       ├── recipes.md                 ← 10 copy-paste motion-graphics patterns
│       ├── silence-cut.sh             ← ffmpeg silence trim
│       ├── transcribe-whisper.py      ← faster-whisper word-level transcription
│       └── cut-retakes.py             ← last-take-rule retake removal
├── CLAUDE.md
├── README.md
└── LICENSE
```

## Quick start

```bash
# 1. Clone this repo into your project
git clone https://github.com/robonuggets/hyperframes-helper

# 2. Copy the skill into your project's .claude/skills/
cp -r hyperframes-helper/.claude/skills/hyperframes-helper YOUR_PROJECT/.claude/skills/

# 3. Open your project in Claude Code (or any agent that reads .claude/skills/)
# 4. Ask the agent for a Hyperframes video — it'll invoke the skill
```

You'll also need Hyperframes itself (one-time install per machine):

```bash
node --version                          # v18+ required
npx hyperframes@latest --help
npx skills add heygen-com/hyperframes   # adds /hyperframes, /gsap, /website-to-hyperframes
```

## The three levels

The skill organises work by complexity. Pick the level that matches what you're trying to do.

**Level 1 — Website-to-Video.** You have an animated webpage or component and want a 6-15s MP4 of it. Use Hyperframes' built-in `/website-to-hyperframes` skill. Reference [21st.dev](https://21st.dev) for great HTML components to capture.

**Level 2 — Storyboards.** Original motion-graphics video, planning the layout before committing to a real composition. The storyboard template lets you iterate visually in HTML (~1 min per cycle) instead of in Studio (~15 min per cycle). Saves a lot of time on intros, hooks, ads, lesson trailers.

**Level 3 — Guided Videos.** Talking-head video with motion graphics on top. Three steps: cut the video (ffmpeg + faster-whisper, or [video-use](https://github.com/browser-use/video-use) if you'd rather automate it), storyboard the title cards, add motion graphics. Recipes for every common pattern (chroma key, D3 globe, pulse borders, liquid glass, curved underlines, etc.) are in `templates/recipes.md`.

## Features the skill covers

- Three-level workflow matched to common goals
- 16 lint gotchas — every Hyperframes error you'll hit, with the fix
- Multi-clip cut-editing pattern — keep cuts editable in Studio via `data-media-start`
- Studio editing limits, documented from the official guide
- Highest-quality render recipe (`--quality high --crf 16 --gpu`)
- Two-pass video editing pipeline (silence-cut → transcribe → retake-cut)
- 10 copy-paste motion-graphics recipes (frosted glass, chroma key, D3 globe, etc.)

## Usage examples

```
"Build me a Hyperframes video from this raw recording. Level 3 pipeline."

"I have a hero animation on this Webflow site — turn it into a 10-second MP4."

"Storyboard the L-0042 lesson intro. 5 scenes, talking-head + side cards."

"Render the current composition at highest quality. Open the MP4 when done."
```

## How it was made

This kit was distilled from real production work — building intro videos for the [RoboNuggets](https://robonuggets.com) YouTube channel. Every gotcha in the SKILL.md is one we hit. Every recipe in `recipes.md` is one we shipped.

If you want to see what end-to-end looks like, watch the channel for the Hyperframes lesson — it walks through the full Level 3 pipeline.

## Attribution

Created by Jay from [RoboNuggets](https://robonuggets.com).

Free to use under [CC BY 4.0](LICENSE) with attribution. Use it for client work, learning, your own channel — just credit RoboNuggets somewhere visible.

## Credits

- [Hyperframes](https://github.com/heygen-com/hyperframes) by HeyGen — Apache 2.0
- [video-use](https://github.com/browser-use/video-use) by browser-use — alternative auto-cut option
- [21st.dev](https://21st.dev) — HTML component reference
- [GSAP](https://gsap.com) — animation library used throughout
- [D3](https://d3js.org) — geo + graphics primitives for the globe recipe
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — transcription engine for the cut workflow
