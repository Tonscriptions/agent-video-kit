# CapCut Desktop Master Manual: Comprehensive Video Engineering, Animation & Typography Guide

> **Document Class**: Permanent Technical Manual & Operational Playbook  
> **Environment**: Cross-Platform (Windows / macOS) CapCut Desktop  
> **Target Audience**: Autonomous AI Agents, Motion Directors & Video Editors  
> **Platform Target**: CapCut Desktop (Windows / macOS) & Programmatic MCP Automation  

---

## 1. TYPOGRAPHY, AUTO-CAPTIONS & DYNAMIC FONT CRAFT

### 1.1 The Auto-Caption Workflow vs. Bespoke Kinetic Styling
Auto-captions generated natively by speech-to-text engines provide accurate timestamps, but they default to static, unformatted text blocks that cause viewer drop-off.
* **The Two-Tier Method**:
  1. Generate auto-captions solely to establish the **acoustic timeline scaffolding** (word boundaries and timestamps).
  2. Suppress the default raw subtitle track and replace it with custom-styled typographic chunks (1 to 3 words maximum per card).
* **Reading Cadence Invariant**: Viewers on mobile consume social video at approximately $250\text{ to }300\text{ words per minute}$ ($4.1\text{ to }5.0\text{ words per second}$). Setting more than 3 words per card creates visual clutter; setting 1 punchy word per card increases retention and focus.

---

### 1.2 Font Superfamily Casting & Visual Identity
Never select arbitrary decorative script or low-contrast serif fonts for rapid kinetic captions. Mobile glass screens, ambient glare, and compression artifacts degrade thin strokes.
* **The 4 Essential Fonts**:
  * **Montserrat (ExtraBold 800 / Black 900)**: The gold standard for high-impact social video. High x-height, wide geometric stance, solid stems that survive compression.
  * **Poppins (SemiBold 600 / Bold 700)**: Clean, friendly geometric grotesk with rounded terminals. Excellent for educational, lifestyle, and explainer content.
  * **Helvetica Now / Neue (Black)**: Neutral, authoritative Swiss precision. Best for finance, corporate case studies, and documentary realism.
  * **Arial (Black)**: Fallback universal sans-serif with heavy mass.

---

### 1.3 The -1.0 Metric Tracking (Kerning) Rule
* **Standard Tracking (`0.0`)**: Glyphs have standard loose spacing designed for long-form print reading. In rapid motion graphics, this reads as disconnected individual letters.
* **The Rule**: Always set **`Character Spacing = -1.0`** (CapCut UI) or **`-0.03em`** (Remotion/CSS).
* **Perceptual Science**: Tightening the kerning eliminates optical dead zones between glyphs, uniting the letters into an atomic visual silhouette. This reduces saccadic eye-travel time by ~40%.

---

### 1.4 The 26/26 Invisible Ambient Shadow
* **The Anti-Stroke Principle**: Heavy 10px black borders around white text scream "amateur template" and cheapen production value.
* **The Ambient Shadow Formulation**:
  * **Color**: `#000000` (Pure Black)
  * **Opacity**: **`26%`**
  * **Blur / Smoothing**: **`26%`**
  * **Distance**: **`0`**
  * **Angle**: **`0°`**
* **Effect**: Produces an omnidirectional, soft dark aura behind each glyph. White text remains 100% legible over white t-shirts, yellow walls, and bright studio lights without harsh boundary lines.

---

### 1.5 Word-Level Hierarchy & Color Accenting
Never style an entire phrase uniformly. The brain tunes out uniform visual stimuli in less than 1.0 second.
* **Syntactic Base Copy**: `#FFFFFF` at $1.0\times$ baseline scale (e.g. 14pt in CapCut).
* **Power Words**:
  * Scale multiplier: **$1.4\times$ to $1.6\times$** baseline size.
  * Accent Color Palette:
    * **Crimson Red (`#FF1E27` / `#FF2238`)**: Loss, critical metrics, urgency, sudden pivots.
    * **Warm Gold (`#FFD700`)**: Wealth, income, revenue, achievement, scaling.
    * **Electric Cyan (`#00E5FF`)**: Technology, systems, software, artificial intelligence.
    * **Neon Emerald (`#00FF88`)**: Growth, profit, positive health, validation.

---

## 2. KEYFRAME MECHANICS, EASING CURVES & BUTTERY SMOOTH MOTION

### 2.1 The Mathematics of Easing Curves
Linear keyframes ($f(p) = p$) look robotic, sterile, and amateur because physical objects in the real world never start or stop instantly without acceleration and friction.

```
Velocity
 ^
 |  *---.
 |  |    `---.       Quad Ease Out: 80% speed at start,
 |  |         `----. cushioned deceleration at end
 0--+-----------------------------------> Time (Frames 0 -> 6)
```

* **Linear Ease**: Flat velocity. Mechanical and dead.
* **Symmetric Ease (50/50 In-Out)**: Sluggish start, peak in the middle, slow stop. Feels floaty and unresponsive.
* **Asymmetric Quad Ease Out (The Pro Velocity Curve)**:
  $$f(p) = 1 - (1 - p)^4 \quad \text{for } p \in [0, 1]$$
  * $80\%$ of spatial translation occurs in the first $25\%$ of the duration.
  * The final $75\%$ of the duration is an ultra-smooth cushion into the resting baseline.

### 2.2 How to Configure Quad Ease in CapCut Desktop
1. Select the animated clip or text segment.
2. Set Keyframe 0 at Start; set Keyframe 1 at Destination (e.g. 5–6 frames forward).
3. Right-click the keyframed property in the timeline $\to$ select **Show variable speed and animation** (or click the curve graph icon).
4. Highlight both keyframes $\to$ Right-click $\to$ **Show all presets** $\to$ choose **Quad Ease**.
5. **The Pro Bezier Adjustment**: Pull the upper bezier tangent handle horizontally toward Frame 0. This steepens the launch velocity and cushions the landing.

---

### 2.3 The "Hover-Up" Pop Recipe
* **Parameters**:
  * Duration: Exactly **$5\text{ to }6\text{ frames}$** at 60 FPS ($83\text{--}100\text{ms}$).
  * Position Translation: $\Delta Y = +35\text{px} \to 0\text{px}$ (translates upward from floor to resting baseline).
  * Opacity / Blend: $0\% \to 100\%$.
* **CapCut Normalized Coordinates**: On a $1080 \times 1920$ canvas:
  $$Y_{\text{start}} = Y_{\text{target}} - 0.035, \quad Y_{\text{end}} = Y_{\text{target}}$$

---

### 2.4 Damped Harmonic Spring Overshoot Formula
When physical mass snaps into a stop, it slightly overshoots and oscillates:
$$S(t) = 1.0 + A \cdot e^{-\lambda t} \cdot \cos(\omega t)$$
* Amplitude $A = 0.08\text{ to }0.12$ ($8\%\text{ to }12\%$ scale overshoot).
* Damping $\lambda = 0.28$ (rapid decay over 8 frames).
* Frame 0: $95\%$ anticipation squeeze.
* Frame 4: $108\%$ peak overshoot.
* Frame 7: $98\%$ rebound undershoot.
* Frame 12: $100\%$ locked settle.

---

## 3. MASKS & VECTOR EDGE DISSOLVES

### 3.1 Mask Types in CapCut Desktop
CapCut provides 6 hardware-accelerated mask models under `materials.common_mask`:
1. **Split Mask**: A single infinite cutting plane that bisects the frame. Ideal for directional wipes, hand-drawn stroke reveals, and split-screen partitions.
2. **Linear / Filmstrip Mask**: Parallel double-cut plane. Ideal for letterboxing, cinematic anamorphic wipes, and focal band passes.
3. **Mirror Mask**: Symmetrical expansion from a central origin axis.
4. **Circle / Radial Mask**: Elliptical boundary with independent $X/Y$ radii and feathering. Ideal for spotlighting faces, vignette dissolves, and circular portal reveals.
5. **Rectangle Mask**: Rounded rectangle with corner radius controls. Ideal for card reveals, UI mockups, and HUD overlays.
6. **Star / Heart Shapes**: Decorative clip masks.

---

### 3.2 Animating Hand-Drawn Scribbles & Underlines (The Split Mask Method)
1. Import a transparent 32-bit PNG of a hand-drawn stroke, underline, or circle above the text track.
2. Add a **Split Mask** to the scribble clip.
3. Rotate the split line so it matches the perpendicular angle of the stroke trajectory.
4. **Keyframe 0**: Position the mask so the scribble is completely outside the visible half-plane ($0\%$ visible).
5. **Keyframe 1** ($6\text{--}10\text{ frames}$ later, matched to spoken syllable duration): Translate the mask across the scribble until it is $100\%$ unmasked.
6. **Result**: The stroke appears organically drawn in real-time by an invisible pen locked to the speaker's vocal emphasis.

---

### 3.3 Vector Edge Fading & Progressive Dissolution
To achieve smooth edge fading (e.g. numbers or graphics dissolving progressively as they increment):
* **Feather Parameter**: CapCut's mask `feather` slider expands the alpha gradient transition zone from $0\text{px}$ (hard razor edge) to $100\text{px}$ (wide Gaussian smoke falloff).
* **Progressive Dissolve Equation**:
  $$\text{Feather}(t) = \text{BaseFeather} + (\text{MaxFeather} - \text{BaseFeather}) \cdot \left(\frac{t}{T}\right)^2$$
  As the element reaches terminal velocity or final count, the boundary feather expands inward while global alpha ramps down, causing the perimeter to soften, smoke, and evaporate into the background.

---

## 4. TIMELINE ARCHITECTURE & AUDIO POLISH

### 4.1 Track Allocation Standard
Maintain clean track discipline to prevent layering collisions:
* **Track 0 (Base)**: Main Video Track / 60 FPS Master Plate / Background Plate.
* **Track 1 (Overlay 1)**: B-Roll cutaways, screen recordings, product demos.
* **Track 2 (Overlay 2)**: Graphic scribbles, animated stickers, UI pointers.
* **Track 3 (Top Video)**: Foreground vignette, optical grain, letterbox mattes.
* **Audio Track 0**: Primary voiceover / spoken dialogue.
* **Audio Track 1**: Background Music (BGM) with auto-fades and leveling ($-18\text{dB}$ to $-24\text{dB}$ under dialogue).
* **Audio Track 2**: Transient Sound Effects (whooshes, pop clicks, sub-impacts).
* **Text Track 0**: Hero Kinetic Captions (Aeovisuals viral typography).
* **Text Track 1**: Secondary Technical Telemetry / Chapter Tags / Watermark.

---

### 4.2 Audio Fade Invariants
* Background music must never cut in or out sharply on frame boundaries.
* **Intro Music Fade**: $1.0\text{s to }1.5\text{s}$ smooth logarithmic fade-in.
* **Outro Music Fade**: $2.0\text{s to }3.5\text{s}$ extended fade-out that lingers under the final branded card.
* **Spliced Dialogue**: Apply micro crossfades ($10\text{--}15\text{ms}$ or 1 frame) across bladed speech clips to eliminate room-tone pops and digital clicks.

---

### 4.3 Transient Audio-Visual Synchronization
Human hearing processes auditory transients faster than optical vision:
* Place whooshes, risers, and impact hits **$1\text{ to }2\text{ frames}$ before** the visual graphic hits its peak impact. This compensates for perceptual audio latency and makes impacts feel physically solid.

---

## 5. CAPCUT MCP AUTONOMOUS TOOL PLAYBOOK

When operating autonomously via the CapCut MCP Server, execute these proven multi-tool choreographies:

### Scenario A: The Viral Hook Build (First 3 Seconds)
1. Call `capcut_create_project` with `ratio="9:16"`, `fps=60`.
2. Call `capcut_add_video_clip` to insert background footage on track 0.
3. Call `capcut_add_viral_caption` with `power_words=["10 MILLION", "SECRET"]`, `font_family="Montserrat"`, `accent_color="#FF1E27"`, and `enable_hover_pop=true`.
4. Call `capcut_add_sound_effect` with a whoosh/pop transient file at $t = 0.0$ to hit on the caption pop.
5. Call `capcut_add_audio_clip` with BGM at `volume=0.25`.
6. Call `capcut_add_audio_fade` with `fade_in_seconds=1.2` on the BGM track.

---

### Scenario B: The Tight Talking-Head Cut (Eliminating Dead Air)
1. Find silence/pause timestamp $T_{\text{pause}}$ using audio analysis.
2. Call `capcut_split_clip` at $T_{\text{start\_pause}}$ $\to$ yields `Segment_A` and `Segment_B`.
3. Call `capcut_split_clip` on `Segment_B` at $T_{\text{end\_pause}}$ $\to$ yields `Segment_Pause` and `Segment_C`.
4. Call `capcut_remove_clip` on `Segment_Pause`.
5. Call `capcut_trim_clip` to close the gap between `Segment_A` and `Segment_C`.

---

### Scenario C: The B-Roll Speed Ramp
1. Call `capcut_add_video_clip` with raw B-roll footage.
2. Call `capcut_split_clip` at the moment action begins $\to$ `Clip_Normal` and `Clip_Ramp`.
3. Call `capcut_set_clip_speed` on `Clip_Ramp` with `speed=2.5` and `preserve_pitch=true`.
4. Call `capcut_add_transition` on the cut point with `transition_name="Slide Left"` and `duration_seconds=0.3`.

---

### Scenario D: The Master Video Track Bridge (Complex Motion to CapCut)
When complex motion design (e.g. spring physics, vector mask dissolves, 3D particles) exceeds native CapCut keyframe limitations:
1. Render 60 FPS master visual plate via headless Chromium or Remotion CLI.
2. Call `capcut_create_video_bridge`:
   - Pass `video_plate_path`.
   - Pass separated uncompressed voiceover and BGM tracks.
   - Pass `.srt` subtitle file.
3. Call `capcut_add_viral_caption` to overlay top-priority branded CTA cards in native editable CapCut text tracks.
4. Verify using `capcut_generate_preview` or direct inspection.
