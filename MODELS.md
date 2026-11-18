# 模型资产与契约

## 来源

`C:\Program Files (x86)\Tencent\Weixin\4.1.13.48\WeChatOcr.bin` 实为 ZIP 包
（文件头 `PK`），版本标记 8096，解压后 49.49 MB。

## 资产清单

源目录 `E:\ocr\models\WeChatOcr-8096\` 保留全部 **14 个文件**（50 MB）；
打包产物 `build\ocr\models\WeChatOcr-8096\` 只保留 **3 个必需文件**（9.5 MB）。
两者用途不同，核对时注意区分。

| 文件 | 大小(MB) | 用途 | 本项目的用法 |
|---|---|---|---|
| `text_det_fp16_v2.xnet` | 1.381 | 文本检测 | 检测模型 |
| `text_rec_zh13562_fp16_v2.xnet` | 7.967 | 中文文本识别 | 识别模型 |
| `charset_zh13562.txt` | 0.053 | 字符集（13563 字符） | CTC 解码字典 |
| `paragraph_det_fp16_v2.xnet` | 2.802 | 段落检测 | 未使用 |
| `wxocr.dll` | 23.353 | OCR 服务插件 | 未直接使用（其内嵌引擎与 XNet.dll 相同） |
| `x64.config` | 0.000 | 架构标记（内容 `x64`） | 未使用 |
| `file_component.xml` | 0.001 | 完整性清单（MD5 + 长度） | 校验依据 |
| `DeepSR_REPSR_R_M4C16_Flip_ep24.xnet` | 0.043 | 超分辨率 | 未使用 |
| `FPMMFG1V1.2.0.26.xnet` | 1.530 | 人脸/隐私 | 未使用 |
| `FPMMFG2V1.3.1.26.xnet` | 6.630 | 人脸/隐私 | 未使用 |
| `PrivacyDetectV8.0.26.xnet` | 5.104 | 隐私检测 | 未使用 |
| `QBarDetV1.7.0.26.xnet` | 0.395 | 二维码检测 | 未使用 |
| `QBarSegV1.1.0.26.xnet` | 0.214 | 二维码分割 | 未使用 |
| `sohu_simp.txt` | 0.019 | 搜狗词库 | 未使用 |

### 打包产物只保留 3 个文件

`build\ocr\models\WeChatOcr-8096\` 仅含：

| 文件 | 原因 |
|---|---|
| `text_det_fp16_v2.xnet` | 检测模型 |
| `text_rec_zh13562_fp16_v2.xnet` | 识别模型 |
| `charset_zh13562.txt` | CTC 解码字典 |

其余 11 个（共 40.1 MB）由 `build\build_exe.py --slim` 剔除：它们对应超分、
人脸/隐私、二维码、OCR 服务插件，本项目从未引用，剔除不影响识别。
未加 `--slim` 时产物为 14 个文件（119.9 MB）。

**注意**：`file_component.xml` 一并剔除，因此打包目录**不能**用下面的完整性
校验脚本核对；该脚本只适用于源目录 `E:\ocr\models\WeChatOcr-8096\`。

## 完整性校验

复制后做过双重校验，全部一致（针对源目录的 14 个文件）：

1. 逐文件 SHA-256：源与目标 14/14 相同
2. 按 `file_component.xml` 内的 MD5 与长度：14/14 相同

`file_component.xml` 关键条目：

| 文件 | MD5 | 长度 |
|---|---|---|
| `charset_zh13562.txt` | `b55e7a03bb0dfcfd8607cf361bc89e5e` | 54258 |
| `text_det_fp16_v2.xnet` | `5508d2a18eedce532093ca81a5026a8c` | 1447764 |
| `text_rec_zh13562_fp16_v2.xnet` | `1bec5f5f7afff0df13c6e4fa7e0f7942` | 8354384 |
| `wxocr.dll` | `532eafe00345beea45179d6192097354` | 24486952 |

可用以下命令重新校验：

```powershell
[xml]$x = Get-Content E:\ocr\models\WeChatOcr-8096\file_component.xml -Raw -Encoding UTF8
foreach ($f in $x.file_component.file) {
  $p = Join-Path 'E:\ocr\models\WeChatOcr-8096' $f.'#text'
  $md5 = (Get-FileHash -LiteralPath $p -Algorithm MD5).Hash.ToLower()
  "{0,-34} {1}" -f $f.'#text', $(if ($md5 -eq $f.md5.ToLower()) {'OK'} else {'MISMATCH'})
}
```

## 模型格式

XNet 是腾讯私有推理格式，文件头 4 字节 magic 为 ASCII `XNET`，
随后是算子图描述（可见 `Conv_0_(+)_Relu_1` 等算子名）。

**不是** ONNX / PyTorch / Paddle / TensorRT，无法用通用运行时加载。

### 检测模型契约

| 项 | 值 |
|---|---|
| 输入 | `1×3×H×W`，float32，NCHW；H 与 W 均须为 32 的倍数 |
| 归一化 | `(pixel/255 − 0.5) / 0.5` |
| 输出 | `score_map [1,H',W']`、`kernel_map [1,16,h',w']`、`ori_map [1,4]` |
| 实测 1×3×64×256 | `score_map [1,64,256]` fp32、`kernel_map [1,16,64]`、`ori_map [1,4]` |
| 实测响应 | 文字区均值 0.71 / 背景 0.06（对比度约 11.8 倍） |

### 识别模型契约

| 项 | 值 |
|---|---|
| 输入 | `1×3×32×W`，float32，NCHW；**高度只能为 32** |
| 归一化 | 同上 |
| 输出 | `[1,T,13564]` float32 logits |
| 步长 | `T = W / 4`（每 4 像素 1 步） |
| 解码 | CTC；blank 在类 0，字符 i 在类 i+1 |
| 实测 1×3×32×100 | `[1,25,13564]` |

### 字符集

- 13563 个字符，**每行一个字符**（不是连续字符串）。
- 解析必须按 `\n` 切分；按解码后字符迭代会因 CJK 多字节而数量错误。
- 输出类别数 13564 = 13563 字符 + 1 个 CTC blank，完全吻合。
- **不含**：全角冒号「：」、全角括号「（）」、全角分号「；」。
  这些标点会被识别为半角或跳过。

### data kind 枚举

通过调用 `XNet::GetStorageDataKindName` 实测：

| 值 | 含义 | 值 | 含义 |
|---|---|---|---|
| 0 | `*`（内部通配） | 7 | s16 |
| 1 | `fp*`（内部通配） | 8 | s32 |
| 2 | u8 | 9 | s64 |
| 3 | u16 | 10 | fp16 |
| 4 | u32 | 11 | **fp32（本项目使用）** |
| 5 | u64 | 12 | fp64 |
| 6 | s8 | | |

越界取值会触发 XNet 内部 `__fastfail`（SEH 无法拦截）。

## 许可与合规

- 模型文件、`XNet.dll`、`wxocr.dll` 均为**腾讯版权组件**，随微信安装分发。
  本项目仅在本机做本地识别研究，未重新分发这些二进制。
- 推理接口 `XNetDnn*Cpu*` 系通过静态分析逆向得到，**无官方授权与文档**，
  与微信 4.1.13.48 版本绑定，升级后不保证可用。
- 本项目代码部分可自由使用（见 [LICENSE](LICENSE)）；**模型与 DLL 部分请遵守
  腾讯相关条款**。
