@echo off
title Yuki Assistant - Launcher
chcp 437 >nul

echo.
echo  +==================================+
echo  ^|        Yuki Assistant            ^|
echo  +==================================+
echo.

:: --- Check Python ---
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found!
    echo.
    echo  Please download Python from:
    echo  https://www.python.org/downloads/
    echo.
    echo  IMPORTANT: Check "Add Python to PATH" during install!
    echo.
    pause
    start https://www.python.org/downloads/
    exit /b 1
)

echo  [OK] Python found.

:: --- Check pip ---
pip --version >nul 2>&1
if errorlevel 1 (
    echo  [INFO] pip not found, installing...
    python -m ensurepip --upgrade
)

echo  [OK] pip found.

:: --- Marker file: if exists - libraries already installed ---
set MARKER=.yuki_installed
set MARKER_VER=5

:: Check marker version (re-install if outdated)
if exist %MARKER% (
    findstr /c:"v%MARKER_VER%" %MARKER% >nul 2>&1
    if errorlevel 1 (
        echo  [INFO] Updating libraries...
        del %MARKER%
    ) else (
        echo  [OK] Libraries already installed.
        goto :launch
    )
)

:: --- First launch or update: install dependencies ---
echo.
echo  +==================================+
echo  ^|  Installing dependencies...      ^|
echo  ^|  (This may take a few minutes)   ^|
echo  +==================================+
echo.

echo  Upgrading pip...
python -m pip install --upgrade pip >nul 2>&1

echo  Installing libraries from requirements.txt...
if exist requirements.txt (
    pip install -r requirements.txt
    if errorlevel 1 (
        echo  [WARNING] Some packages failed or need fallback.
        echo  [INFO] Trying pipwin fallback for PyAudio...
        pip install pipwin >nul 2>&1
        pipwin install pyaudio >nul 2>&1
    )
) else (
    echo  [ERROR] requirements.txt not found! 
    echo  Please ensure it is in the same folder as start.bat.
    echo.
    pause
    exit /b 1
)

:: --- Create marker with version ---
echo v%MARKER_VER% > %MARKER%

echo.
echo  [DONE] All libraries installed!
echo.

:launch
:: --- Check .env file ---
if not exist .env (
    echo  [WARNING] .env file not found!
    echo.
    echo  Creating .env template...
    echo GEMINI_API_KEY=PASTE_YOUR_KEY_HERE > .env
    echo.
    echo  +---------------------------------------------+
    echo  ^|  Open the .env file in Yuki folder          ^|
    echo  ^|  and paste your Google Gemini API key       ^|
    echo  ^|                                             ^|
    echo  ^|  Get key: https://aistudio.google.com       ^|
    echo  +---------------------------------------------+
    echo.
    pause
    notepad .env
    echo.
)

:: --- Launch Yuki ---
echo  Launching Yuki...
start "" pythonw yuki_char.py
if errorlevel 1 (
    start "" python yuki_char.py
)

exit /b 0