@echo off
REM Build the C++ tools against the generated XNet.lib.
REM Usage: build_cpp.bat [x64|x86]
setlocal
set "HERE=%~dp0"
if "%HERE:~-1%"=="\" set "HERE=%HERE:~0,-1%"
set "ARCH=%~1"
if "%ARCH%"=="" set "ARCH=x64"

if "%ARCH%"=="x64" (
    set "VCVARS=D:\APPS\VSBuildTools2019\VC\Auxiliary\Build\vcvars64.bat"
) else (
    set "VCVARS=D:\APPS\VSBuildTools2019\VC\Auxiliary\Build\vcvars32.bat"
)

if not exist "%VCVARS%" (
    echo [ERROR] vcvars not found: %VCVARS%
    exit /b 1
)

call "%VCVARS%" >nul || exit /b 1

REM /MT links the CRT statically, so the exe has no VC++ runtime dependency
REM and runs on a machine that never installed the redistributable.
REM xnet_infer: generic NCHW raw inference driver used by the Python pipeline.
cl /nologo /EHsc /O2 /MT /W3 /I"%HERE%" "%HERE%\xnet_infer.cpp" /link /OUT:"%HERE%\xnet_infer.exe" "%HERE%\XNet.lib"
if errorlevel 1 exit /b 1

REM xnet_ocr_demo: model-level probe proving the XNet.lib binding works.
cl /nologo /EHsc /O2 /MT /W3 /I"%HERE%" "%HERE%\xnet_ocr_demo.cpp" /link /OUT:"%HERE%\xnet_ocr_demo.exe" "%HERE%\XNet.lib"
if errorlevel 1 exit /b 1

echo [OK] built xnet_infer.exe and xnet_ocr_demo.exe
endlocal
