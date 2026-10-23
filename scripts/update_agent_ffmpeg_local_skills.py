"""Update the existing 17 local Skills to the reviewed alpha.2 installation."""
from pathlib import Path
import hashlib
import json
import re

ROOT=Path(__file__).resolve().parents[1]
TAG="v0.1.0-alpha.2"


def main():
    config=json.loads((ROOT/"local/agent-ffmpeg/runtime.json").read_bytes())
    installed=Path(config["installed_directory"])
    receipt=json.loads((installed/"receipt.json").read_bytes())
    if config["release"]!=TAG or receipt["manifest_sha256"]!=config["manifest_sha256"]:
        raise ValueError("Install and activate the reviewed alpha.2 build first")
    manifest_path=ROOT/"agent-ffmpeg-local-install-manifest.json"
    manifest=json.loads(manifest_path.read_bytes())
    editor=ROOT/"skills/agent-ffmpeg-local-editor"
    launcher=editor/"scripts/run.py"
    text=launcher.read_text("utf-8")
    text=re.sub(r"^MANIFEST = .*$", "MANIFEST = "+repr(config["manifest_sha256"]), text, flags=re.M)
    text=re.sub(r"^RELEASE = .*$", "RELEASE = "+repr(TAG), text, flags=re.M)
    launcher.write_text(text,encoding="utf-8",newline="\n")
    descriptions={
        "agent-ffmpeg-local-editor":"Edit local advertising videos with the installed Agent Video Kit CLI, including 100 offline style/filter presets. Use for setup, look search, previews, editing, rendering and delivery.",
        "agent-ffmpeg-local-timeline":"Compose local video timelines, keyframes, camera presets, transitions, masks, speed curves and apply 100 built-in style/filter presets to clips or global adjustments using the installed CLI.",
        "agent-ffmpeg-local-quality":"Review locally rendered video, pixels, masks, audio, scopes and manifests. Compare previews of the 100 offline style/filter presets and verify their actual rendered output.",
        "agent-ffmpeg-local-rights-ledger":"Record source, license, creator and local evidence for media, fonts, templates, LUTs and models. Audit the 100 bundled MIT look presets and their project-local license evidence."
    }
    for row in manifest["skills"]:
        path=ROOT/"skills"/row["name"]/"SKILL.md"
        text=path.read_text("utf-8").replace("v0.1.0-alpha.1",TAG)
        if row["name"] in descriptions:
            text=re.sub(r"^description: .*$", "description: "+json.dumps(descriptions[row["name"]]), text, flags=re.M)
            marker="## Offline look presets"
            if marker not in text:
                text += ("\n"+marker+"\n\nUse `look list`, `look inspect`, `look preview` and `look apply` for 100 installed MIT style presets. "
                         "Read [the look workflow](../agent-ffmpeg-local-editor/references/looks.md) before choosing a target, strength or publication settings. "
                         "These are creative SDR looks; they do not establish official branded-filter or CapCut equivalence.\n")
        path.write_text(text,encoding="utf-8",newline="\n")
        row["skill_md_sha256"]=hashlib.sha256(path.read_bytes()).hexdigest()
    runtime=editor/"references/runtime.md"
    text=runtime.read_text("utf-8").replace("v0.1.0-alpha.1",TAG).replace("scripts/install_agent_ffmpeg_local.py", "scripts/install_look_release.py --activate")
    if "100 offline looks" not in text:
        text += "\n## 100 offline looks\n\nRead [looks.md](looks.md). `look apply` copies LUT/license/provenance into the project. Built-in preset evidence uses relative project paths; unrelated user media evidence still needs review after relocation.\n"
    runtime.write_text(text,encoding="utf-8",newline="\n")
    manifest.update(release=TAG,manifest_sha256=config["manifest_sha256"],look_catalog_version="1.0.0",look_count=100)
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
    print(json.dumps({"ok":True,"release":TAG,"updated_skills":len(manifest["skills"]),"look_presets":100}))


if __name__=="__main__":main()
