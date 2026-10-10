@echo off
setlocal
cd /d "%~dp0"

set GODOT_EXE=
set CACHE_FILE=%~dp0.godot_path.txt

rem Remembered from a previous successful run - fastest path, and lets
rem you fix a wrong guess by just editing this file directly.
if exist "%CACHE_FILE%" set /p GODOT_EXE=<"%CACHE_FILE%"
if defined GODOT_EXE if not exist "%GODOT_EXE%" set GODOT_EXE=
if defined GODOT_EXE goto :found

where godot >nul 2>nul
if not errorlevel 1 (
    set GODOT_EXE=godot
    goto :found
)

if exist "%~dp0godot.exe" set GODOT_EXE=%~dp0godot.exe
if defined GODOT_EXE goto :found
if exist "%~dp0Godot.exe" set GODOT_EXE=%~dp0Godot.exe
if defined GODOT_EXE goto :found
if exist "%LOCALAPPDATA%\Programs\Godot\Godot.exe" set GODOT_EXE=%LOCALAPPDATA%\Programs\Godot\Godot.exe
if defined GODOT_EXE goto :found
if exist "%ProgramFiles%\Godot\Godot.exe" set GODOT_EXE=%ProgramFiles%\Godot\Godot.exe
if defined GODOT_EXE goto :found
if exist "%ProgramFiles(x86)%\Godot\Godot.exe" set GODOT_EXE=%ProgramFiles(x86)%\Godot\Godot.exe
if defined GODOT_EXE goto :found
if exist "%ProgramFiles(x86)%\Steam\steamapps\common\Godot Engine\godot.exe" set "GODOT_EXE=%ProgramFiles(x86)%\Steam\steamapps\common\Godot Engine\godot.exe"
if defined GODOT_EXE goto :found

rem Most people just unzip the Godot download wherever and run the exe
rem directly - it's never on PATH and never in a "Program Files"-style
rem location. The download itself is named e.g. Godot_v4.3-stable_win64.exe,
rem never just "Godot.exe", so search by wildcard in the places that
rem actually land in.
echo Searching your Desktop, Downloads, and this folder for a Godot
echo executable - this is a one-time search, remembered for next time...

for /f "delims=" %%F in ('dir /b /s /a-d "%~dp0Godot*.exe" 2^>nul') do (
    set "GODOT_EXE=%%F"
    goto :found
)
for /f "delims=" %%F in ('dir /b /s /a-d "%USERPROFILE%\Desktop\Godot*.exe" 2^>nul') do (
    set "GODOT_EXE=%%F"
    goto :found
)
for /f "delims=" %%F in ('dir /b /s /a-d "%USERPROFILE%\Downloads\Godot*.exe" 2^>nul') do (
    set "GODOT_EXE=%%F"
    goto :found
)

echo Godot wasn't found automatically. Either:
echo   - put its full .exe path into a new file "%CACHE_FILE%", or
echo   - copy the Godot .exe into this folder, or
echo   - add it to your PATH as "godot"
echo and run this shortcut again.
pause
exit /b 1

:found
echo %GODOT_EXE%>"%CACHE_FILE%"
echo Launching Kiara in Godot ^(%GODOT_EXE%^)...
"%GODOT_EXE%" --path "%~dp0godot"
if errorlevel 1 pause
