"""Download selected public skill descriptions as research evidence, without activating them."""

import concurrent.futures
import json
from pathlib import Path
import re
import sys
import urllib.parse

from collect_github_skills import ROOT, get

TARGETS = {
    "ComposioHQ/awesome-claude-skills": ["competitive-ads-extractor/SKILL.md"],
    "davila7/claude-code-templates": ["cli-tool/components/skills/business-marketing/paid-ads/SKILL.md"],
    "garytan023/video-content-teardown": ["video-content-teardown/SKILL.md"],
    "fralapo/awesome-agent-skills": ["skills/video-editor/SKILL.md", "skills/creative-director/SKILL.md"],
    "calesthio/OpenMontage": [".agents/skills/create-video/SKILL.md", ".agents/skills/video-edit/SKILL.md", ".agents/skills/music-to-video/SKILL.md"],
    "heygen-com/hyperframes": ["skills/general-video/SKILL.md", "skills/music-to-video/SKILL.md", "skills/product-launch-video/SKILL.md", "skills/talking-head-recut/SKILL.md"],
    "coreyhaines31/marketingskills": ["skills/ad-creative/SKILL.md", "skills/ads/SKILL.md"],
    "sickn33/agentic-awesome-skills": ["skills/ad-creative/SKILL.md", "skills/viral-video-teardown-remake/SKILL.md"],
    "browser-use/video-use": ["SKILL.md"],
    "alirezarezvani/claude-skills": ["marketing-skill/skills/ad-creative/SKILL.md", "marketing-skill/video-content-strategist/skills/video-content-strategist/SKILL.md"],
    "Vincentwei1021/video-shotcraft": ["SKILL.md"],
    "remotion-dev/skills": ["skills/remotion-best-practices/SKILL.md", "skills/remotion-create/SKILL.md"],
    "irinabuht12-oss/marketing-skills": ["skills/ad-copy-variant-generator/SKILL.md", "skills/competitor-creative-analysis/SKILL.md", "skills/creative-fatigue-detection/SKILL.md"],
    "luoluoluo22/jianying-editor-skill": ["SKILL.md", "LICENSE"],
    "ericosiu/ai-marketing-skills": ["net-new-video-editor/SKILL.md", "video-clip-pipeline/SKILL.md", "agentic-video-understanding/SKILL.md"],
    "FireRedTeam/FireRed-OpenStoryline": [".storyline/skills/default_editing_workflow_skill/SKILL.md", ".storyline/skills/ai_transition_editing_skill/SKILL.md"],
    "Agentchengfeng/chengfeng-videocut-skills": ["plugins/chengfeng-videocut/skills/chengfeng-cut/SKILL.md", "plugins/chengfeng-videocut/skills/chengfeng-visual/SKILL.md"],
    "aaron-he-zhu/aaron-marketing-skills": ["ad/orchestrate/ad-creative-builder/SKILL.md", "ad/orchestrate/ad-test-designer/SKILL.md"],
    "zubair-trabzada/ai-marketing-claude": ["skills/market-ads/SKILL.md"],
    "digitalsamba/claude-code-video-toolkit": [".claude/skills/ffmpeg/SKILL.md", ".claude/skills/remotion/SKILL.md"],
    "liuluhaixiu/DaVinci-AutoEdit-Agent": ["skills/davinci-autoedit-agent/SKILL.md"],
    "ivangfalco/ads-skills": [".claude/skills/meta-ads/SKILL.md", "LICENSE"],
    "ALBEDO-TABAI/video-expert-analyzer": ["SKILL.md"],
    "isYangs/jianying-editor-skill": ["SKILL.md"],
    "znyupup/ai-video-editing-skill": ["SKILL.md"],
    "liyupi/ai-promo-video-maker": ["SKILL.md"],
    "leosssvip-dot/remotion-ad-video-skill": ["skills/remotion-ad-video/SKILL.md"],
    "robonuggets/hyperframes-helper": [".claude/skills/hyperframes-helper/SKILL.md", "LICENSE", "README.md"],
    "kangarooking/promo-creator-skills": ["SKILL.md", "skills/promo-creator/SKILL.md"],
    "nopefallacy/vertical-video-editing-skills": ["skills/video-editing/SKILL.md"],
    "appergb/ClipSkills": ["SKILL.md", "clip-skills/SKILL.md", "LICENSE"],
    "iart-ai/ad-video-skills": ["skills/ad-creative-video/SKILL.md", "README.md"],
    "SamurAIGPT/Generative-Media-Skills": ["library/visual/ad-creative/SKILL.md"],
    "DotanVG/video-director-skill": ["video-director/SKILL.md", "LICENSE"],
    "Killusions/open-video-use": ["SKILL.md"],
    "Rajbharti06/Ultimate-Video-Editing-Skills": ["skills/ultimate-video-editor/SKILL.md"],
    "xsourabhsharma/remotion-marketing-video-skill": ["SKILL.md"],
    "riffkit/skills": ["ugc-ad-creative/SKILL.md"],
    "rendleyhq/video-editing-skill": ["SKILL.md", "skills/video-editing/SKILL.md"],
}


def main():
    metadata = {r["repository"]: r for r in json.loads((ROOT / "github-repository-snapshot.json").read_text(encoding="utf-8"))["repositories"] if "repository" in r}
    extra_path = ROOT / "additional-public-page-snapshot.json"
    if extra_path.exists():
        metadata.update({r["repository"]: r for r in json.loads(extra_path.read_text(encoding="utf-8"))})
    inspections = {r["repository"]: r for r in json.loads((ROOT / "skill-file-inspections.json").read_text(encoding="utf-8"))}
    requested = set(sys.argv[1:])
    jobs = [(repo, path) for repo, paths in TARGETS.items() for path in paths if not requested or repo in requested]

    def fetch(job):
        repo, path = job
        ref = metadata[repo]["default_branch"]
        url = f"https://raw.githubusercontent.com/{repo}/{ref}/{urllib.parse.quote(path, safe='/')}"
        row = {"repository": repo, "path": path, "ref": ref, "raw_url": url, "source_url": f"https://github.com/{repo}/blob/{ref}/{urllib.parse.quote(path, safe='/')}"}
        try:
            try:
                body = get(url).decode("utf-8-sig")
                row["fetch_method"] = "raw"
            except Exception:
                page = get(row["source_url"]).decode("utf-8")
                body = None
                def find_lines(node):
                    if isinstance(node, dict):
                        if isinstance(node.get("rawLines"), list):
                            return node["rawLines"]
                        for value in node.values():
                            found = find_lines(value)
                            if found is not None:
                                return found
                    elif isinstance(node, list):
                        for value in node:
                            found = find_lines(value)
                            if found is not None:
                                return found
                    return None
                for script in re.findall(r"<script[^>]*>(.*?)</script>", page, re.S):
                    if '"rawLines"' in script:
                        payload = json.loads(script)
                        lines = find_lines(payload)
                        if lines is not None:
                            body = "\n".join(lines) + "\n"
                            break
                if body is None:
                    raise ValueError("GitHub page did not expose file content")
                row["fetch_method"] = "github_blob_embedded_data"
            destination = ROOT / "sources" / repo.replace("/", "__") / "selected" / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(body, encoding="utf-8")
            row["local_path"] = str(destination)
            row["verified"] = True
            row["characters"] = len(body)
            row["header_excerpt"] = body[:2500]
            row["dependency_mentions"] = [s.strip()[:500] for s in body.splitlines() if re.search(r"docker|wsl|windows|macOS|linux|API.key|API key|ffmpeg|remotion|hyperframes", s, re.I)][:18]
        except Exception as exc:
            row["verified"] = False
            row["error"] = str(exc)
        return row

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(fetch, jobs))
    saved_path = ROOT / "verified-skill-sources.json"
    existing = json.loads(saved_path.read_text(encoding="utf-8")) if saved_path.exists() else []
    merged = {(r["repository"], r["path"]): r for r in existing + rows}
    saved_path.write_text(json.dumps(list(merged.values()), ensure_ascii=False, indent=2), encoding="utf-8")
    for row in rows:
        print(json.dumps({k: row.get(k) for k in ["repository", "path", "verified", "error"]}, ensure_ascii=True))


if __name__ == "__main__":
    main()
