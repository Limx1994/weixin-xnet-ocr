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
| 输入 | `1×3×H×W`，float32，NCHW；H 实测可取 **18–32**（推荐 32） |
| 归一化 | 同上 |
| 输出 | `[1,T,13564]` float32 logits，**T = W/4，与 H 无关** |
| 步长 | 每 4 像素 1 步（约 1/4 汉字/步） |
| 解码 | CTC；blank 在类 0，字符 i 在类 i+1 |
| 实测 1×3×32×100 | `[1,25,13564]` |

识别模型实测包线（29 字中文行，单段不分割）：

| 输入高度 H | 16 | 18–24 | 28–32 | ≥34 |
|---|---|---|---|---|
| 结果 | rc=10 | 可运行但漏字 | **准确** | rc=10 |

| 单段宽度 W | ≤1600（T≤400） | 1700–1800（T=425–450） | ≥2000（T≥500） |
|---|---|---|---|
| 结果 | **29 字全对** | 开始退化 | 明显崩坏 |

主流程取 H=32、T≤180，处于包线内较保守处。

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

---

## XNet.dll 使用手册

### 它是什么

`XNet.dll` 是腾讯私有的推理运行时，随微信 Windows 版分发。模型文件为 `.xnet`
格式（文件头 4 字节 ASCII `XNET`），**不是** ONNX / PyTorch / Paddle /
TensorRT，通用运行时无法加载。

导出表包含 24 个未修饰 C 推理函数（另有 3784 个 MSVC 修饰的 C++ 符号，
本项目的 OCR 链路只用到前者）。全部为 `__cdecl`，返回不透明句柄。

声明见 `tools\xnet_capi.h`，导入库 `tools\XNet.lib` 由 `tools\XNet.def` 生成：

```powershell
lib /def:E:\ocr\tools\XNet.def /machine:x64 /out:E:\ocr\tools\XNet.lib
```

### 加载 DLL：导入表约束

`xnet_infer.exe` / `xnet_ocr_demo.exe` 通过导入表按**裸名** `XNet.dll` 链接，
Windows 在**代码执行前**就解析该依赖。因此 DLL 必须在：

- 与 exe 同目录，**或**
- 在 `PATH` 中

代码里再写 `LoadLibrary` 也无法绕过这一点（实测：DLL 不在 PATH 时进程直接以
`0xC0000135` 启动失败，一句代码都执行不到）。

定位顺序（`ocr\paths.py`、`xnet_infer.cpp`、`xnet_ocr_demo.cpp` 三处一致）：

1. 环境变量 `XNET_WEIXIN_DIR`
2. exe 同目录副本
3. `C:\Program Files (x86)\Tencent\Weixin\<版本号最新的子目录>`
4. `C:\Program Files\Tencent\Weixin\<同上>`
5. `%LOCALAPPDATA%\Tencent\Weixin\<同上>`
6. 上述根目录本身

### 调用生命周期

```
CreateFromFile → GetNumInputs/Outputs → SessionCreate
  → InitializeInputs → TensorCreate → Lock/写入 → UnLock
  → SetInput → Run(0) → GetOutput → Lock/读取 → UnLock
  → TensorDestroy → SessionDestroy → ModelDestroy
```

### 函数逐条说明（标「实测」的均已验证）

#### 模型

| 函数 | 说明 |
|---|---|
| `XNetDnnModelCpuCreateFromFile(path, options)` | **实测** `options` 必须传 `nullptr`，传其他值行为未验证 |
| `XNetDnnModelCpuCreateFromStream(stream, size, options)` | 从内存加载；本项目未使用 |
| `XNetDnnModelCpuDestroy(model)` | 释放模型 |
| `XNetDnnModelCpuGetNumInputs / GetNumOutputs` | 输入/输出个数 |
| `XNetDnnModelCpuGetInputName / GetOutputName` | **实测** 名字需传给 `SetInput` / `GetOutput`；检测模型输入名为 `input`，输出为 `score_map`、`kernel_map`、`ori_map` |

#### 会话

| 函数 | 说明 |
|---|---|
| `XNetDnnSessionCpuCreate(model)` | 创建会话，一个模型可创建多个 |
| `XNetDnnSessionCpuInitializeInputs(session)` | 必须调用，返回 0 为成功 |
| `XNetDnnSessionCpuSetInput(session, name, tensor)` | `name` 取自 `GetInputName`，返回 0 为成功 |
| `XNetDnnSessionCpuRun(session, blocking)` | **实测 blocking 必须为 0**；传 1 在引擎内部崩溃。返回 0 为成功 |
| `XNetDnnSessionCpuGetOutput(session, name)` | 返回 tensor 指针本身；**未就绪时返回 NULL**，需判空 |
| `XNetDnnSessionCpuDestroy(session)` | 释放会话 |

#### 张量

| 函数 | 说明 |
|---|---|
| `XNetDnnTensorCpuCreate(rank, shape, kind)` | `shape` 为 `rank` 个 int64；`kind` 见上方枚举，越界会 `__fastfail` |
| `XNetDnnTensorCpuCreateFromBuffer(...)` | 从既有缓冲区创建；本项目未使用 |
| `XNetDnnTensorCpuLock / UnLock` | 取数据指针，读完必须 UnLock |
| `XNetDnnTensorCpuGetSizeInBytes` | 字节数 |
| `XNetDnnTensorCpuGetDim / GetShape / GetDataKind` | 取元信息；本项目未使用（原因见下） |
| `XNetDnnTensorCpuDestroy` | 释放张量 |

#### 工作区

| 函数 | 说明 |
|---|---|
| `XNetDnnWorkspaceCpuCreate(sizeInBytes)` / `...Destroy` | 本项目未使用 |

### 关键陷阱：输出张量的布局字段为零

**实测**：`GetOutput` 返回的 tensor 对象中，常规布局字段（dims 数组等）是
**零值**，直接用 `GetDim` / `GetShape` 会读到 0 或越界。

可用的对象内偏移（x64，本项目已验证）：

| 偏移 | 内容 |
|---|---|
| `+0x08` | `uint64_t rank` |
| `+0x10` | `int64_t dims[rank]`（连续） |
| `+0x50` | `int` data kind |

`tools\xnet_infer.cpp` 的 `readInfo()` 即按此读取。数据指针仍走
`Lock()` 获取。

### 最小可用示例（C）

```c
#include "xnet_capi.h"

int main(void) {
    // 1. 模型
    XNetModel model = XNetDnnModelCpuCreateFromFile("model.xnet", NULL);
    if (!model) return 5;

    // 2. 会话与输入
    XNetSession session = XNetDnnSessionCpuCreate(model);
    if (!session) return 6;
    if (XNetDnnSessionCpuInitializeInputs(session) != 0) return 7;

    int64_t shape[4] = {1, 3, 32, 200};
    XNetTensor input = XNetDnnTensorCpuCreate(4, shape, XNET_KIND_FP32);
    void *ptr = XNetDnnTensorCpuLock(input);
    // ... 写入 1*3*32*200 个 float32 ...
    XNetDnnTensorCpuUnLock(input);

    const char *inName = XNetDnnModelCpuGetInputName(model, 0);
    if (XNetDnnSessionCpuSetInput(session, inName, input) != 0) return 9;

    // 3. 运行：blocking 必须为 0
    if (XNetDnnSessionCpuRun(session, 0) != 0) return 10;

    // 4. 取输出
    XNetTensor out = XNetDnnSessionCpuGetOutput(session, "output");
    if (!out) return 11;
    uint64_t rank = *(uint64_t *)((unsigned char *)out + 0x08);
    int64_t *dims = (int64_t *)((unsigned char *)out + 0x10);
    int kind = *(int *)((unsigned char *)out + 0x50);
    void *data = XNetDnnTensorCpuLock(out);
    // ... 按 rank/dims/kind 解释 data ...
    XNetDnnTensorCpuUnLock(out);

    XNetDnnTensorCpuDestroy(input);
    XNetDnnSessionCpuDestroy(session);
    XNetDnnModelCpuDestroy(model);
    return 0;
}
```

崩溃场景（如非法 shape）建议用 SEH 包裹 `Run`，参考 `xnet_infer.cpp` 的
`SafeRun()`：`__try` 不能与 C++ 异常展开共存，须放在 `__declspec(noinline)`
的独立函数里。

### 本项目中的两种封装

| 方式 | 位置 | 适用 |
|---|---|---|
| C++ 子进程 | `tools\xnet_infer.cpp` → `xnet_infer.exe` | 主流水线；读 raw NCHW bin，出 bin + json |
| C++ 演示 | `tools\xnet_ocr_demo.cpp` → `xnet_ocr_demo.exe` | 单模型调用演示，验证导入库可用 |

Python 侧不直接调用 DLL，而是以子进程方式驱动 `xnet_infer.exe`
（见 `ocr\ocr_image.py` 的 `run_infer()`）。这样做的好处是引擎崩溃只终止
子进程，不会带走 Python 进程。

raw 输入格式：头部 `uint64 rank` + `rank × int64 dims` + `float32` 数据
（小端），见 `ocr\make_input.py` 的 `write_input_nchw()`。

---

## 许可与合规

- 模型文件、`XNet.dll`、`wxocr.dll` 均为**腾讯版权组件**，随微信安装分发。
  本项目仅在本机做本地识别研究，未重新分发这些二进制。
- 推理接口 `XNetDnn*Cpu*` 系通过静态分析逆向得到，**无官方授权与文档**，
  与微信 4.1.13.48 版本绑定，升级后不保证可用。
- 本项目代码部分可自由使用（见 [LICENSE](LICENSE)）；**模型与 DLL 部分请遵守
  腾讯相关条款**。
