# 本地 HDemucs 人声/伴奏分离契约 v0.1

| 项目 | 内容 |
|---|---|
| 文档编号 | SPEC-HDEMUCS-001 |
| 日期 | 2026-10-16，Asia/Taipei |
| 状态 | 有效 |
| Engine | `torchaudio-hdemucs-local-v1` |
| 协议 | `agent-video-hdemucs-separation-v1` |
| 运行边界 | 原生 Windows、显式本地 Python/权重/证据、FFmpeg；无运行时下载或服务请求 |

## 1. 功能与依赖

本引擎用已安装 TorchAudio 的 `hdemucs_high` 架构执行真实模型推理，直接加载显式本地 `.pt/.pth` 状态字典。模型包含 drums/bass/other/vocals 四源，当前产品输出 **vocals 和 accompaniment 两轨**：人声取模型预测，伴奏为原输入减预测人声，保留混音一致性。它与旧的 `demucs-local-v1` metadata 登记项分别命名，旧项仍结构化拒绝推理。

登记的 Python `.exe` 必须已包含 Torch、TorchAudio、numpy。构造架构后用 `torch.load(weights_only=True)` 和严格参数键/形状匹配加载权重；不调用会获取权重的 bundle API。CPU/CUDA 必须显式登记，不自动回退、安装依赖或下载模型。

架构与来源依据为 [TorchAudio 官方模型说明](https://docs.pytorch.org/audio/stable/generated/torchaudio.pipelines.HDEMUCS_HIGH_MUSDB.html)及[官方模型源码](https://github.com/pytorch/audio/blob/main/src/torchaudio/models/_hdemucs.py)。[TorchAudio 代码许可证](https://github.com/pytorch/audio/blob/main/LICENSE)与模型权重、训练数据、源音频及输出权利分别核验；本次开发验证权重许可仍记为 unverified。

## 2. Agent 调用

```powershell
python -m ai_ad_editor audio adapter register --project .\workspace\demo `
  --adapter-id music_local --engine torchaudio-hdemucs-local-v1 `
  --model-path E:\models\hdemucs_high_musdbhq_only.pt `
  --executable E:\python\python.exe --evidence E:\models\evidence.json `
  --device cpu --threads 4 --segment-seconds 6 --overlap 0.25 --dry-run
```

确认计划后去掉 `--dry-run` 正式登记，再执行：

```powershell
python -m ai_ad_editor audio adapter inspect --project .\workspace\demo --adapter-id music_local
python -m ai_ad_editor audio separate --project .\workspace\demo `
  --asset-id source_audio --adapter-id music_local `
  --vocals-asset-id vocals_01 --accompaniment-asset-id accompaniment_01 `
  --apply --track-id track_audio_1 --stem vocals --dry-run
```

正式运行会保存 before-audio-separate 快照、两个资产和台账依赖，选择的 stem 可进入现有 audio 轨道；`--stem accompaniment` 可应用伴奏。使用 `--replace-track` 清空现有目标轨道须显式指定。仅分离不入轨时，也可传本地 `--input`；模型入轨要求已摄取的 `--asset-id`。

输出参数为 `--vocals-output`/`--accompaniment-output`，默认为项目内 assets/derived/<asset-id>.wav。旧 center/side 参数名保留为参数别名，native 响应中的语义键始终为 vocals/accompaniment；mid/side 和 command-json 仍保留 center/side。不同引擎的 stem 选择不可混用。

## 3. 登记与完整性

| 项目 | 约束 |
|---|---|
| Registry | `models/audio-adapters.json`，跟随项目元数据事务、快照、恢复和项目包 |
| 输入文件 | 现有非空本地权重、Python `.exe`、证据文件；拒绝远程/UNC 和 shell wrapper |
| 六项文件摘要 | 权重、Python、证据、worker、DSP、controller 各自 SHA-256/大小/路径 |
| 配置 | device=cpu/cuda；threads=1..32；segment-seconds=1..20；overlap=0..0.75 |
| 模型规格 | 44,100 Hz、双声道、固定四源及严格架构 |
| Manifest | 绑定模型、实现、运行环境、配置、协议和 rights_ref；执行前后再次核验 |
| 响应摘要语义 | adapter.model_sha256 为权重文件摘要；separation.model_sha256 沿既有模型集成约定记录完整登记 manifest 摘要 |
| 权利记录 | `audio_adapter_<id>`，kind=model-adapter，SHA 为完整登记 manifest |

登记、list/inspect、dry-run 不导入 Torch、不读取 checkpoint 内容做推理、不启动 worker。登记成功只证明文件和配置可复核，兼容性由正式推理确认。外部模型/Python 不随项目包分发。

## 4. 推理、音质与资源

FFmpeg 仅按 file/pipe 协议解码为 44.1 kHz 双声道 float32 PCM。worker 通过 `-I -B` 启动，使用项目 E 盘缓存，禁止 Python socket/DNS/HTTP；响应必须包含 network=disabled、空 blocked_network_events、输入/源文件/manifest 摘要和完整采样数。

DSP 使用磁盘 memmap 保存输入、输出累加及权重；RAM 主要由一个分段和模型占用。全局归一化包含反相双声道的方差回退，纯零音频不调用模型。分段允许末段补零，但只输出原样本范围；正三角权重 overlap/add 归一化覆盖首尾每个采样点，不独立归一化两轨。伴奏为原混音减人声。

最终 WAV 为 `pcm_f32le`，峰值可能超出 ±1，保留数值而不静默削波。`--sample-rate` 接受既有白名单；重采样后精确补齐/截取至 round(源解码采样数×目标采样率/44100)。时长上限 7200 秒；解码/编码单阶段超时 1800 秒，worker 超时 7200 秒。此预算不证明两小时输入的实际内存、吞吐或音质已验收。

## 5. 写入、错误与权利门禁

| 错误码 | 含义 |
|---|---|
| `MODEL_ADAPTER_HASH_INVALID` | 文件、实现或 manifest 与登记不一致 |
| `SEPARATION_SOURCE_HASH_MISMATCH` | 已摄取源资产内容被更改 |
| `SEPARATION_LOCAL_ARTIFACT_INVALID` | 本地文件缺失、为空或不符合要求 |
| `SEPARATION_AUDIO_DECODE_FAILED` | 音频解码、采样格式或时长预算失败 |
| `SEPARATION_WORKER_FAILED` | worker 非零退出、响应缺失、协议/摘要/网络状态不符；底层原因写入结构化 cause |
| `SEPARATION_OUTPUT_INVALID` | 指标非有限、PCM 哈希/长度、WAV 编码或采样规格不符 |
| `SEPARATION_INTEGRITY_FAILED` | 推理或编码过程中输入/登记内容发生变化 |
| `AUDIO_SEPARATION_MODEL_REVIEW` | 成功后仍需复核泄漏、音乐残留、接缝、峰值及许可 |

输出必须是两个不同、尚不存在、位于项目内的 `.wav`。生成、编码、项目校验或后续元数据提交失败时清理本次 WAV；原有项目、锁文件、台账和 registry 由元数据事务恢复。cache job 在终止后清理，Windows memmap 显式关闭。幂等重放不重复推理。

两个衍生资产均依赖源素材和登记模型的 Rights Ledger 记录；源素材已核验不能绕过未核验模型。运行成功不授予商业发布权；默认 unverified/internal 继续阻断 commercial_ad。

## 6. 验证与未完成部分

专项测试覆盖分段首尾/接缝/DC、静音/反相、非有限值、登记/dry-run、篡改、采样率和精确时长、协议异常、网络尝试、模型依赖、二次编码失败、提交失败回滚、幂等、项目包和恢复。真实权重 CPU/CUDA 实测及限制见[实测记录](../validation/HDemucs本地人声伴奏分离实测_2026-10-16.md)。

自然歌曲/噪声/多人对白、跨模型兼容、人工听感、长音频吞吐和资源上限仍待扩展；当前不输出独立四源、多总线或空间音频，也不据一个受控样例声称全面达到剪映音频质量。
