# 离线音频伸缩与 PCM 输出契约

| 项目 | 内容 |
|---|---|
| 文档编号 | SPEC-AUDIO-STRETCH-001 |
| 状态 | 有效 |
| 日期 | 2026-10-17 |

项目可显式配置 `settings.audio_stretch`，选择已有本地 Rubber Band R3 CLI 的 whole-clip offline study/process。生产运行不会安装、下载或查找线上引擎。未配置项目继续使用 FFmpeg atempo；速度为 1 的段直接通过 anull，避免不必要的伸缩；同源旧版 4 ms 恒速控制也通过，不把它记作旧版失败。显式 null 与未配置等价。

配置字段为 `engine: rubberband-r3-offline-v1`、`executable`、`sha256`、`dependencies: [{path, sha256}]`、`license_path`、`license_sha256` 和 `license_spdx`。摘要为 `sha256:` 加 64 位小写十六进制。路径须是已有本地文件；每个依赖非空且至多 64 MiB。Windows 要求原生 `.exe`，同目录 `sndfile.dll` 显式登记。未知配置字段拒绝。许可证登记仅保留来源证据，不自动接受所有用途。

渲染计划保留全部程序、依赖、许可证、FFmpeg 和原音频摘要；实际执行持 Windows 只读锁至渲染结束，规划后变更拒绝。`--dry-run` 只规划，不解码、不执行离线引擎、不创建 PCM 缓存。

音频先重采样至 48 kHz，再按全局采样点四舍五入裁切，以 32-bit float WAV 保留 1..8 声道。输入或输出单份 PCM 上限 512 MiB；预算在解码前检查。真实输入短于声明范围时失败，禁止补静音冒充成功。WAV 检查拒绝截断、异常长度、非浮点格式、NaN/Inf 和丢声道。

整段音频只执行一次 R3，使用 `-3 --no-threads --centre-focus -t RATIO --timemap FILE`。原嵌套曲线的累计输入/输出采样边界构成严格递增映射，最多 16385 个锚点，计划包含真实起止端点；传给 R3 的文件只包含内部锚点，0→0 会触发原生零长比率/NaN，端点由输入长度与整体比率表达。无内部锚点则不传 timemap。检测到引擎 NaN/Inf 警告同样失败。倒放在离线伸缩后执行。时间图约束引擎的伸缩分配，不证明每个瞬态精确命中锚点；音高、瞬态、相位和听感分别验收。

缓存键包含输入、程序/依赖、FFmpeg、映射、声道/采样数、方向和实现文件摘要。libsndfile 的 PEAK 区块含当前时间，原始引擎 WAV 先记录摘要，再将全部 float PCM 字节写入仅含固定 fmt/data 的 WAV，去除随时间变化的元数据；采样不改写。临时 WAV 在渲染临时目录中自动清理。取消不发布缓存；同一计划已有不同字节时 `AUDIO_STRETCH_CACHE_CONFLICT`，保留旧文件。输入/输出真实采样数必须分别等于计划，非零输入声道不得变成全静音。

MKV 增加 `pcm_s24le`、`pcm_s32le`、`pcm_f32le`，保留原有 16-bit PCM；不向 PCM 编码器传入码率。MP4 继续使用兼容音频编码，PCM 明确拒绝；WebM 使用 Opus。浮点派生文件可供独立逐采样对比，不把 AAC 量化差异算作伸缩错误。

短至 4 ms 的音频即使有声且采样数正确，音高仍可能显著偏移。执行记录的 `pitch_and_listening_accepted: false` 保持明确；质量 CLI 的峰值/非静音结果不能代替音高、瞬态或听审。未配置离线引擎时，既有极短 atempo 变速缺口继续存在。

[对应实测](../validation/离线音频伸缩与真实采样实测_2026-10-17.md)记录实际通过和失败；[嵌套时间映射](./嵌套序列解析时间映射契约_v0.1_2026-10-16.md)与[视频首尾帧契约](./嵌套视频帧区间与结束时钟契约_v0.1_2026-10-17.md)分别定义时钟和视频可见性。


已有本地工具可用以下原生 PowerShell 生成配置 JSON，再写入项目 `settings.audio_stretch`。脚本只读取本地程序、依赖和许可，不下载或执行引擎；路径按本机实际位置填写。

```powershell
$AudioEnginePath = (Resolve-Path -LiteralPath 'E:/local-tools/rubberband/rubberband.exe').Path
$AudioDllPath = Join-Path (Split-Path -Parent $AudioEnginePath) 'sndfile.dll'
$AudioLicensePath = Join-Path (Split-Path -Parent $AudioEnginePath) 'COPYING.txt'
$AudioDigest = { param($AudioFile) 'sha256:' + (Get-FileHash -LiteralPath $AudioFile -Algorithm SHA256).Hash.ToLowerInvariant() }
$AudioEngineSettings = [ordered]@{
    engine = 'rubberband-r3-offline-v1'
    executable = $AudioEnginePath
    sha256 = (& $AudioDigest $AudioEnginePath)
    dependencies = @(@{ path = $AudioDllPath; sha256 = (& $AudioDigest $AudioDllPath) })
    license_path = $AudioLicensePath
    license_sha256 = (& $AudioDigest $AudioLicensePath)
    license_spdx = 'GPL-2.0-or-later'
}
$AudioEngineSettings | ConvertTo-Json -Depth 5
```
