# 预设来源与再分发 / Look provenance and redistribution

| 资源 / Source | 锁定提交 / Pinned commit | 数量 / Count | 许可 / License |
|---|---|---:|---|
| [João Almeida / t3mujinpack](https://github.com/t3mujinpack/t3mujinpack) | `0b421f3e25209ed78253d1724a29cc6255c5e7fe` | 51 Hald → CUBE | MIT, notice retained |
| [Nixua / Striped Purple](https://github.com/stripedpurple/color-grading-luts) | `9757e8b5147693cab49c3fd674bf23dbe28d6c8e` | 49 CUBE | MIT, notice retained |

原始文件通过 Git SSH 获取，逐文件校验 Git blob 与 SHA-256；只读取数据，未运行上游程序。上游完整许可证原文位于随包 `ai_ad_editor/look_data/licenses/`，每条目录记录绑定原文哈希、仓库、提交、路径、原始哈希和派生 LUT 哈希。应用时将相关许可与转换记录复制到项目，不依赖联网读取许可。MIT 要求再分发保留版权和许可文本。

Original blobs were acquired through native Git SSH and checked against pinned Git blob IDs and SHA-256. Upstream code was not executed. Full unmodified MIT notices ship in `ai_ad_editor/look_data/licenses/`. Each entry binds its source commit/path/hash, conversion and notice hash. Project application copies notices locally; retain them when redistributing.

名称沿用上游，品牌商标不构成背书或官方滤镜声明。相机/胶片观感是社区模拟，未经厂商认证。随包合成预览测试卡和本轮演示素材为本项目原创合成数据，按 CC0-1.0 提供；字体由本机已有字体渲染成图像，不捆绑字体文件。

Names identify upstream community looks and do not establish endorsement or an official manufacturer filter. The generated reference chart and synthetic demonstration media are CC0-1.0; no font files are bundled. Dependencies retain their existing notices in `bundle/licenses/` and the first release's [third-party inventory](../v0.1.0-alpha.1/THIRD_PARTY.md).
