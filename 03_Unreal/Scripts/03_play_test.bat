@echo off
REM THE LAST SIN: The Sin-Eater - M0
REM Step 3 of 3: open the editor on the test map and play.
REM
REM In the editor press Play (PIE):
REM   - The grey-box test room (floor, walls, collision blocks, sun) builds itself.
REM   - The calibration gnomon + reference figure are placed and measured
REM     (watch the Output Log for [CAL-01] lines).
REM   - Move: WASD / left stick. Look: mouse / right stick.
REM     Run: hold Shift / gamepad A. Crouch: hold C / press left stick.
REM   - NO jump by design (M0 movement contract).
REM   - Take documentation screenshots with F9 during PIE, then copy them from
REM     03_Unreal\Saved\Screenshots\ into reports\ (CAL-01 evidence).

setlocal
set "PROJ=%~dp0..\TLS.uproject"
set "UEBIN="

if defined TLS_UE_ROOT (
    set "UEBIN=%TLS_UE_ROOT%\Engine\Binaries\Win64"
)
if not defined UEBIN (
    for %%V in (5.6 5.5 5.4) do (
        if not defined UEBIN (
            if exist "%ProgramFiles%\Epic Games\UE_%%V\Engine\Binaries\Win64\UnrealEditor.exe" (
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

if not exist "%UEBIN%\UnrealEditor.exe" (
    echo [ERROR] UnrealEditor.exe not found under "%UEBIN%".
    echo   Check the TLS_UE_ROOT value or run 01_build_editor.bat first.
    pause
    exit /b 1
)

echo [TLS M0] Opening the editor on L_TLS_TestRoom...
start "" "%UEBIN%\UnrealEditor.exe" "%PROJ%"
