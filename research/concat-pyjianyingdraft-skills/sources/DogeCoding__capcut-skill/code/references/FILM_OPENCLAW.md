# 与 OpenClaw 影视工作流的衔接

本 Skill 解决的是 **剪映桌面版草稿 JSON**：把本地视频（含即梦等工具导出的成片）放进时间线、写入 **SRT 字幕**、可选 **入场动画 / 滤镜**（见 `pyJianYingDraft` 枚举）。**转场**需要至少两段视频片段，单段成片请进剪映后再加片或后续扩展多段脚本。

## 上游：即梦 / 漫剧素材

- OpenClaw 工作区内常见技能：**`jimeng-video-volc-sdk`**（即梦视频样片/SDK 封装）。输出 **mp4** 后，用本 Skill 的 `jy_create_from_media.py` 或一键 `jy_film_pipeline.py` 写入草稿根。
- 漫剧工程示例目录（本机路径以你仓库为准）：`film-projects/零下一百度生存日记漫剧/成片/` 等。将 **成片 mp4** 作为 `--video` 即可。

## 推荐流水线

1. **粗剪（可选）**：`rough_cut_silence.py` 按静音去长间隙；语义级删句需 ASR+人工或其它工具。
2. **字幕（可选）**：`audio_to_srt_whisper.py`（需系统 PATH 中有 `whisper`，见 `requirements-optional.txt`）→ `jy_import_srt.py`。  
   - 若使用 **自备 SRT** 且同时做粗剪，SRT 时间轴必须与 **最终入轨的视频** 一致；否则请 **`--no-rough-cut`** 先对齐流程，或先粗剪再对 **剪切后文件** 跑 Whisper。
3. **一键**：`jy_film_pipeline.py`（粗剪 → Whisper → 建草稿+字幕），支持 `--intro` / `--filter`。
4. **枚举名**：`jy_list_effect_names.py --kind all` 输出 JSON，供填 `--intro`、`--filter`。

## 配音（TTS）

剪映 **内置朗读音色** 无稳定公开 API，本 Skill **不**模拟剪映客户端内 TTS。可行做法：

- 使用 **火山引擎 / 豆包 / 其它 TTS API** 导出 **wav/mp3**，再用 `jy_create_from_media.py --audio` 与视频对齐（从 0s）；或先混音进单条 mp4 再仅铺视频轨。
- 若后续在 OpenClaw 增加专用 TTS Skill，仅把 **密钥放在环境变量或本机配置**，勿写入仓库。

## 与 `MEMORY.md` / `TOOLS.md`

Agent 可在 workspace 的 `MEMORY.md` 中检索 `film-projects`、`jimeng`、`capcut` 等关键词；工具列表以 `TOOLS.md` 为准，部署本 Skill 后可在该文件中保留 **capcut-skill** 的绝对路径与自检命令。
