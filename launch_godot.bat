@echo off
setlocal
cd /d "%~dp0"

set GODOT_EXE=
where godot >nul 2>nul && set GODOT_EXE=godot
if not defined GODOT_EXE if exist "%~dp0godot.exe" set GODOT_EXE=%~dp0godot.exe
if not defined GODOT_EXE if exist "%~dp0Godot.exe" set GODOT_EXE=%~dp0Godot.exe
if not defined GODOT_EXE if exist "%LOCALAPPDATA%\Programs\Godot\Godot.exe" set GODOT_EXE=%LOCALAPPDATA%\Programs\Godot\Godot.exe

if not defined GODOT_EXE (
    echo Godot 4.3+ wasn't found.
    echo Download it from https://godotengine.org/download, then either:
    echo   - add godot.exe to your PATH, or
    echo   - copy godot.exe into this folder ^(next to this .bat^)
    echo and run this shortcut again.
    pause
    exit /b 1
)

echo Launching Kiara in Godot...
"%GODOT_EXE%" --path "%~dp0godot"
if errorlevel 1 pause
