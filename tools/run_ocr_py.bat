@echo off
REM One-click entry point: image -> recognised text.
REM
REM This script resolves its own location, so the project can be copied to any
REM directory and still run. Weixin's install directory is discovered by
REM ocr\paths.py; set XNET_WEIXIN_DIR if it lives elsewhere.
REM
REM Usage:
REM   run_ocr_py.bat <image.png|jpg|bmp|tif> [long_side]
setlocal
set "OCR_DIR=%~dp0..\ocr"
if not exist "%OCR_DIR%\ocr.py" goto :no_code

if "%~1"=="" goto :usage

python "%OCR_DIR%\ocr.py" "%~1" --out "%OCR_DIR%\_run" %~2
exit /b %ERRORLEVEL%

:no_code
echo [ERROR] ocr.py not found under %OCR_DIR%
exit /b 1

:usage
echo usage: run_ocr_py.bat ^<image^> [long_side]
echo.
echo examples:
echo   run_ocr_py.bat "C:\path\to\image.png"
echo   run_ocr_py.bat "C:\path\to\image.png" 1280
echo.
echo recognised text is printed to stdout; structured JSON is written to
echo %OCR_DIR%\_run\result.json
echo.
echo optional environment overrides:
echo   XNET_MODEL_DIR    model + charset directory
echo   XNET_TOOLS_DIR    directory holding xnet_infer.exe
echo   XNET_WEIXIN_DIR   directory holding XNet.dll
exit /b 2
