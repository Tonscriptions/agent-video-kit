# 本地 LUT 资产库与效果引用契约

| 项目 | 内容 |
|---|---|
| 文档编号 | SPEC-LUT-001 |
| 状态 | 有效 |
| 生效日期 | 2026-10-15 |
| 运行边界 | 原生 Windows、项目本地文件、FFmpeg `lut3d` |

## 1. 目的

LUT 不再只能在片段里写一条容易失效的绝对路径。Agent 可以先把本地 LUT 登记为项目资源，再在效果参数中使用稳定的 `lut_id`。登记内容进入项目的 `assets/lut-library.json`，实际文件复制到 `assets/luts/`，权利信息写入项目 `rights-ledger.json`。

该流程不下载 LUT、不访问网络、不调用闭源服务，也不把许可证状态自动提升为可发布。发布仍由 Rights Ledger 的状态、用途和证据门禁决定。

## 2. CLI

```powershell
python -X utf8 -m ai_ad_editor lut register `
  --project .\project `
  --input .\looks\warm.cube `
  --lut-id lut_warm `
  --license-spdx CC0-1.0 `
  --verification-status verified

python -X utf8 -m ai_ad_editor lut list --project .\project
python -X utf8 -m ai_ad_editor lut inspect --project .\project --lut-id lut_warm
```

`lut register` 只接受存在的本地 `.cube`、`.3dl`、`.csp` 或 `.dat` 文件。没有显式 `--lut-id` 时使用 `lut_<sha256前16位>`；同一内容或冲突 ID 会拒绝重复登记。写入前生成项目快照，并在操作记录和 provenance 中保存 LUT ID、SHA-256 与快照 ID。

## 3. 清单字段

每个 `records[]` 元素至少包含：

| 字段 | 约束 |
|---|---|
| `id` | 项目内稳定 ID，符合 Agent ID 规则 |
| `uri` | 项目相对路径，必须位于 `assets/luts/` |
| `sha256` | `sha256:<64位十六进制>`；校验和渲染前复核 |
| `extension` | `.cube`、`.3dl`、`.csp` 或 `.dat` |
| `metadata` | `.cube` 可记录 title、3D 尺寸、域和样本数；其他格式保留扩展名信息 |
| `interpolations` | 本机 FFmpeg `lut3d` 可声明的 `nearest`、`trilinear`、`tetrahedral`、`pyramid`、`prism` |
| `source` | 原始本地文件名与 `local://` 引用 |

`.cube` 的 `sample_count_valid=false` 会保留在登记信息中，项目校验或 FFmpeg 本身负责拒绝不可执行的内容；登记器不会修改 LUT 数值。

## 4. 效果引用

效果可以使用以下两种形式：

```json
{"type":"lut3d","parameters":{"lut_id":"lut_warm","interpolation":"tetrahedral"}}
```

或继续使用项目内路径：

```json
{"type":"lut3d","parameters":{"path":"assets/luts/warm.cube","interpolation":"tetrahedral"}}
```

使用 `lut_id` 时，校验器会从清单解析路径、检查扩展名、存在性和 SHA-256；哈希不一致返回 `LUT_HASH_MISMATCH`。项目外路径、网络协议、缺失文件和未知扩展名在保存前拒绝。渲染器随后只生成本地 FFmpeg `lut3d` filter。可选 `parameters.intensity` 是 `0..1` 的有限数字，默认 `1`：`1` 使用源 LUT，`0` 精确跳过 LUT，`0< intensity <1` 仅对 `.cube` 在项目 `cache/luts/` 中按源文件 SHA-256 和强度派生 identity 混合表，再交给本地 FFmpeg `lut3d`。派生缓存可重建，不进入 Rights Ledger 资产清单；源 LUT 的登记记录仍是唯一权利依据。`.3dl/.csp/.dat` 的部分强度、强度关键帧和 HDR 色域转换仍返回明确的近似/不支持警告，不能伪装成逐帧或精确混合。

## 5. 强度与失败语义

- `LUT_INTENSITY_INVALID`：强度不是 `0..1` 有限数字，项目保存/发布校验失败。
- `LUT_INTENSITY_FORMAT_UNSUPPORTED`：非 `.cube` 试图使用部分强度；渲染报告保留 `RENDER_FEATURE_UNSUPPORTED` 并跳过该效果。
- `LUT_INTENSITY_CONTEXT_MISSING`：直接调用渲染器但没有项目根目录，无法创建项目内派生缓存。
- `RENDER_FEATURE_APPROXIMATE` / `feature=lut_intensity`：`.cube` 派生表已执行静态强度；若效果含关键帧，关键帧仍按静态参数处理并披露限制。

派生文件名由 `sha256(source_sha256 + normalized_intensity)` 确定，写入采用同目录临时文件替换；源文件内容变化会生成新缓存，不复用旧内容。

## 6. 版本边界

当前契约关闭了项目级 LUT 登记、复用、哈希追踪、权利登记和 `.cube` 静态强度混合。LUT 预览缓存、动态强度关键帧、非 `.cube` 的部分强度/深入元数据解析、HDR LUT 色域转换和跨渲染器视觉等效仍是独立缺口，不能从 `lut_id` 登记能力推断为已实现。
