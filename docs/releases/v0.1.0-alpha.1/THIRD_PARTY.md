# 许可与第三方通知 / Licensing and third-party notices

Original Agent Video Kit code and documentation: [MIT](../../../LICENSE). This grant does not relicense separately identified upstream code, repositories, Skills, models, fonts or media.
自有代码与文档使用 MIT；各第三方内容保留独立许可证，不以根目录许可覆盖第三方条款。

| Component | Preserved evidence / notices | Distribution boundary |
|---|---|---|
| Python dependencies | Offline `bundle/manifest.json`, `requirements.lock`, `licenses/`; original notices in wheels | Eight pinned wheels; no runtime fetch |
| OpenFilm | [MIT](../../../product/src/ai_ad_editor/OPENFILM_LICENSE.txt), [examples notices](../../../product/src/ai_ad_editor/OPENFILM_EXAMPLES_LICENSE.txt) | Identified adapted/preserved modules, not its hosted service |
| pdoom-video adaptation | [Original notice](../../../product/src/ai_ad_editor/PDOOM_VIDEO_LICENSE.txt) | Identified local modules |
| Native HSL kernel | [MIT](../../../product/src/ai_ad_editor/NATIVE_HSL_LICENSE.txt), [source](../../../product/src/ai_ad_editor/native_hsl.c) | Packaged Windows DLL and corresponding source |
| RFC3339 checker adaptation | [BSD notice](../../../product/src/ai_ad_editor/RFC3339_VALIDATOR_LICENSE.txt) | Local schema validation |
| OpenSeeFace / Paddle interfaces | [OpenSeeFace](../../../product/src/ai_ad_editor/OPENSEEFACE_LICENSE.txt), [Paddle](../../../product/src/ai_ad_editor/PADDLE_OCR_LICENSE.txt) and adjacent NOTICE files | Adapter attribution; model weights are not bundled |
| External Skills | [Origin/commit/hash mapping](../../../video-cut-install-manifest.json), per-Skill LICENSE/resources | Modified entries identified as local copies |
| New release examples | [CC0 declaration](../../assets/release-v0.1.0-alpha.1-r2/LICENSE.txt), generator, individual SHA-256 inventory | Fictional generated artwork/audio; no font binary or model weights |
| Older examples / research | Their own LICENSE, Rights Ledger and dated evidence | Historical; not all research assets are included in the release examples ZIP |
| FFmpeg and optional native tools | Existing local installation/build versions recorded by doctor and case checks | Not redistributed in the base release; required features depend on your build |

模型、参考声音、商用字体或外部媒体的权利不由接口存在自动获得；需要使用者提供对应本地证据。
An adapter's existence does not grant rights to model weights, reference voices, commercial fonts or external media. Supply appropriate evidence for your own assets.
