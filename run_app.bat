@echo off
echo Running School Timetable Algorithm...

:: Try to find Python in common locations
set PYTHON_FOUND=0

:: Check if python is in PATH
where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Found Python in PATH
    python gui.py
    set PYTHON_FOUND=1
    goto :end
)

:: Check if py launcher is available
where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Found Python launcher
    py gui.py
    set PYTHON_FOUND=1
    goto :end
)

:: Check common Python locations
for %%P in (
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
    "C:\Python310\python.exe"
    "C:\Python39\python.exe"
    "C:\Program Files\Python312\python.exe"
    "C:\Program Files\Python311\python.exe"
    "C:\Program Files\Python310\python.exe"
    "C:\Program Files\Python39\python.exe"
    "C:\Program Files (x86)\Python312\python.exe"
    "C:\Program Files (x86)\Python311\python.exe"
    "C:\Program Files (x86)\Python310\python.exe"
    "C:\Program Files (x86)\Python39\python.exe"
) do (
    if exist %%P (
        echo Found Python at %%P
        %%P gui.py
        set PYTHON_FOUND=1
        goto :end
    )
)

:: If Python not found yet, check Microsoft Store installation locations
for /f "delims=" %%a in ('dir /b /s "%LOCALAPPDATA%\Microsoft\WindowsApps\python*.exe" 2^>nul') do (
    echo Found Python at %%a
    "%%a" gui.py
    set PYTHON_FOUND=1
    goto :end
)

:: If we reach here, Python wasn't found
if %PYTHON_FOUND% EQU 0 (
    echo Error: Python not found on this system.
    echo Please install Python from https://www.python.org/downloads/
    pause
)

:end
echo Done.
pause
