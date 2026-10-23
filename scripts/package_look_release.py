"""Package the new offline look release; keep every alpha.1 asset immutable."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT=Path(__file__).resolve().parents[1]
TAG="v0.1.0-alpha.2"
BUNDLE=ROOT/"product/.runtime/look-release-20261024/bundle"
ARTIFACTS=ROOT/"docs/releases"/TAG/"artifacts"


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle,"sha256").hexdigest()


def main():
    ARTIFACTS.mkdir(parents=True,exist_ok=True)
    archive=ARTIFACTS/f"agent-video-kit-{TAG}-cp313-win_amd64.zip"
    if archive.exists():raise ValueError("An existing release archive is preserved")
    manifest=json.loads((BUNDLE/"manifest.json").read_bytes())
    version={"release":TAG,"cli_version":"0.1.1","manifest_sha256":"sha256:"+sha(BUNDLE/"manifest.json"),
             "schema_sha256":manifest["schema_sha256"],"look_catalog_version":"1.0.0","look_count":100,
             "look_catalog_sha256":sha(ROOT/"product/src/ai_ad_editor/look_data/catalog.json"),
             "target":"cp313-win_amd64","network":"disabled","python_included":False,"ffmpeg_included":False,
             "status":"local-tested-build","public_github_release_created":False}
    (ARTIFACTS/"version.json").write_text(json.dumps(version,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    rows=[(p,"bundle/"+p.relative_to(BUNDLE).as_posix()) for p in BUNDLE.rglob("*") if p.is_file()]
    rows += [(ARTIFACTS/"version.json","version.json"),(ROOT/"LICENSE","LICENSE")]
    for filename in ("USAGE.md","THIRD_PARTY.md"):
        rows.append((ARTIFACTS.parent/filename,filename))
    with zipfile.ZipFile(archive,"x",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as zipped:
        for path,name in sorted(rows,key=lambda x:x[1]):zipped.write(path,name)
    files=[archive, ARTIFACTS/"version.json"]
    (ARTIFACTS/"SHA256SUMS.txt").write_text("".join(sha(p)+"  "+p.name+"\n" for p in files),encoding="ascii")
    print(json.dumps({"archive":str(archive),"bytes":archive.stat().st_size,"sha256":sha(archive),"version":version}))


if __name__=="__main__":main()
