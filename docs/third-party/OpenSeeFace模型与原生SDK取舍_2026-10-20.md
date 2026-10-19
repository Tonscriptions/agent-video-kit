# OpenSeeFace 模型与原生 SDK 取舍

本轮只采用本地 ONNX 推理和几何修饰，不接入在线 provider。固定源码、原始文件与模型摘要见
[来源清单](../validation/evidence/local-face-beauty-20261020-v69/upstream-provenance.json)。
执行契约见[离线人脸锚点与局部修饰](../specs/离线人脸锚点与局部修饰契约_v0.1_2026-10-20.md)。

## 采用范围

[OpenSeeFace](https://github.com/emilianavt/OpenSeeFace) 固定提交
`50c09741897010faad721a218b2bbe14ecad6251`。作者 [README 的 License 段](https://github.com/emilianavt/OpenSeeFace#license)
说明代码和模型采用 BSD-2-Clause；项目保留[原版权与许可](../../product/src/ai_ad_editor/OPENSEEFACE_LICENSE.txt)
及[修改说明](../../product/src/ai_ad_editor/OPENSEEFACE_NOTICE.txt)。训练数据来源另行维护，
不能由作者对权重的许可声明推导全部训练数据可再次分发或人物肖像可用于广告。

| 文件 | 字节 | SHA-256，不含前缀 |
|---|---:|---|
| mnv3_detection_opt.onnx | 568302 | 0e8e4806766d85ab067a52c7af0dcb59eb7f9dfe580b44f20a8e6ab712d89809 |
| lm_model3_opt.onnx | 13500226 | 5aa0ab2594acaf2e1d3916a8de592cffeb1f1a7a7f778cad2f37948bff6549d1 |

只取检测/地标预处理、裁剪、热力图与偏移解码约定；与固定作者纯函数的真实模型输出逐值比较。
不执行上游 webcam、UDP、GUI、RetinaFace、视线和个体识别入口。66 点有近似三维轮廓的用途，
不能当作精确二维皮肤分割、478 点网格或身份。原始热力图分数可能大于 1，保留原值，不伪称概率。

两个优化模型含 ORT 内置 `com.microsoft::FusedConv`；产品仅允许该固定内置算子，
拒绝其它自定义节点、本地函数与外部张量，不加载外部内核库。
[ORT 官方 contrib 算子说明](https://github.com/microsoft/onnxruntime/wiki/Contrib-Ops)
与[CPU 注册源码](https://github.com/microsoft/onnxruntime/blob/main/onnxruntime/contrib_ops/cpu/cpu_contrib_kernels.cc)
可复核内置来源。CPUExecutionProvider 显式选择；登记现有原生 Python 和已有 NumPy/OpenCV/ONNX/ORT。
开发、安装和运行均不自动安装这些依赖或下载权重。权重保存在 E 盘忽略目录，不随产品 wheel 分发。

## 未采用 MediaPipe SDK

检查过官方 Windows MediaPipe 1.1.1 wheel，22764009 字节，SHA-256
`a4b27829e808cd659e7cf481cbbbfc31917092a1ebcb7eafed2395dbabcd2499`。
静态 DLL 字符串含 Clearcut 客户端及 `https://play.googleapis.com/log`。
**没有执行这个 SDK**；字符串存在并不证明实际发送过请求，也不能用 Python socket 钩子证明原生 DLL 无出网。
本产品选择不接入它。[官方 Face Landmarker 文档](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker)
列出的 478 点和 blendshape 能力因此不在本轮实现范围。

许可层面，[官方维护者说明](https://github.com/google-ai-edge/mediapipe/issues/6355#issuecomment-5997480830)
与[隐私/遥测讨论](https://github.com/google-ai-edge/mediapipe/issues/6291)分别保存事实边界；
本次取舍不等于宣布其代码或模型不可商用。没有引入 MediaPipe、Google 在线服务或其它云模型替代。

## 示例素材

来自现有 scikit-image 安装的 NASA Eileen Collins 512×512 人像，
[数据文档](https://scikit-image.org/docs/0.25.x/api/skimage.data.html#skimage.data.astronaut)、
[原档案引用](https://flic.kr/p/r9qvLn)和[NASA 人物页](https://www.nasa.gov/former-astronaut-eileen-collins/)
分别提供来源。公开样例是技术几何/滤波演示，不将人物用于产品背书或投放广告。
演示原图、生成平移、空脸段、Alpha 和本地生成的双音 PCM 均有哈希；原图不是自然动态视频。
项目内源与模型权利默认未核验/仅内部用途，生成派生资产不会自动获得发布许可。
