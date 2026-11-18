# 独立可执行版（换电脑直接运行）

## 结论

`build\ocr\` 是**独立目录**：复制到任意 Windows x64 电脑，运行
`run_ocr_exe.bat` 即可识别图片，**目标机无需安装 Python、numpy、Pillow，
也无需安装微信**。

实测（2026-11-18）：PATH 削减到只剩 `C:\Windows\system32`、`C:\Windows`、
`C:\Windows\System32\Wbem`，10 个场景用例 **10/10 通过**。

## 产物结构

```
build\ocr\
  ocr.exe              打包后的 OCR 主程序
  run_ocr_exe.bat      一键入口
  xnet_infer.exe       C++ 推理驱动
  XNet.dll             推理引擎（随包携带）
  models\WeChatOcr-8096\   模型与字符集
  _internal\           PyInstaller 运行时（Python 解释器 + numpy + Pillow）
  _out\                识别结果输出目录（运行后生成）
```

体积 **79.8 MB**（`--slim`）：`_internal` 57.6 MB、模型 9.4 MB（仅检测/识别/
字符集三个文件）、其余为 exe 与 DLL。不加 `--slim` 为 119.9 MB，因为会一并
复制微信包内其余 11 个无关模型（超分、人脸/隐私、二维码、OCR 服务插件）。
已实测剔除后场景 10/10 不变，见 `build\test_slim.py`。

`_out\`、`_c\`、`_case\` 都是运行残留，可安全删除。

## 重新构建

需要 Python 3.10+、numpy、Pillow、PyInstaller；重新编译 C++ 还需要 MSVC。

```powershell
E:\ocr\tools\build_cpp.bat x64          # 可选，仅在改动 .cpp 后需要
python E:\ocr\build\build_exe.py --slim
```

`build_exe.py` 会：
1. 用 PyInstaller `--onedir` 打包 `ocr\ocr.py`
2. 把 `tools\xnet_infer.exe`、`runtime\XNet.dll`、`models\` 复制到产物目录
3. 生成 `run_ocr_exe.bat`
4. `--slim` 时删除 11 个未引用的模型资产
5. 清理 PyInstaller 中间目录（`build_tmp\`、`spec\`）

### 两个必须知道的构建约束

**① C++ 工具用 `/MT` 静态链接 CRT。** 因此 `xnet_infer.exe` /
`xnet_ocr_demo.exe` 不依赖 VC++ 运行库。若改用 `/MD`，产物会额外依赖
`VCRUNTIME140.dll`，在未安装可再发行组件的目标机上直接以 `0xC0000135`
启动失败。

**② `xnet_infer.exe` 通过导入表链接 `XNet.dll`。** Windows 在代码执行前就
解析该依赖，所以 `XNet.dll` 必须与 exe 同目录或在 `PATH` 中。Python 流水线
由 `ocr\paths.py` 解析出 DLL 目录并注入子进程 `PATH`；`tools\run_ocr.bat`
同样会把 `runtime\` 加入 `PATH`。

## 技术说明：这是「打包」而非「编译为机器码」

PyInstaller 是**打包器**：把 Python 解释器、依赖库与字节码封装进 exe，运行时
解包到内存/临时目录执行，并非编译成原生机器码。

它满足「目标机无需 Python」这一目标（已实测），两点如实说明：

- `--onedir` 模式运行时**不解包到临时目录**，没有冷启动惩罚：实测首次 0.99 秒，
  与后续一致（0.98 秒）。
- 若需真正编译为机器码，可选 Nuitka；本机未采用，因其对 numpy/Pillow 打包
  配置更复杂、构建更慢，且当前方案已通过全部验收。

## 目标机不需要 VC++ 运行库（静态验证）

`build\dep_closure.py` 扫描产物 56 个 PE 文件的全部导入 DLL：

| 类别 | 数量 | 说明 |
|---|---|---|
| 包内提供 | 11 | `python314.dll`、`python3.dll`、`pywintypes314.dll`、`libssl-3.dll`、`libcrypto-3.dll`、`libffi-8.dll`、`libscipy_openblas*.dll`、`VCRUNTIME140.dll`、`VCRUNTIME140_1.dll`、`msvcp140-*.dll`、`XNet.dll` |
| Windows 系统 | 35 | kernel32、user32、advapi32、ole32、shell32、ws2_32、crypt32、bcrypt、dbghelp、imagehlp、`api-ms-win-crt-*` 等（Win10+ 自带） |
| **外部 / 未找到** | **0** | 无 |

`python314.dll` 确实导入 `VCRUNTIME140.dll`，但该文件随包位于 `_internal\`，
且 bootloader 调用 `SetDllDirectory` 把 `_internal` 加入 DLL 搜索路径
（已在 `ocr.exe` 中检出相关符号），因此不依赖系统安装的 VC++ 运行库。

```powershell
python E:\ocr\build\dep_closure.py E:\ocr\build\ocr   # 期望 VC runtime dependencies: NONE
python E:\ocr\build\dep_blindspots.py E:\ocr\build\ocr
```

**盲区补查**（`objdump` 导入表不含 delay-load，`LoadLibrary*` 运行时才解析）：
实测 **delay-loaded DLL 0 个**；字面 DLL 名中唯一的非系统名字（`OpenCL.dll`、
`amdhip64*.dll`、`455_64.dll`）全部来自 `models\wxocr.dll`——那是**未使用的**
OCR 服务插件，推理只走 `XNet.dll`，项目代码无任何 `wxocr` 引用。

## 合规提示

产物中的 `XNet.dll` 与 `models\` 是**腾讯版权组件**，本项目不包含其源代码授权。
仅可用于自有设备做本地识别；**对外分发前请确认符合腾讯相关条款**。
更稳妥的做法：把 `build\ocr\` 复制到目标机后，用目标机自身微信安装目录下的
同名 `XNet.dll` 覆盖产物副本，并设 `XNET_WEIXIN_DIR` 指向它。

## 故障排查

| 现象 | 处置 |
|---|---|
| 缺少 `XNet.dll` | 确认产物目录内有该文件；或设 `XNET_WEIXIN_DIR` |
| 缺少模型 | 确认 `models\WeChatOcr-8096\` 随目录一起复制 |
| 缺少 `api-ms-win-*` | 目标机系统过旧，需 Windows 10 及以上 |
| `0xC0000135` 启动失败 | exe 以 `/MD` 编译，缺 VC++ 运行库；改用 `/MT` 重新编译 |
| 杀软误报 | PyInstaller 打包程序常见误报，属已知现象 |

环境变量说明见 [PORTABILITY.md](PORTABILITY.md)；其余排障见
[TROUBLESHOOTING.md](TROUBLESHOOTING.md)。
