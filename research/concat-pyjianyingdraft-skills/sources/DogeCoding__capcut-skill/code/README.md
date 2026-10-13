# capcut-skill

面向 **剪映专业版 / CapCut 桌面版** 的独立 OpenClaw（及通用 Agent）技能包：**探测本机草稿目录**、用 **PyPI `pyJianYingDraft`** 生成可打开的工程、**导入 SRT**，以及 **FFmpeg 静音粗剪**。  
实现与维护在本仓库完成，**不依赖**其它指定 GitHub 技能仓库的源码树。

---

## 功能概览

| 能力 | 实现方式 | 说明 |
|------|-----------|------|
| 草稿目录 | `capcut_paths.py` | 自动探测 macOS 常见路径，支持环境变量覆盖 |
| 环境检查 | `check_capcut_env.py` | `ffmpeg` / `ffprobe`、可选 `whisper` CLI、`.venv` 内 `pyJianYingDraft` |
| 列草稿 | `jy_list_drafts.py` | 列出草稿根下子目录名 |
| 特效枚举 | `jy_list_effect_names.py` | 输出 `IntroType` / `TransitionType` / `FilterType` 中文名（JSON） |
| 新建草稿 + 视频 | `jy_create_from_media.py` | 主轨视频，可选音频；可选入场动画、滤镜 |
| 新建草稿 + 字幕 | `jy_import_srt.py` | 主轨视频 + `import_srt` 文本轨；同上特效参数 |
| 口播粗剪 | `rough_cut_silence.py` | 仅 FFmpeg `silencedetect`，去长静音 |
| Whisper 字幕 | `audio_to_srt_whisper.py` | 可选依赖，见 `requirements-optional.txt` |
| 一键流水线 | `jy_film_pipeline.py` | 粗剪 → Whisper → `jy_import_srt` 或仅建草稿 |

---

## 系统要求

- **macOS**（当前脚本以darwin路径为主；Windows 可自行改草稿根）
- **Python 3.10+**（推荐 3.11；与 `pyJianYingDraft` 说明一致更佳）
- **FFmpeg**（含 `ffprobe`）：`brew install ffmpeg`
- **剪映专业版**（或 CapCut）已安装，且能正常创建草稿

---

## 安装

### 1. 克隆本仓库（任选位置）

```bash
git clone git@github.com:DogeCoding/capcut-skill.git
cd capcut-skill
```

### 2. 创建虚拟环境并安装 Python 依赖

```bash
bash scripts/install_deps.sh
```

或手动：

```bash
python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements.txt
```

依赖仅一项：**`pyJianYingDraft`**（从 PyPI 安装，用于写剪映草稿 JSON）。  
若要用 **Whisper 自动生成 SRT**，另见根目录 **`requirements-optional.txt`**（不默认安装）。

### 3. 验证环境

```bash
.venv/bin/python scripts/check_capcut_env.py
# 若希望在缺 ffmpeg 或缺库时返回非零退出码：
.venv/bin/python scripts/check_capcut_env.py --strict
```

---

## 剪映草稿根目录在哪里？

运行：

```bash
python3 scripts/capcut_paths.py
```

常见输出示例（以你机器为准）：

```json
{
  "draft_roots": [
    { "path": "/Users/你的用户名/Movies/JianyingPro/User Data/Projects/com.lveditor.draft", "source": "auto" }
  ]
}
```

若你的草稿不在默认位置，在 **剪映 → 全局设置 → 草稿位置** 查看，然后设置环境变量（二选一）：

```bash
export CAPCUT_DRAFT_ROOT="/绝对路径/.../com.lveditor.draft"
# 或
export JIANYING_DRAFT_ROOT="/绝对路径/.../com.lveditor.draft"
```

再运行 `capcut_paths.py`，会多一条 `source: env`。

---

## 命令详解

以下 **`DRAFT_ROOT`** 表示：`capcut_paths.py` 打印的某个 `draft_roots[].path`（整段复制为字符串）。

所有 **`jy_*` 脚本必须用**：

```bash
.venv/bin/python scripts/<脚本>.py ...
```

（系统 Python 未安装 `pyJianYingDraft` 时会报错。）

### `jy_list_drafts.py` — 列出草稿名

```bash
.venv/bin/python scripts/jy_list_drafts.py --draft-root "$DRAFT_ROOT"
```

输出 JSON：`{ "ok": true, "drafts": ["草稿A", "草稿B", ...] }`

---

### `jy_create_from_media.py` — 新建草稿 + 主视频（+ 可选音频）

**必填**

- `--draft-root`：草稿根目录（见上）
- `--name`：新草稿文件夹名（剪映里显示的名字）
- `--video`：主视频素材的**绝对路径**

**常用可选**

- `--audio`：独立音频文件绝对路径（从时间线 0 秒对齐；长度会与视频时长取短）
- `--intro`：入场动画枚举名（中文，与 `IntroType` 一致）；可先跑 `jy_list_effect_names.py --kind intro`
- `--filter`：滤镜枚举名（`FilterType`）；`--filter-intensity` 默认 `80`（0–100）
- `--width` / `--height`：画布分辨率。横屏默认 `1920 1080`；竖屏示例：`1080 1920`
- `--fps`：默认 `30`
- `--allow-replace`：已存在同名草稿时**删除并重建**

**示例**

```bash
.venv/bin/python scripts/jy_create_from_media.py \
  --draft-root "$DRAFT_ROOT" \
  --name "我的口播_20260326" \
  --video "/Users/你/素材/main.mp4" \
  --audio "/Users/你/素材/voice.wav" \
  --width 1080 --height 1920 \
  --allow-replace
```

成功后终端打印 JSON，含 `draft_path`。  
**然后在剪映里**：若列表未刷新，可**重启剪映**或进出其它草稿一次。

---

### `jy_import_srt.py` — 新建草稿 + 视频 + SRT 字幕

**必填**

- `--draft-root`、`--name`、`--video`、`--srt`（SRT 文件绝对路径）

**可选**

- `--track-name`：文本轨名称，默认 `subtitle`
- `--intro` / `--filter` / `--filter-intensity`：与 `jy_create_from_media.py` 相同
- `--width` / `--height` / `--fps` / `--allow-replace`：同上

**示例**

```bash
.venv/bin/python scripts/jy_import_srt.py \
  --draft-root "$DRAFT_ROOT" \
  --name "带字幕演示" \
  --video "/Users/你/素材/main.mp4" \
  --srt "/Users/你/素材/captions.srt" \
  --allow-replace
```

SRT 编码建议 **UTF-8**（带 BOM 亦可）。

---

### `jy_list_effect_names.py` — 列出剪映特效相关枚举名（JSON）

`pyJianYingDraft` 中入场、转场、滤镜等多为**中文枚举名**。本脚本便于 Agent/用户在命令行填 `--intro`、`--filter`。

```bash
.venv/bin/python scripts/jy_list_effect_names.py --kind all
.venv/bin/python scripts/jy_list_effect_names.py --kind intro
```

**说明**：当前 `jy_create_from_media.py` / `jy_import_srt.py` 仅接入了**单段**上的入场与滤镜；**转场**需时间线上至少两段视频，后续可扩展多段脚本。

---

### `audio_to_srt_whisper.py` — 音视频转 SRT（可选）

依赖系统 PATH 中的 **`whisper`**（如 `pip install openai-whisper`），不在默认 `requirements.txt` 中。

```bash
.venv/bin/python scripts/audio_to_srt_whisper.py "/绝对路径/成片.mp4" \
  --output-dir "/绝对路径/out" --model base --language Chinese
```

成功后 stdout 打印 JSON，含 `srt` 路径；再接 `jy_import_srt.py`。

---

### `jy_film_pipeline.py` — 粗剪 + Whisper + 建草稿（一键）

使用 **Skill 根目录下 `.venv` 的 Python** 依次调用 `rough_cut_silence.py`、`audio_to_srt_whisper.py`、`jy_import_srt.py`（或无生字幕时 `jy_create_from_media.py`）。草稿根与 `capcut_paths` 逻辑一致，也可用 `--draft-root` 覆盖。

```bash
.venv/bin/python scripts/jy_film_pipeline.py \
  --video "/path/to/jimeng_output.mp4" \
  --name "漫剧_某集_草稿" \
  --allow-replace \
  --intro "斜切" \
  --filter "亮肤"
```

常用开关：`--no-rough-cut`、`--no-whisper`、`--srt /path/existing.srt`、`--whisper-model small`。

**注意**：若传入 **`--srt`** 且仍启用粗剪，字幕时间轴可能与剪切后视频不对齐；应保证 SRT 与**最终入轨视频**同源，或改用 `--no-rough-cut` / 先粗剪再对该 mp4 跑 Whisper。

---

### `rough_cut_silence.py` — 口播粗剪（仅 FFmpeg，不进剪映）

在把素材丢进剪映**之前**，可先去掉长于阈值的静音段。

**用法**

```bash
# 只看会保留哪些片段（不写文件）
python3 scripts/rough_cut_silence.py 输入.mp4 /dev/null --dry-run

# 真正输出
python3 scripts/rough_cut_silence.py 输入.mp4 输出.mp4
```

**调参**

| 参数 | 默认 | 含义 |
|------|------|------|
| `--min-silence` | `0.45` | 连续静音 ≥ 该秒数才判为「静音段」 |
| `--noise-db` | `-35` | `silencedetect` 噪声阈值（dB，越小越严） |
| `--pad` | `0.04` | 有声段边界向内收缩，减少砍到气口 |

**说明**

- 会 **重新编码**（`libx264` + `aac`），画质/码率与源可能不同。
- **不能**识别「说错重说」类语义问题，仅按音量/静音切。

---

## 与 OpenClaw 影视项目

即梦成片、漫剧目录与 TTS 建议见 **`references/FILM_OPENCLAW.md`**。

---

## 与 pyJianYingDraft / 剪映版本的限制

详见仓库内 **`references/PYJIANGYING_LIMITS.md`**。要点：

- **macOS 不能使用**该库自带的 **Windows GUI 自动导出**；导出请在剪映内手动完成。
- **剪映 6+** 若对旧草稿加密，**模板模式**可能打不开；**从零 `create_draft`** 一般仍可用（以你本机为准）。

---

## OpenClaw 部署

将本目录同步到 OpenClaw 工作区技能目录（勿必带上 `.venv` 也可，但建议在目标机再执行一次 `python3 -m venv .venv && pip install -r requirements.txt`）：

```bash
rsync -a --delete --exclude .git --exclude .venv \
  /path/to/capcut-skill/ \
  ~/.openclaw/workspace/skills/capcut-skill/
```

然后在目标机器上进入 `~/.openclaw/workspace/skills/capcut-skill` **创建 `.venv` 并安装依赖**。

各子 agent 若共用 `~/.openclaw/workspace`，即可通过 **`SKILL.md`** 发现本技能。

---

## 常见问题

**Q：`check_capcut_env.py` 显示 pyJianYingDraft 为 false**  
A：是否在 **`capcut-skill` 根目录** 创建了 `.venv` 并执行了 `pip install -r requirements.txt`？

**Q：剪映里看不到新草稿**  
A：重启剪映，或打开任意旧草稿再返回列表。

**Q：想自动点导出**  
A：本 Skill 不包含 macOS 上的剪映 UI 自动化；可自行用 AppleScript/快捷指令等，风险与版本强相关。

**Q：`rough_cut_silence` 切太碎或切不动**  
A：调 `--min-silence`、`--noise-db`；或先用 `--dry-run` 看 `keep_segments`。

---

## License

MIT
