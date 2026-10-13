---
name: creative-director
description: "Creative-director knowledge base distilled from 16 books on advertising, creative leadership, idea generation, taste, typography, visual literacy, and information design, plus an evaluation engine adapted from smixs/creative-director-skill. Use when writing or critiquing copy/ads/headlines/campaigns, generating creative ideas or concepts, mining a consumer insight, scoring/evaluating or refining a concept to a quality bar, leading and giving feedback to creative teams, handling difficult conversations, shaping team culture, or developing taste, vision, and creative judgment. Routes to one of five role toolkits (Copywriter, Idea Generator, Creative Leader, Visionary, Evaluator) and loads only what the task needs."
---

<!-- argument-hint: [role, task, topic, or book — e.g. "headline", "lead my team", "develop taste", "ogilvy"] -->

# Creative Director

A working operating system for the creative-director role, distilled from 16 books and extended with an evaluation engine adapted from [smixs/creative-director-skill](https://github.com/smixs/creative-director-skill). It is organized as a **router**: this file is small and always-loaded; the depth lives in **five role files** (loaded one at a time, only when the task calls for it) and **sixteen book digests** (loaded only when you drill into a specific author).

**Built for token economy.** A typical task loads this router (~small) + one role (~3k) ≈ a few thousand tokens — not the 1.28M-token source corpus. Read deeper layers only when needed.

---

## How to Use This Skill

**Fast path:** read the user's request → match it to one row of the **Route by Task** table below → read *only* that role file → act on its playbook. If the task is *scoring, refining, or "is this good enough?"*, read [roles/evaluator.md](roles/evaluator.md) alongside the primary role. Everything below expands this.

1. **Identify the task**, then read the matching **role file** below. Read **one** role unless the task genuinely spans two.
2. **Apply the role's playbook and decision rules** directly — they are written as practitioner instructions, not summaries.
3. **Drill deeper only when needed**: a role file links to its source **book digests** in `books/`. Read a digest when the user asks about a specific author/book or wants the full framework.
4. **For fast cross-role lookups**, use `cheatsheet.md` (decision rules), `patterns.md` (named techniques), `glossary.md` (terms).

---

## Route by Task → Role

Read the role file whose triggers match. Each is a self-contained toolkit.

| Read this role | When the task is… | Source books |
|---|---|---|
| **[roles/copywriter.md](roles/copywriter.md)** | Writing or critiquing ads, headlines, body copy, taglines, campaigns, sales/marketing messaging, or creative briefs | Ogilvy on Advertising · Guts |
| **[roles/idea-generator.md](roles/idea-generator.md)** | Brainstorming, finding a creative angle/concept, adding wit or surprise, making work memorable, or understanding why audiences respond | Creative Mischief · A Smile in the Mind · Predictably Irrational |
| **[roles/creative-leader.md](roles/creative-leader.md)** | Managing creatives, giving feedback, 1:1s/meetings, hiring, motivating, resolving conflict, difficult conversations, the maker→manager transition, or shaping culture | Fired Up · The Making of a Manager · Tribal Leadership · Crucial Conversations · Herding Tigers |
| **[roles/visionary.md](roles/visionary.md)** | Developing taste/vision, setting creative direction, judging quality, cultivating "the eye", typography and type choice, information/data-viz design, or sustaining a creative practice | The Creative Act · The Eye · Steve Jobs · A Primer of Visual Literacy · Envisioning Information · Stop Stealing Sheep |
| **[roles/evaluator.md](roles/evaluator.md)** | Scoring/critiquing an idea, deciding if work is good enough to present, **refining a near-miss concept that scored below the bar**, running a generate→score→refine loop to a quality bar, mining an insight before ideating, killing mediocrity | *engine layer* — adapted from [smixs/creative-director-skill](https://github.com/smixs/creative-director-skill) |

**Mixed tasks** (common): a campaign needs *idea-generator* (concept) + *copywriter* (execution); a tough design critique needs *creative-leader* (how to deliver it) + *visionary* (the quality bar); a pitch needs *copywriter* (argument) + *idea-generator* (behavioral levers). The **evaluator** pairs with *any* role — generate with idea-generator/copywriter, then score and refine with evaluator. Read both roles only when the task truly straddles them.

---

## Topic Index → Role / Book

Jump straight to the right file by topic.

- **Headlines, body copy, layout, print/TV** → copywriter ([ogilvy](books/ogilvy-on-advertising.md))
- **Positioning, brand image, the brief, copy style** → copywriter ([ogilvy](books/ogilvy-on-advertising.md), [guts](books/guts.md))
- **The Big Idea / judging a campaign** → copywriter + idea-generator
- **Brainstorming, provocation, predatory strategy** → idea-generator ([creative-mischief](books/creative-mischief.md))
- **Wit, surprise, visual ideas, the "smile in the mind"** → idea-generator ([smile-in-the-mind](books/smile-in-the-mind.md))
- **Persuasion psychology, pricing, anchoring, decoy, free, social vs market norms** → idea-generator ([predictably-irrational](books/predictably-irrational.md))
- **Feedback & critiquing creative work** → creative-leader ([making-of-a-manager](books/making-of-a-manager.md), [crucial-conversations](books/crucial-conversations.md))
- **Difficult / high-stakes conversations (STATE, AMPP, CRIB)** → creative-leader ([crucial-conversations](books/crucial-conversations.md))
- **Motivating creative teams, burnout, the Fire Triangle** → creative-leader ([fired-up](books/fired-up.md))
- **Culture, the Five Tribal Stages, core values, noble cause** → creative-leader ([tribal-leadership](books/tribal-leadership.md))
- **1:1s, hiring, delegation, meetings, scaling yourself** → creative-leader ([making-of-a-manager](books/making-of-a-manager.md))
- **Maker→manager transition, stability + challenge, fighting for the team, autonomy vs. competence** → creative-leader ([herding-tigers](books/herding-tigers.md))
- **Developing taste / "the eye", input diet, references** → visionary ([the-eye](books/the-eye.md))
- **Creative practice, the Source, the Ecstatic, the four phases** → visionary ([creative-act](books/creative-act.md))
- **Product vision, focus, simplicity, end-to-end, the RDF (+ shadow side)** → visionary ([steve-jobs](books/steve-jobs.md))
- **Visual grammar / composition (basic elements, balance, the felt axis, leveling vs. sharpening, contrast vs. harmony)** → visionary ([a-primer-of-visual-literacy](books/a-primer-of-visual-literacy.md))
- **Information & data-viz design (escaping flatland, micro/macro, layering, small multiples, 1+1=3 clutter, chartjunk)** → visionary ([envisioning-information](books/envisioning-information.md))
- **Typography & type choice (legibility vs. readability, type as voice, spacing/leading/measure, text vs. display)** → visionary ([stop-stealing-sheep](books/stop-stealing-sheep.md))
- **Finding the insight before ideating (Pollard Four Points, JTBD, Tension Spotting, HMW, Abstraction Laddering)** → idea-generator ([insight section](roles/idea-generator.md#finding-the-insight-first))
- **Idea level / Pollard 7-level taxonomy (business → execution), activation test** → idea-generator + [evaluator](roles/evaluator.md)
- **Scoring an idea / "is it good enough to present?" / refine to a quality bar (6 weighted criteria, HumanKind + Grey, Gap Analysis)** → [evaluator](roles/evaluator.md)
- **Emotion Tier (generic vs. specific vs. complex feeling)** → [visionary](roles/visionary.md#judging-quality-the-call) + [evaluator](roles/evaluator.md)
- **Anti-pitfall rules (specificity test, kill your darlings, serial-order warmup, simplicity as violence)** → [evaluator](roles/evaluator.md) + [cheatsheet](cheatsheet.md)
- **Practitioner angles from designer TED talks (habituation, serious-vs-solemn, say-or-show, legibility≠communication, thoughtless acts, data-is-soil)** → [references/ted-talks.md](references/ted-talks.md)
- **Pitching / presenting work to clients or stakeholders** → copywriter (strategy framing, argument) + idea-generator (persuasion levers: anchoring, decoy, norm frame) + [cheatsheet](cheatsheet.md) (Anchor-First Sequencing)

---

## Book Index

| Book | Author | Role | Digest |
|---|---|---|---|
| Ogilvy on Advertising | David Ogilvy | copywriter | [books/ogilvy-on-advertising.md](books/ogilvy-on-advertising.md) |
| Guts: Advertising from the Inside Out | John Lyons | copywriter | [books/guts.md](books/guts.md) |
| Creative Mischief | Dave Trott | idea-generator | [books/creative-mischief.md](books/creative-mischief.md) |
| A Smile in the Mind | McAlhone & Stuart | idea-generator | [books/smile-in-the-mind.md](books/smile-in-the-mind.md) |
| Predictably Irrational | Dan Ariely | idea-generator | [books/predictably-irrational.md](books/predictably-irrational.md) |
| Fired Up | Andrew Johnston | creative-leader | [books/fired-up.md](books/fired-up.md) |
| The Making of a Manager | Julie Zhuo | creative-leader | [books/making-of-a-manager.md](books/making-of-a-manager.md) |
| Tribal Leadership | Logan, King & Fischer-Wright | creative-leader | [books/tribal-leadership.md](books/tribal-leadership.md) |
| Crucial Conversations | Patterson, Grenny, McMillan & Switzler | creative-leader | [books/crucial-conversations.md](books/crucial-conversations.md) |
| Herding Tigers | Todd Henry | creative-leader | [books/herding-tigers.md](books/herding-tigers.md) |
| The Creative Act | Rick Rubin | visionary | [books/creative-act.md](books/creative-act.md) |
| The Eye | Nathan Williams | visionary | [books/the-eye.md](books/the-eye.md) |
| Steve Jobs | Walter Isaacson | visionary | [books/steve-jobs.md](books/steve-jobs.md) |
| A Primer of Visual Literacy | Donis A. Dondis | visionary | [books/a-primer-of-visual-literacy.md](books/a-primer-of-visual-literacy.md) |
| Envisioning Information | Edward R. Tufte | visionary | [books/envisioning-information.md](books/envisioning-information.md) |
| Stop Stealing Sheep | Erik Spiekermann | visionary | [books/stop-stealing-sheep.md](books/stop-stealing-sheep.md) |

---

## Supporting Files

- **[cheatsheet.md](cheatsheet.md)** — cross-role decision rules and quick-reference tables (the judgment layer)
- **[patterns.md](patterns.md)** — every named technique/framework, grouped by use
- **[glossary.md](glossary.md)** — all key terms with definitions and source
- **[references/ted-talks.md](references/ted-talks.md)** — 23 designer/creative TED talks distilled, grouped by the role each feeds (supplementary practitioner layer; not from the 16 books)

---

## Scope & Limits

This skill carries the *ideas* of these books, synthesized — not their full text. It is a thinking and craft aid, not a substitute for the originals. One source — *Tested Advertising Methods* (Caples) — was in the folder but shipped as a scanned PDF with no extractable text, so it is **not** included; add it later by OCR'ing the file and folding it into the copywriter role.

**Related skill.** The copy produced through this skill is LLM-generated and will drift toward AI-slop. The [copywriter](roles/copywriter.md) and [evaluator](roles/evaluator.md) roles hand off to the external [humanizer](https://github.com/blader/humanizer) skill for the final "doesn't-read-as-AI" pass on body copy and long-form prose — it catches tells (em-dash overuse, rule-of-three, soulless rhythm) the Ogilvy/Lyons-era craft checks were never written to catch.

The **Evaluator** role and the insight/Pollard/emotion-tier layers are *not* from the 16 books — they are a distilled adaptation of [smixs/creative-director-skill](https://github.com/smixs/creative-director-skill) (HumanKind/Grey calibration, Pollard taxonomy, weighted scoring loop), marked as such wherever they appear. That project carries the heavier version: a 569-case canon, the P01–P18 pattern map, and a full methods catalog. Drop in a curated case subset there if you want empirical saturation calibration here.
