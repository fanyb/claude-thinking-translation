@echo off
setlocal
cd /d "%~dp0"
py -3 -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>&1
if not errorlevel 1 (
    py -3 -X utf8 install.py install
) else (
    python -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>&1
    if errorlevel 1 (
        echo Please install Python 3.10 or later, then run this installer again.
        start "" "https://www.python.org/downloads/windows/"
        pause
        exit /b 1
    )
    python -X utf8 install.py install
)
if errorlevel 1 (
    pause
    exit /b 1
)
