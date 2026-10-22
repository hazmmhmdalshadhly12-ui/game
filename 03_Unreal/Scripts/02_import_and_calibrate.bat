@echo off
REM THE LAST SIN: The Sin-Eater - M0
REM Step 2 of 3: automated FBX import + CAL-01 verification + test map creation.
REM Runs the editor in commandlet mode - no window, results in the log and in
REM 03_Unreal\Reports\import_report.json

setlocal
set "PROJ=%~dp0..\TLS.uproject"
set "UEBIN="

if defined TLS_UE_ROOT (
    set "UEBIN=%TLS_UE_ROOT%\Engine\Binaries\Win64"
)
if not defined UEBIN (
    for %%V in (5.6 5.5 5.4) do (
        if not defined UEBIN (
            if exist "%ProgramFiles%\Epic Games\UE_%%V\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" (
                set "UEBIN=%ProgramFiles%\Epic Games\UE_%%V\Engine\Binaries\Win64"
            )
        )
    )
)

if not defined UEBIN (
    echo [ERROR] Unreal Engine 5.4+ not found. Run 01_build_editor.bat first.
    pause
    exit /b 1
)

if not exist "%UEBIN%\UnrealEditor-Cmd.exe" (
    echo [ERROR] UnrealEditor-Cmd.exe not found under %UEBIN%.
    pause
    exit /b 1
)

echo [TLS M0] Importing calibration FBX files and verifying CAL-01...
"%UEBIN%\UnrealEditor-Cmd.exe" "%PROJ%" -run=pythonscript -script="%~dp0import_and_calibrate.py" -stdout -unattended -nopause -nosplash

echo.
echo [TLS M0] Done. Report: %~dp0..\Reports\import_report.json
echo [TLS M0] Read the "overall_pass" field (true = CAL-01 import checks passed).
pause
