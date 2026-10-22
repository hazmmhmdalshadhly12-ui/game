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
if errorlevel 1 (
    echo.
    echo [ERROR] UnrealEditor-Cmd.exe exited with an error - the import did NOT
    echo   complete successfully. Read the log above and fix before re-running.
    pause
    exit /b 1
)

set "REPORT=%~dp0..\Reports\import_report.json"
if not exist "%REPORT%" (
    echo.
    echo [ERROR] Import report not found: %REPORT%
    echo   The import script did not run to completion - see the log above.
    pause
    exit /b 1
)

REM The report is authoritative: only "overall_pass": true counts as success.
findstr /C:"overall_pass" "%REPORT%" | findstr /C:"true" >nul
if errorlevel 1 (
    echo.
    echo [ERROR] CAL-01 report says overall_pass=false - the import FAILED.
    echo   Read the [CAL-01] FAIL lines above and fix before re-running.
    pause
    exit /b 1
)

echo.
echo [TLS M0] Import + CAL-01 PASSED. Report: %REPORT%
pause
