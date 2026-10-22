@echo off
REM THE LAST SIN: The Sin-Eater - M1
REM Play the M1 vertical slice "Day One in Blackthorne".
REM
REM In the editor press Play (PIE) on L_TLS_Blackthorne:
REM   - The village blockout builds itself from 05_Narrative/world data.
REM   - Day 1: attend the burial, find the untouched dish at the boundary
REM     stone, take the cottage, talk (E) to Gwendolyn / Crane / Coles / Mair,
REM     examine + restore at the father's table, link evidence on the ledger
REM     board, sleep to end the day.
REM   - Day 2: the miller is dead - the first crime scene of the case.
REM   - Move: WASD, look: mouse, run: Shift, crouch: C. Interact: E.
REM     Journal: J. Panels: 1-9 select, R restore page, Esc close.
REM   - Save: the writing desk in the cottage (E). Auto-continue on next run.
REM   - TLS.NewGame in the console restarts from Day 1.

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

echo [TLS M1] Opening the editor (startup map: L_TLS_Blackthorne)...
start "" "%UEBIN%\UnrealEditor.exe" "%PROJ%"
