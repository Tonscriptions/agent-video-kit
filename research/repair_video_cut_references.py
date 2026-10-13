"""Repair bundled upstream reference paths after adapting Skill names."""
import hashlib
import json
from pathlib import Path
import re

PROJECT = Path(__file__).resolve().parents[1]

HYPERFRAMES_MOVES = {
    "techniques.md": "video-cut-hyperframes-animation/techniques.md",
    "html-in-canvas-patterns.md": "video-cut-hyperframes-animation/adapters/html-in-canvas-patterns.md",
    "text-effects.md": "video-cut-hyperframes-animation/adapters/animate-text.md",
    "transitions.md": "video-cut-hyperframes-animation/transitions/overview.md",
    "transitions/": "video-cut-hyperframes-animation/transitions/",
    "css-patterns.md": "video-cut-hyperframes-animation/rules/css-marker-patterns.md",
    "audio-reactive.md": "video-cut-hyperframes-creative/references/audio-reactive.md",
    "captions.md": "video-cut-hyperframes-media/references/captions/authoring.md",
    "typography.md": "video-cut-hyperframes-creative/references/typography.md",
    "motion-principles.md": "video-cut-hyperframes-creative/references/motion-principles.md",
    "dynamic-techniques.md": "video-cut-hyperframes-animation/rules-index.md",
    "video-composition.md": "video-cut-hyperframes-creative/references/video-composition.md",
}


def repair(manifest):
    changed_count = 0
    for entry in manifest["skills"]:
        root = Path(entry["canonical_directory"])
        changed = []
        for path in root.rglob("*.md"):
            original = path.read_text(encoding="utf-8")
            text = original.replace("./video-cut-ffmpeg.md", "./ffmpeg.md")
            text = text.replace("`hyperframes` skill", "`video-cut-hyperframes` skill")
            if root.name == "video-cut-website-to-video":
                for old, new in HYPERFRAMES_MOVES.items():
                    text = text.replace("video-cut-hyperframes/references/" + old, new)
                # The descriptive table now refers to the split-domain documentation.
                text = text.replace("24 named text animations from `pixel-point/animate-text` (separate skill — load via `/animate-text` for specs)", "Text animation adapter and pointers to optional external effect specifications")
            if root.name == "video-cut-hyperframes-creative" and path.name == "house-style.md":
                text = text.replace("](references/typography.md)", "](typography.md)")
                text = text.replace("](references/motion-principles.md)", "](motion-principles.md)")
                text = text.replace("](palettes/", "](../palettes/")
            if root.name == "video-cut-jianying-editor" and path.relative_to(root).as_posix() == "references/README.md":
                text = text.replace("](demo.py)", "](../examples/)")
                marker = "> 本地安装说明：上游文档中的 demo.py 未随本仓库打包；示例链接已指向本地 examples/，具体功能以对应示例内容为准。\n\n"
                if marker not in text:
                    text = marker + text
            if text != original:
                path.write_text(text, encoding="utf-8", newline="\n")
                changed.append(path.relative_to(root).as_posix())
                changed_count += 1
        entry["adapted_files"] = sorted(set(entry["adapted_files"] + changed))
        entry["skill_md_sha256"] = hashlib.sha256((root / "SKILL.md").read_bytes()).hexdigest()
    manifest["local_reference_repairs"] = {
        "description": "Relocated old monolithic HyperFrames references to the bundled split-domain docs; fixed house-style relative links; preserved Remotion's ffmpeg.md resource name; redirected absent vendored demo links to the local examples directory.",
        "changed_markdown_files": changed_count,
    }
    return changed_count


if __name__ == "__main__":
    path = PROJECT / "video-cut-install-manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    count = repair(manifest)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Updated local references in {count} Markdown files.")
