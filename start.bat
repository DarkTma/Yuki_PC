@echo off
title Yuki Assistant - Launcher
chcp 437 >nul

echo.
echo  +==================================+
echo  ^|       Yuki Assistant             ^|
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

if exist %MARKER% (
    echo  [OK] Libraries already installed.
    goto :launch
)

:: --- First launch: install dependencies ---
echo.
echo  +==================================+
echo  ^|  First launch - installing       ^|
echo  ^|  libraries (1-2 minutes)...      ^|
echo  +==================================+
echo.

echo  Upgrading pip...
pip install --upgrade pip >nul 2>&1

echo  Installing PyQt5...
pip install PyQt5 >nul 2>&1
if errorlevel 1 (
    echo  [WARNING] PyQt5 failed. Try manually: pip install PyQt5
)

echo  Installing requests...
pip install requests >nul 2>&1

echo  Installing python-dotenv...
pip install python-dotenv >nul 2>&1

echo  Installing google-generativeai...
pip install google-generativeai >nul 2>&1

echo  Installing selenium (YouTube auto-click)...
pip install selenium >nul 2>&1

echo  Installing pycaw (volume control)...
pip install pycaw comtypes >nul 2>&1

echo  Installing pyautogui (screenshots)...
pip install pyautogui >nul 2>&1

:: --- Create marker ---
echo installed > %MARKER%

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
