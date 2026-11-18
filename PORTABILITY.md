# 可移植性与部署

回答「把 `E:\ocr` 复制到任意位置、任意 Windows 电脑，能否直接运行」。

## 结论

| 形态 | 目标机要求 | 验证方式 |
|---|---|---|
| **独立 exe 版**（`build\ocr\`） | **无要求**（不需 Python、不需微信） | PATH 削减到 3 个系统目录后 10/10 场景通过 |
| 源码版 | Python 3.10+ 与 numpy/Pillow | 移除 `E:\ocr` 后副本完整运行 |

推荐交付 **独立 exe 版**，复制 `build\ocr\` 整个目录即可。构建见
[BUILD_EXE.md](BUILD_EXE.md)。

## 项目自包含的部分（源码版）

| 内容 | 位置 |
|---|---|
| OCR 模型（2 个 `.xnet`） | `models\WeChatOcr-8096\` |
| 字符集字典 | `models\WeChatOcr-8096\charset_zh13562.txt` |
| 推理引擎 `XNet.dll` | `runtime\XNet.dll` |
| 推理器 `xnet_infer.exe` | `tools\` |
| 导入库 `XNet.lib` / `XNet.def` | `tools\` |
| 全部 Python 流水线 | `ocr\` |

路径不硬编码：`ocr\paths.py` 从自身位置推导，优先使用项目内 `runtime\XNet.dll`
（`_weixin_candidates()` 把 bundled 目录排在微信目录之前）。两个 `.bat` 用
`%~dp0` 自解析。

## 环境变量

全部可选，仅在自动探测失败时需要设置：

| 变量 | 指向 | 默认探测顺序 |
|---|---|---|
| `XNET_MODEL_DIR` | 模型与字典目录 | `<项目根>\models\WeChatOcr-8096`（打包版为 `<exe目录>\models\WeChatOcr-8096`） |
| `XNET_TOOLS_DIR` | `xnet_infer.exe` 所在目录 | `<项目根>\tools`（打包版为 `<exe目录>`） |
| `XNET_INFER` | 推理器可执行文件 | `<XNET_TOOLS_DIR>\xnet_infer.exe` |
| `XNET_WEIXIN_DIR` | `XNet.dll` 所在目录 | ① `runtime\` 随包副本 ② 微信安装目录（版本号倒序探测） |

```powershell
$env:XNET_WEIXIN_DIR = "D:\Weixin"
```

## 外部依赖

| 依赖 | 独立 exe 版 | 源码版 |
|---|---|---|
| Python | 不需要 | 需要 3.10+ |
| numpy / Pillow | 不需要 | `pip install numpy Pillow` |
| `XNet.dll` | 随包携带 | 优先用 `runtime\` 副本，可回退到微信目录 |
| Windows x64 | 需要 | 需要 |
| VC++ 运行库 | 不需要（exe 已 `/MT` 静态链接） | 同左 |

## XNet.dll 的版本绑定

`XNet.dll` 来自微信安装目录，属腾讯版权组件。项目在 `runtime\` 下保留了一份
已验证副本，使源码版与打包版都不依赖微信安装：

```
C:\Program Files (x86)\Tencent\Weixin\4.1.13.48\XNet.dll
SHA-256 12d07bab58aecb6dde9b91bc03b9ba69301914741a0d1aff46a951ce9a28648d
大小 6.97 MB
```

微信升级后 DLL 可能变化，接口不保证兼容；随包副本反而能规避该问题。
`paths.py` 仍会探测 `Weixin` 目录作为回退。

C++ 侧同样不绑定版本号：`xnet_ocr_demo.exe` 按
`XNET_WEIXIN_DIR` → exe 同目录 → 版本号最新的微信子目录 → 安装根目录
的顺序自行搜索；`tools\run_ocr.bat` 会把 `runtime\` 加进 `PATH`。
`tools\xnet_infer.exe` 由 Python 流水线在子进程中注入 DLL 目录，
直接单独运行它需要 `XNet.dll` 位于同目录或 `PATH` 中。

## 换机部署步骤

1. 复制整个项目目录到目标机任意位置（如 `D:\ocr`）。
2. 安装 Python 3.10+ 与 `pip install numpy Pillow`（独立 exe 版跳过此步）。
3. 诊断路径解析：`python D:\ocr\ocr\paths.py`，期望每行都是 `OK`。
4. 运行：`D:\ocr\tools\run_ocr_py.bat "C:\path\to\image.png"`。

若 `paths.py` 报 `MISS`，按上表设置环境变量。

## 已验证的可移植场景

| 场景 | 结果 |
|---|---|
| **打包 exe 版 + PATH 仅 3 个系统目录 + 10 场景** | **通过** |
| 打包 exe 版复制到桌面运行 | 通过 |
| 源码版复制到桌面运行 | 通过 |
| 源码版移除 `E:\ocr` 后运行副本 | 通过 |
| 源码版剔除全部微信 PATH 项（用 `runtime\` 副本） | 通过 |
| 环境变量指向不存在的路径 | 明确报 `FileNotFoundError` 并提示设置项 |

## 未验证 / 不适用

- 未在其他物理机器上实测。上述结论基于等价条件：PATH 被削减到仅系统目录、
  且 `E:\ocr` 被移除，此时项目不读取自身目录以外的任何文件。
- 未在 Windows 7/8 或非 x64 系统验证；`xnet_infer.exe` 为 x64，
  PyInstaller 运行时要求 Windows 10 及以上。
- macOS / Linux 不适用（`XNet.dll` 与 exe 均为 Windows 二进制）。

## 合规提示

`runtime\XNet.dll` 与 `models\` 均为腾讯版权组件。随包分发前请确认符合相关
条款；自用与自有设备通常无问题，**对外分发需自行评估**。详见
[MODELS.md](MODELS.md) 与 [BUILD_EXE.md](BUILD_EXE.md)。
