@echo off
setlocal
rem planning-with-files: Windows hook launcher for Codex (issue #201).
rem Codex runs each hook's commandWindows; on Windows that routes here as:
rem   cmd /c .codex\hooks\pwf-hook.cmd <script.py> [args...]
rem A .cmd is the one form that runs identically whether Codex spawns the hook
rem via cmd.exe, PowerShell, or direct CreateProcess, and it lets us fall back
rem from the py launcher to python.exe. The Microsoft Store python3.exe alias is
rem deliberately never selected. Always exits 0 so an advisory hook cannot
rem report "hook exited with code 1".
set "PY_EXE="
set "PY_ARGS="
if defined PYTHON_BIN if exist "%PYTHON_BIN%" set "PY_EXE=%PYTHON_BIN%"
if not defined PY_EXE where py >nul 2>nul && set "PY_EXE=py" && set "PY_ARGS=-3"
if not defined PY_EXE where python >nul 2>nul && set "PY_EXE=python"
rem Codex can start hooks with a reduced PATH. Probe the normal uv and CPython
rem install locations so a valid user installation still works in that case.
if not defined PY_EXE for /d %%D in ("%APPDATA%\uv\python\*") do if exist "%%~fD\python.exe" if not defined PY_EXE set "PY_EXE=%%~fD\python.exe"
if not defined PY_EXE for /d %%D in ("%LOCALAPPDATA%\uv\python\*") do if exist "%%~fD\python.exe" if not defined PY_EXE set "PY_EXE=%%~fD\python.exe"
if not defined PY_EXE for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python*") do if exist "%%~fD\python.exe" if not defined PY_EXE set "PY_EXE=%%~fD\python.exe"
if not defined PY_EXE exit /b 0
"%PY_EXE%" %PY_ARGS% "%~dp0%~1" %2 %3 %4 %5
exit /b 0
