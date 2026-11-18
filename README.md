# E:\ocr — 微信 XNet OCR

更新时间：2026-11-18

## 文档索引

| 文档 | 内容 |
|---|---|
| **README.md**（本文） | 快速使用、输出格式、验收结果、接口事实、限制 |
| [BUILD_EXE.md](BUILD_EXE.md) | 独立 exe 版：构建、依赖闭包、合规 |
| [PORTABILITY.md](PORTABILITY.md) | 换机部署、环境变量、外部依赖、版本绑定 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 分层架构、模块职责、数据流、调参入口 |
| [MODELS.md](MODELS.md) | 模型清单与校验、模型契约、许可 |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | 诊断流程、退出码表、识别质量问题 |
| [LICENSE](LICENSE) | 代码授权（PolyForm Noncommercial 1.0.0） |

## 结论

**两种形态，换电脑均可直接运行：**

| 形态 | 目标机要求 | 用法 |
|---|---|---|
| **独立 exe 版**（推荐） | **无要求**（不需 Python、不需微信） | 复制 `build\ocr\`，运行 `run_ocr_exe.bat <图片>` |
| 源码版 | Python 3.10+ 与 numpy/Pillow | `E:\ocr\tools\run_ocr_py.bat <图片>` |

识别链路：检测 → 裁切 → 识别 → CTC 解码。

实测：源码场景 10/10、边界 7/7、扩展 10/10；打包版场景 10/10、边界/格式 14/14；
三配置（源码 / 打包 / 复制+最小 PATH）3/3 全通过。独立 exe 在 PATH 只剩
3 个 Windows 系统目录、无任何 Python 与微信路径时仍 10/10。

> **合规提示**：`runtime\XNet.dll` 与 `models\` 均为腾讯版权组件，仅可用于
> 自有设备做本地识别；对外分发前请确认符合腾讯相关条款。
> 详见 [MODELS.md](MODELS.md) 与 [BUILD_EXE.md](BUILD_EXE.md)。

---

## 1. 快速使用

### 源码版

```powershell
E:\ocr\tools\run_ocr_py.bat E:\ocr\ocr\test_images\plain.png
```

等价的手动调用：

```powershell
cd E:\ocr\ocr
python ocr.py <图片路径>            # 每行文字一行输出
python ocr.py <图片路径> --json     # 只输出 JSON 到 stdout
python ocr.py <图片路径> --long 960 # 检测长边上限，默认 960
```

### 独立 exe 版

复制 `E:\ocr\build\ocr\` 整个目录到任意 Windows x64 电脑，然后：

```powershell
<目标目录>\run_ocr_exe.bat "C:\path\to\image.png"        # 默认长边 960
<目标目录>\run_ocr_exe.bat "C:\path\to\image.png" 1280   # 指定长边上限
<目标目录>\ocr.exe "C:\path\to\image.png" --out "D:\result"
```

**目标机不需要安装 Python、numpy、Pillow，也不需要安装微信。**
支持 PNG、JPEG、BMP、TIFF（Pillow 能解码即可）。

### 输出格式

stdout 每行文字占一行（自上而下）。结构化结果写入 `--out\result.json`，
源码版与打包版**字段名一致**：

```json
{
  "image": "E:\\ocr\\ocr\\test_images\\plain.png",
  "lines": [
    {"text": "微信扫码支付成功", "conf": 0.0002,
     "box": [425.4, 107.6, 14.0, 107.6, 14.0, 49.0, 425.4, 49.0]}
  ]
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `image` | string | 输入图片路径（打包版为绝对路径） |
| `lines` | array | 每行文字一个元素，按从上到下排序 |
| `lines[].text` | string | 识别出的文字 |
| `lines[].conf` | number | 该行 CTC 平均置信度（0–1，数值偏小属正常，见限制 6） |
| `lines[].box` | number[8] | 四顶点 `[x1,y1,x2,y2,x3,y3,x4,y4]`，原图像素 |

退出码：`0` 成功；`2` 输入问题（文件不存在、格式不支持、图片过小）；
推理器退出码含义见 [TROUBLESHOOTING.md](TROUBLESHOOTING.md)。

---

## 2. 验收结果

### 场景 10/10（源码 `acceptance.py`）

| 用例 | 内容 | 结果 |
|---|---|---|
| plain | 三行中英文与数字 | PASS |
| mixed_fonts | 黑体/雅黑/楷体混排 | PASS |
| small_text | 20px 小字号 | PASS |
| dense_lines | 四行密集 | PASS |
| noisy_bg | 噪点背景 | PASS |
| low_contrast | 低对比度 | PASS |
| blur | 高斯模糊 | PASS |
| no_text | 无文字图形 | PASS（正确返回空） |
| single_char | 单个汉字 | PASS |
| long_line | 39 字长行 | PASS（完整识别） |

`--long 640 / 960 / 1280` 均全量通过。

### 扩展 10/10（`test_extended.py`）

PNG / JPEG / BMP / TIFF / RGBA / 灰度 / 调色板全部 PASS；4000×2600 大图 6 行
PASS（3.5 秒）；无文字图片无误检；同一输出目录重复运行 2 次 PASS。

### 边界 7/7（`test_edge.py`）

1x1 像素（明确拒绝）、超宽细条、纯黑、纯白、高窄、极小文字、文件不存在。

### 打包版

场景 10/10（最小 PATH）、边界/格式 14/14、`test_det_post.py` matched 3/3
（IoU 0.53–0.71）。

### 检测参数裕度

81 组扫描（`det_param_scan.py`，thresh × min_area × box_thresh × unclip）：
默认 `(0.3, 40, 0.2, 2.0)` 平均召回 1.000，与 27 组并列最优区，**不在临界点**。

### 误检实测

| 输入 | 过滤前 | 形状过滤后 |
|---|---|---|
| 随机噪点 | 5 条单字 | 3 条单字 |
| 随机圆形纹理 | 5 条单字 | 4 条单字 |
| 几何图形 / 无文字 | 0 | 0 |

过滤规则：剔除高宽比 > 1.2 的竖高框、面积超过全图 60% 的超大框。

### 性能基线（`bench_speed.py -n 3`，`--long 960`）

| 用例 | 解码 | 检测 | 裁切 | 识别 | 端到端 | 吞吐 |
|---|---|---|---|---|---|---|
| plain（3 行） | 0.008 | 0.533 | 0.153 | 0.197 | **0.883** | 40.8 字/秒 |
| dense_lines（4 行） | 0.001 | 0.515 | 0.139 | 0.257 | **0.911** | 54.9 字/秒 |
| small_text（3 行） | 0.001 | 0.227 | 0.054 | 0.182 | **0.462** | 69.2 字/秒 |
| long_line（39 字） | 0.001 | 0.263 | 0.110 | 0.523 | **0.896** | 43.5 字/秒 |
| single_char | 0.000 | 0.135 | 0.035 | 0.048 | **0.218** | 4.6 字/秒 |

**瓶颈在检测**（约 60%）。打包版冷启动 0.99 秒，与后续运行一致（`--onedir`
不解包到临时目录）。

---

## 3. 逆向得到的关键接口事实

以下均为实测确定，非推测。

### XNet C API

`XNet.dll` 导出 24 个未修饰 C 函数（另有 3784 个 MSVC 修饰的 C++ 符号）。
完整用法——生命周期、逐函数说明、DLL 加载约束、输出张量布局陷阱、可直接
编译的 C 示例——见 [MODELS.md](MODELS.md) 的「XNet.dll 使用手册」。

其中最易踩的三点：

- `CreateFromFile` 的 `options` 必须传 `nullptr`
- `Run` 必须传非阻塞 `0`（传 1 在引擎内部崩溃）
- DLL 是**导入表**依赖，必须在 exe 同目录或 `PATH` 中，否则 `0xC0000135`

### 模型契约

| 项 | 检测模型 | 识别模型 |
|---|---|---|
| 输入 | `1×3×H×W`，fp32，H 必须是 32 的倍数 | `1×3×H×W`，fp32，H 实测可取 **18–32**（推荐 32） |
| 输出 | `score_map [1,H',W']`、`kernel_map [1,16,h',w']`、`ori_map [1,4]` | `[1,T,13564]` logits，**T = W/4，与 H 无关** |
| 归一化 | `(x/255 - 0.5)/0.5` | 同左 |

识别模型实测包线（29 字中文行，单段不分割）：

| 输入高度 H | 16 | 18–24 | 28–32 | ≥34 |
|---|---|---|---|---|
| 结果 | rc=10 | 可运行但漏字 | **准确** | rc=10 |

| 单段宽度 W | ≤1600（T≤400） | 1700–1800（T=425–450） | ≥2000（T≥500） |
|---|---|---|---|
| 结果 | **29 字全对** | 开始退化 | 明显崩坏 |

主流程取 `target_h=32`、`max_steps=90`（即 `max_w=720`、`T=180`），处于实测
包线内较保守的位置，留有余量。

- **data kind 枚举**（`GetStorageDataKindName` 实测）：
  `2=u8 3=u16 4=u32 5=u64 6=s8 7=s16 8=s32 9=s64 10=fp16 11=fp32 12=fp64`
- **CTC blank 在索引 0**，字符 i 对应类 i+1（13564 = 13563 字符 + 1 blank）
- **`Run` 必须传非阻塞 0**：传 1 会在引擎内部崩溃
- **`GetOutput` 返回 tensor 指针本身**，未就绪返回 NULL
- **kernel_map 全为 0**：该模型未启用渐进核收缩，后处理直接用阈值图

### 长文本分段

实测：**1 个 CTC 步约覆盖 1/4 个汉字**（每字约 4 步、约 16px 宽）。单段可靠长度
实测达 **29 字（T=400）**；主流程把单段限制在 `T≤180`（约 720px）留裕度。
宽行因此按**字符间隙**切分后逐段识别再拼接，避免切断字符。

### 字符集边界

`charset_zh13562.txt` 共 13563 字符，**不含**全角冒号「：」、全角括号「（）」、
全角分号「；」。这些标点会被识别为半角或跳过，属模型固有限制。

---

## 4. 已知限制

1. **依赖私有运行时**：与微信 4.1.13.48 的 `XNet.dll` 绑定，升级后可能失效。
2. **需要 PATH 指向 DLL**：exe 导入表按裸名 `XNet.dll` 绑定，DLL 必须在同目录或 PATH。
3. **识别高度推荐 32**：实测 18–32 可运行，28–32 准确；<18 或 >32 引擎返回失败码 10。
4. **长行依赖分段**：单段实测可靠长度达 29 字（T≤400），主流程限制在 T≤180
   留裕度。若字符粘连无间隙，切分可能不准。
5. **竖排文字未支持**：检测模型的 `ori_map` 指示方向，本实现按水平行处理。
6. **置信度不可用作阈值**：模型 logits 尺度小，softmax 后仍接近均匀（均值约
   0.0002），argmax 正确但绝对概率无区分度。
7. **随机纹理可能误检**：纯噪点、随机圆形纹理会产出少量单字误检（实测 3–4 个）。
   形状过滤已降低误检但无法根除——检测模型本身会响应。几何图形、纯色、渐变不误检。
8. **超大图字号会缩小**：4000×2600 缩放到 960 长边后，部分拉丁字母识别退化
   （`LargeImage` → `Largelmage`），中文主体不受影响。用 `--long 1280` 可缓解。

---

## 5. 复现构建

```powershell
# C++ 推理层（MSVC）
E:\ocr\tools\build_cpp.bat x64          # 编译 xnet_infer.exe / xnet_ocr_demo.exe

# 导入库
cmd /c "call `"$vc`" && lib /def:E:\ocr\tools\XNet.def /machine:x64 /out:E:\ocr\tools\XNet.lib"

# 独立 exe 版
python E:\ocr\build\build_exe.py --slim
```

Python 侧依赖：`numpy`、`Pillow`。验收与静态检查命令见
[TROUBLESHOOTING.md](TROUBLESHOOTING.md) 末节。
