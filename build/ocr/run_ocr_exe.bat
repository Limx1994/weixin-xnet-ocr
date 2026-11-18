@echo off
REM One-click OCR. No Python installation required.
REM Usage: run_ocr_exe.bat <image> [long_side]
setlocal
set "HERE=%~dp0"
if "%~1"=="" goto :usage
if "%~2"=="" (
    "%HERE%ocr.exe" "%~1" --out "%HERE%_out"
) else (
    "%HERE%ocr.exe" "%~1" --long %~2 --out "%HERE%_out"
)
exit /b %ERRORLEVEL%

:usage
echo usage: run_ocr_exe.bat ^<image^> [long_side]
echo example: run_ocr_exe.bat "C:\path\to\image.png"
exit /b 2
