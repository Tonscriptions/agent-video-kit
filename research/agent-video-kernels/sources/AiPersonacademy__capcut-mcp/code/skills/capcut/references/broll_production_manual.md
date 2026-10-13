# B-Roll Production & Selection Manual: Real-World Sourcing vs. AI Prompting

A comprehensive operational manual for selecting, sourcing, pacing, and compositing B-roll in **Remotion** and **CapCut Desktop**.

---

## 1. The Core Sourcing Decision Matrix

The biggest error in modern AI video production is hallucinating real-world historical figures or actual news events with synthetic image generators. Doing so destroys credibility and repels savvy viewers.

### Rule 1: Real-World Events, Public Figures & Historical Milestones $\to$ REAL-WORLD MEDIA ONLY
Whenever the script refers to:
- Real individuals (**Donald Trump**, **Elon Musk**, **Jensen Huang**, **Steve Jobs**, **Sam Altman**).
- Real breaking news or urban events (**Explosion in Los Angeles**, **CrowdStrike airport outage**, **Fed interest rate hikes**).
- Authentic engineering feats (**SpaceX Starship orbital launches**, **NASA Apollo telemetry**).
- Actual financial institutions (**NYSE trading floor**, **Goldman Sachs headquarters**).

> [!IMPORTANT]
> **MANDATE**: Source authentic documentary photography or broadcast footage from verified archival hubs:
> - **Editorial Archives**: AP Archive, Reuters, Wikimedia Commons, NASA Public Domain Flickr, SpaceX Flickr.
> - **Stock Footage Providers**: Pexels Video, Pixabay, Unsplash Editorial, Coverr.
> - **Never** prompt an AI image generator to synthesize a fake photo of living public figures or real disasters.

---

### Rule 2: Abstract, Conceptual, Metaphorical & Hard-to-Find Scenarios $\to$ SPECIALIZED AI PROMPTING
Whenever the script refers to:
- Impossible or micro-scale concepts (**Bioluminescent neural synapses inside a quantum chip**, **nanobots repairing microcircuits**).
- Sci-Fi / Cyberpunk visualizations (**Holographic AI agent in brutalist room**, **hyperspeed fiber-optic space tunnels**).
- High-concept metaphors (**Melting red candlestick charts under cyber rain**, **shattering financial hourglass**).

> [!TIP]
> **MANDATE**: Route to the specialized AI prompt engineer (Nano Banana 2.0, Midjourney v6.1, Kling v3, Veo 2).
> Apply the **5-Pillar Cinematic Prompt Formula**:
> 1. **Core Subject**: Exact focal element with physical texture.
> 2. **Environment & Atmosphere**: Volumetric lighting, smoke, depth, reflection.
> 3. **Camera & Optics**: ARRI Alexa 65 / anamorphic lens / 85mm f/1.4 / shallow depth-of-field.
> 4. **Color & Contrast**: High-contrast, electric cyan rim lights, deep crushed blacks (`#06080c`).
> 5. **Aspect Ratio & Style**: `--ar 9:16 --v 6.1 --style raw` (or 60 FPS Kling motion prompt).

---

### Rule 3: Dynamic Data, UI Micro-Stories & Software Proof $\to$ REMOTION PROCEDURAL
Whenever the script refers to:
- **Revenue counters rolling from \$0 to \$100k**.
- **Interactive mobile feeds scrolling with Apple-style push notifications**.
- **Live candlestick breakout charts drawing across the screen**.
- **Vector HUD target crosshairs locking on coordinates**.

> [!NOTE]
> **MANDATE**: Build directly as Remotion DOM components or SVG vectors.
> Rendering UI as code gives **100% razor-sharp typography at 60 FPS**, zero YouTube/TikTok video compression artifacts, and microsecond-level animation control.

---

## 2. Pacing & Cut Duration (Walter Murch's Rule of Six)

Never leave a B-roll clip on screen for an arbitrary duration. Every cut must satisfy the **Rule of Six hierarchy**:
1. **Emotion (51%)**: Does the cut match the emotional pulse of the speaker?
2. **Story (23%)**: Does the cut advance understanding?
3. **Rhythm (10%)**: Does the cut land on an acoustic beat or biological blink point?
4. **Eye-Trace (7%)**: Where does the spectator's eye land from the previous shot?
5. **Two-Dimensional Screen Plane (5%)**: Does the composition balance the frame?
6. **Three-Dimensional Space (4%)**: Physical continuity of direction and scale.

### Concrete Pacing Ranges:
| B-Roll Type | Duration Range | Energy Level | Acoustic Treatment |
| :--- | :--- | :--- | :--- |
| **Shock Hook / Pattern Interrupt** | `0.4s - 0.8s` | 9 - 10 / 10 | Instant high-transient crack + sub hit |
| **B-Roll Accent / Reaction** | `0.8s - 1.5s` | 7 - 8 / 10 | Whoosh riser leading into cut point |
| **Anchor Narrative Scene** | `1.8s - 3.2s` | 5 - 6 / 10 | Ambient drone (-22dB) + rhythmic ticking |
| **Atmospheric Film Texture** | Continuous Loop | Background | Analog tape floor noise (-28dB) |

---

## 3. Acoustic Architecture & Mix Hierarchy

B-roll without sound feels hollow. Always attach an acoustic footprint to every visual cut.

### The 4 Audio Planes:
1. **Dialogue / Voiceover**: `0.0 dB` (Normalized LUFS: `-14 LUFS`, high-pass filter at 80 Hz).
2. **Sound Effects (SFX)**: `-6.0 dB` to `-10.0 dB` (Sharp transient clicks, whooshes, sub-bass drops).
3. **Background Music (BGM)**: `-18.0 dB` to `-24.0 dB` (Ducked automatically by `-4dB` during speech).
4. **Atmospheric Tone / Room Noise**: `-26.0 dB` to `-32.0 dB` (Fills acoustic vacuums between words).

---

## 4. Compositing & Blend Modes (CapCut & Remotion)

### Screen Mode (`mix-blend-mode: screen`):
- **Use For**: Anamorphic light flares, lightning sparks, holographic HUD overlays, particle embers.
- **Rule**: Pure black (`#000000`) becomes completely transparent; highlights shine through.

### Overlay Mode (`mix-blend-mode: overlay`):
- **Use For**: 35mm organic film grain, vintage paper textures, subtle light leaks.
- **Rule**: Preserves base video luminance while injecting organic micro-texture.

---

## 5. Instant Catalog Search

To query the B-roll asset catalog with exact search queries and AI prompts:
```bash
# Search real-world events
python scripts/asset_lookup.py broll -s "REAL_WORLD_SEARCH"

# Search by topic / keyword
python scripts/asset_lookup.py broll -q "trump"
python scripts/asset_lookup.py broll -q "explosion"
python scripts/asset_lookup.py broll -q "neural"

# Search by mood
python scripts/asset_lookup.py broll -m "cyberpunk"
```
