---
name: capcut-jianying
description: "剪映专业版/CapCut 桌面：macOS 草稿路径、pyJianYingDraft 建草稿与 SRT 字幕、FFmpeg 静音粗剪；独立实现，依赖 PyPI+ffmpeg"
allowed-tools: Read, Write, Bash, exec
---

# 剪映 / CapCut Skill（独立版）

当用户需要 **剪映（或 CapCut）桌面版草稿**、**导入字幕**，或 **口播视频按静音粗剪** 时使用本 Skill。

## 依赖（本仓库内自洽）

1. **系统**：`ffmpeg`、`ffprobe`（`brew install ffmpeg`）。  
2. **Python 库**：在 **`capcut-skill` 根目录** 使用虚拟环境安装：
   ```bash
   cd /path/to/capcut-skill
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```
   仅含 PyPI 包 **`pyJianYingDraft`**（生成 `draft_content.json`），**不**依赖任何指定 GitHub 技能仓库源码。

## 脚本一览（务必用 `.venv/bin/python` 跑带 `jy_` 的脚本）

| 脚本 | 作用 |
|------|------|
| `scripts/capcut_paths.py` | 打印草稿根目录 JSON（`CAPCUT_DRAFT_ROOT` 可覆盖） |
| `scripts/check_capcut_env.py` | 检查 ffmpeg、可选 `whisper`、`.venv` 内 pyJianYingDraft |
| `scripts/jy_list_drafts.py` | 列出草稿名 |
| `scripts/jy_list_effect_names.py` | JSON 列出入场/转场/滤镜等**中文枚举名**（供 `--intro` / `--filter`） |
| `scripts/jy_create_from_media.py` | 新建草稿 + 主视频（可选音频轨；可选 `--intro` / `--filter`） |
| `scripts/jy_import_srt.py` | 新建草稿 + 视频 + **SRT 字幕轨**（同上特效参数） |
| `scripts/rough_cut_silence.py` | **仅 FFmpeg**：按静音粗剪输出新 MP4（可先于剪映处理素材） |
| `scripts/audio_to_srt_whisper.py` | 可选：PATH 中 `whisper` → 生成 SRT（见 `requirements-optional.txt`） |
| `scripts/jy_film_pipeline.py` | 漫剧/口播一键：可选粗剪 → 可选 Whisper → 建草稿（+ 字幕） |

## Agent 推荐路径（OpenClaw）

- Skill 同步副本：`/Users/graves/.openclaw/workspace/skills/capcut-skill/`  
- 开发仓库：`/Users/graves/Workspace/Skills/capcut-skill/`  

自检：

```bash
python3 /Users/graves/.openclaw/workspace/skills/capcut-skill/scripts/capcut_paths.py
/Users/graves/.openclaw/workspace/skills/capcut-skill/.venv/bin/python /Users/graves/.openclaw/workspace/skills/capcut-skill/scripts/check_capcut_env.py
```

## 原则

- **路径**：`read`/`exec` 使用**绝对路径**；勿依赖未展开的 `~`。  
- **限制**：macOS **不能**使用 pyJianYingDraft 自带的 Windows GUI 自动导出；生成草稿后在剪映内手动导出。详见 `references/PYJIANGYING_LIMITS.md`。  
- **口播精剪**：`rough_cut_silence.py` 只做静音阈值切割；语义级删句需人工或其它 ASR+LLM 流水线。  
- **详细参数与示例**：以 **`README.md`** 为准。  
- **与即梦/漫剧目录协作**：见 **`references/FILM_OPENCLAW.md`**。
