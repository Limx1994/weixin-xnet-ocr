# 排障指南

先跑诊断，多数问题能直接定位：

```powershell
python E:\ocr\ocr\paths.py
```

期望全部 `OK`。任何 `MISS` 都会指出缺哪个依赖。

## 快速自查表

| 现象 | 原因 | 处置 |
|---|---|---|
| `FileNotFoundError: 系统找不到指定的文件` | 推理器路径不对，或模型不在推导位置 | 设 `XNET_TOOLS_DIR` / `XNET_MODEL_DIR`，或跑 `paths.py` |
| `detection model not found` | 模型目录未随项目复制 | 复制 `models\WeChatOcr-8096\`，或设 `XNET_MODEL_DIR` |
| `inference driver not found` | `xnet_infer.exe` 缺失 | 复制 `tools\`，或设 `XNET_TOOLS_DIR` |
| `XNet.dll not found` | 微信未安装或版本路径未探测到 | 设 `XNET_WEIXIN_DIR` 指向含 `XNet.dll` 的目录 |
| `ModuleNotFoundError: numpy / PIL` | Python 依赖未装 | `pip install numpy Pillow` |
| `'python' 不是内部或外部命令` | 未装 Python 或未入 PATH | 装 Python 3.10+ 并勾选加入 PATH |
| 退出码 2 + `error: image not found` | 路径拼写或含空格未加引号 | 用引号包裹路径 |
| 退出码 2 + `image too small` | 图片任一维 < 4 像素 | 属正常拒绝，非缺陷 |
| `0xC0000135` 启动失败 | exe 以 `/MD` 编译，缺 VC++ 运行库 | 用 `/MT` 重新编译（见 BUILD_EXE.md） |
| 无输出但退出码 0 | 图中无文字 | 正常；日志会打印 `no text detected` |

## 识别质量问题

| 现象 | 原因 | 处置 |
|---|---|---|
| 整行文字缺失 | 检测未响应 | 换 `--long 640` 或 `1280`；调整图片对比度 |
| 长行尾部被截断 | 单段过宽导致步数不足 | `recognize()` 已自动分段；实测单段可靠长度达 29 字（T≤400），主流程限 T≤180 |
| 字符粘连导致切分错误 | 笔画相连，列投影无空白列 | `_plan_cuts()` 退化为按像素硬切；提高图片分辨率 |
| 单字识别错误 | 目标过小 | 已自动加白边；仍错则换更大字号图片 |
| 全角标点变成半角或消失 | 字符集不含该标点 | 模型固有限制，无法修复 |
| 结果带前导/尾随空格 | CTC 边缘空白 | 已用 `normalize_text()` 去除 |
| 置信度数值极小（约 0.0002） | 模型 logits 尺度小 | **正常现象**，不可用作阈值 |
| 随机纹理图出现少量单字 | 检测模型在随机纹理上误响应 | 形状过滤已降低误检，无法根除 |
| 竖排文字识别失败 | 未实现方向校正 | 当前仅支持水平行 |
| 超大图拉丁字母退化 | 缩放到 960 后字号过小 | 用 `--long 1280` 或切图处理 |

## 推理器退出码

| 码 | 含义 | 处置 |
|---|---|---|
| 2 | 参数不足 | 检查调用参数 |
| 3 | `XNet.dll` 加载失败 | 确认 DLL 在 PATH 或 exe 同目录，或设 `XNET_WEIXIN_DIR` |
| 4 | 输入文件头错误 | 重新生成 raw 输入 |
| 5 | 模型加载失败 | 模型损坏或版本不匹配；校验 MD5（见 `MODELS.md`） |
| 6/7 | 会话创建/输入初始化失败 | 输入 shape 不合法 |
| 8 | 输入张量创建失败 | shape 超界或 data kind 越界 |
| 9 | `SetInput` 失败 | 输入尺寸与模型不匹配 |
| 10 | `Run` 失败 | 检测高度非 32 倍数，或识别高度不在 18–32 |
| 11 | manifest 写入失败 | `--out` 目录不可写 |

### Python 侧异常

| 异常 | 含义 |
|---|---|
| `FileNotFoundError: <name> not found: <path>` | `paths.require()` 抛出，提示需设置的环境变量 |
| `RuntimeError: detector failed 0x...` | 推理器非零退出，消息内含退出码 |
| `UnicodeDecodeError` | 读 JSON 未指定 UTF-8（本项目已统一处理） |

## 分段逻辑说明

宽文本行会被切成多段分别识别：

- 切点优先选**字符间隙**（列投影为 0 的空白列），保证不切断字符；
- 无间隙时（下划线、粘连）退化为按像素硬切，已实测可用；
- 段数按 `预算 = 步数上限 × 4 × 0.18` 均分，默认约 130 像素/段；
- 单段宽度上限 `max_w = 32 × 90 / 4 = 720px`（T≤180），实测 29 字可靠；
- 实测 39 字长行可完整识别。

## 诊断命令

```powershell
python E:\ocr\ocr\paths.py                      # 依赖与路径
python E:\ocr\ocr\ocr.py "图片.png" --out E:\ocr\ocr\_dbg   # 单张图详细过程
python E:\ocr\ocr\det_param_scan.py             # 检测参数裕度
python E:\ocr\ocr\bench_speed.py -n 3            # 速度基线
python E:\ocr\ocr\acceptance.py                 # 全量回归
python E:\ocr\ocr\test_edge.py
python E:\ocr\ocr\test_extended.py
python E:\ocr\build\check_undefined.py          # AST 静态检查（期望 0 file(s) with issues）
python E:\ocr\build\dep_closure.py E:\ocr\build\ocr   # 依赖闭包（期望 0 外部依赖）
```

中间产物（raw 输入、模型输出 bin/json、result.json）都在 `--out` 目录下，
便于定位是检测、识别还是解码环节出错。

## 仍然失败时

请提供：

1. `python paths.py` 的完整输出
2. 失败命令原文与完整 stderr
3. 图片尺寸与内容描述（是否含文字、字体、颜色）
4. 微信版本号（`4.1.13.48` 之外的版本未验证）
