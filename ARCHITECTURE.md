# 架构与模块职责

## 分层

```
入口层   tools\run_ocr_py.bat → ocr\ocr.py（命令行）
         tools\run_ocr.bat    → xnet_ocr_demo.exe（模型演示）
             │
编排层   ocr\ocr_image.py    detect() → crop_line() → recognize() → sort/输出
             │
   ┌─────────┼──────────────┬────────────────┐
后处理 det_postprocess   几何/分段 ocr_image   识别解码 xnet_ocr_lib
   └─────────┴──────────────┴────────────────┘
             │
基础设施 ocr\paths.py（路径解析）  ocr\make_input.py（raw NCHW）
         tools\xnet_infer.exe（C++ 推理器）  tools\XNet.lib（逆向导入库）
```

## 模块职责

| 模块 | 职责 | 关键函数/常量 |
|---|---|---|
| `ocr.py` | CLI 入口，解析参数，打印文本/JSON | `main()` |
| `ocr_image.py` | 主流水线编排；含检测、裁切、识别分段 | `detect()`、`crop_line()`、`recognize()`、`_plan_cuts()`、`_filter_boxes()` |
| `det_postprocess.py` | 检测图 → 文本框 | `recover_quads()`、`_label()`、`_min_area_rect()`、`scale_boxes()` |
| `xnet_ocr_lib.py` | 字符集、预处理、CTC 解码 | `load_charset()`、`preprocess_gray()`、`ctc_decode()`、`normalize_text()` |
| `paths.py` | 所有外部路径解析与诊断 | `model_dir()`、`tools_dir()`、`infer_exe()`、`weixin_dir()`、`diagnose()` |
| `make_input.py` | 生成 NCHW raw 输入 | `write_input_nchw()` |
| `xnet_infer.cpp` | C++ 推理器：读 raw → 跑模型 → 出 bin/json | `wmain()` |

## 一次识别的数据流

```
PNG/JPEG/BMP
  → PIL 转灰度 uint8
  → det_preprocess(): 等比缩放到长边 ≤ limit，两侧向上取整到 32 倍数
  → write_input_nchw(): 头部(rank + dims) + float32 payload
  → xnet_infer.exe 写 score_map.bin / kernel_map.bin / ori_map.bin + .json
  → recover_quads(): 阈值 → 连通域 → 最小外接矩形 → unclip → 分行
  → _filter_boxes(): 剔除竖高框与超大框
  → scale_boxes(): 映射回原图坐标
  → crop_line(): 透视裁切 + 墨迹收紧
  → recognize(): 按宽度分段 → 每段缩放到高 32 → 识别 → 拼接
  → ctc_decode(): softmax → argmax → 去重去 blank → 查字符集
  → normalize_text(): 去首尾空白、压缩连续空格
```

## 关键参数与调参入口

| 参数 | 默认值 | 位置 | 影响 |
|---|---|---|---|
| `limit_side` | 960 | `ocr.py --long` | 检测长边上限，影响精度与耗时 |
| `thresh` | 0.3 | `ocr_image.detect()` | 检测二值化阈值 |
| `min_area` | 40 | `ocr_image.detect()` | 连通域最小像素数 |
| `box_thresh` | 0.2 | `ocr_image.detect()` | 框内平均响应下限 |
| `unclip_ratio` | 2.0 | `ocr_image.detect()` | 框外扩倍数（81 组扫描最优区含 1.5–2.5） |
| `mean/std` | 0.5 / 0.5 | `ocr_image.det_preprocess()` | 归一化 |
| `target_h` | 32 | `recognize()` | 识别输入高度，**模型只接受 32** |
| `max_steps` | 90 | `recognize()` | 单段 CTC 步数预算，决定分段粒度 |
| `align` | 32 | `det_preprocess()` | 检测输入尺寸对齐（模型要求 32 倍数） |

参数裕度已验证：`det_param_scan.py` 81 组扫描，默认组合平均召回 1.000，
与 27 组并列最优，不在临界点。

## 并发模型

- 无多线程。Python 侧串行调用 `xnet_infer.exe` 子进程。
- 每次推理使用独立输出目录（`rec_out_<idx>`），同一进程内可安全重复调用。
- `_recognize_segments` 用 `idx * 1000 + n` 分配子目录，但**不支持两个进程
  同时写同一 `--out`**。

## 已知实现约束（模型契约，非缺陷）

| 约束 | 值 | 后果 |
|---|---|---|
| 检测输入高度 | 必须 32 的倍数 | 否则引擎返回失败码 10 |
| 识别输入高度 | 只能是 32 | 48 及以上引擎内部崩溃 |
| 识别步长 | 约 4 像素/步，约 1/4 汉字/步 | 宽行必须分段 |
| `Run` 阻塞参数 | 必须为 0 | 传 1 引擎内部崩溃 |
| `kernel_map` | 全为 0 | 该模型未启用渐进核收缩 |
| CTC blank | 索引 0 | 字符 i 对应类 i+1 |

详见 [MODELS.md](MODELS.md)。
