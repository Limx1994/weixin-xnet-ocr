@echo off
REM Launcher for the C++ inference demo (validates the XNet.lib binding).
REM
REM This is the low-level model probe, not the full OCR pipeline. The full
REM pipeline is run_ocr_py.bat, which drives ocr\ocr.py.
REM
REM The demo itself locates XNet.dll (override, bundled copy, then the newest
REM Weixin version subdirectory), so this launcher does not need to. It only
REM puts the tools directory on PATH for the exe's own dependencies.
REM
REM Usage:
REM   run_ocr.bat ^<model.xnet^> ^<height^> ^<width^>
setlocal
set "TOOLS_DIR=%~dp0"

if "%~1"=="" goto :usage

REM xnet_ocr_demo.exe links XNet.dll through its import table, so Windows
REM resolves it before any code runs: it must sit next to the exe or on PATH.
REM The project keeps its copy in ..\runtime, so put that on PATH. An explicit
REM XNET_WEIXIN_DIR still wins.
if "%XNET_WEIXIN_DIR%"=="" if exist "%TOOLS_DIR%..\runtime\XNet.dll" (
    set "XNET_WEIXIN_DIR=%TOOLS_DIR%..\runtime"
)
set "PATH=%TOOLS_DIR%;%XNET_WEIXIN_DIR%;%PATH%"

"%TOOLS_DIR%xnet_ocr_demo.exe" %*
exit /b %ERRORLEVEL%

:usage
echo usage: run_ocr.bat ^<model.xnet^> ^<height^> ^<width^>
echo.
echo example:
echo   run_ocr.bat "%~dp0..\models\WeChatOcr-8096\text_det_fp16_v2.xnet" 64 256
echo.
echo optional environment override:
echo   XNET_WEIXIN_DIR   directory holding XNet.dll
exit /b 2
