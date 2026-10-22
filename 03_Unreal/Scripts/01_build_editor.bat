@echo off
REM THE LAST SIN: The Sin-Eater - M0
REM Step 1 of 3: locate UE 5.4+ and build the TLS editor binaries.
REM Requires: Windows 10/11 64-bit, Unreal Engine 5.4+ (Epic Launcher),
REM           Visual Studio 2022 with the "Game development with C++" workload.

setlocal
set "PROJ=%~dp0..\TLS.uproject"
set "UEBIN="

REM Engine lookup order: TLS_UE_ROOT env var, then standard Launcher installs (newest first).
if defined TLS_UE_ROOT (
    set "UEBIN=%TLS_UE_ROOT%\Engine\Binaries\Win64"
)
if not defined UEBIN (
    for %%V in (5.6 5.5 5.4) do (
        if not defined UEBIN (
            if exist "%ProgramFiles%\Epic Games\UE_%%V\Engine\Binaries\Win64\UnrealEditor.exe" (
                set "UEBIN=%ProgramFiles%\Epic Games\UE_%%V\Engine\Binaries\Win64"
                set "UEVER=%%V"
            )
        )
    )
)

if not defined UEBIN (
    echo [ERROR] Unreal Engine 5.4+ not found.
    echo   Install it with the Epic Games Launcher, or set TLS_UE_ROOT to the engine folder,
    echo   e.g.: set TLS_UE_ROOT=C:\Program Files\Epic Games\UE_5.4
    pause
    exit /b 1
)

for %%I in ("%UEBIN%") do set "UEROOT=%%~dp0..\.."
set "UEBUILD=%UEROOT%\Engine\Build\BatchFiles"

echo [TLS M0] Using engine: %UEBIN%
echo [TLS M0] Building TLSEditor (Win64 Development)...
call "%UEBUILD%\Build.bat" TLSEditor Win64 Development -project="%PROJ%" -waitmutex

if errorlevel 1 (
    echo [ERROR] Build failed. Make sure Visual Studio 2022 with "Game development with C++" is installed.
    pause
    exit /b 1
)

echo.
echo [TLS M0] Build OK. Next step: run 02_import_and_calibrate.bat
pause
