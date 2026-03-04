@echo off
title Yuki - Запуск
chcp 65001 >nul

echo.
echo  ╔══════════════════════════════════╗
echo  ║        Yuki Assistant            ║
echo  ╚══════════════════════════════════╝
echo.

:: --- Проверка Python ---
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ОШИБКА] Python не найден!
    echo.
    echo  Пожалуйста, скачай Python с сайта:
    echo  https://www.python.org/downloads/
    echo.
    echo  Важно: при установке поставь галочку
    echo  "Add Python to PATH"
    echo.
    pause
    start https://www.python.org/downloads/
    exit /b 1
)

echo  [OK] Python найден.

:: --- Проверка pip ---
pip --version >nul 2>&1
if errorlevel 1 (
    echo  [INFO] pip не найден, устанавливаю...
    python -m ensurepip --upgrade
)

:: --- Файл-маркер: если есть — библиотеки уже ставились ---
set MARKER=.yuki_installed

if exist %MARKER% (
    echo  [OK] Библиотеки уже установлены.
    goto :launch
)

:: --- Первый запуск: устанавливаем зависимости ---
echo.
echo  ╔══════════════════════════════════╗
echo  ║   Первый запуск — установка      ║
echo  ║   библиотек (1-2 минуты)...      ║
echo  ╚══════════════════════════════════╝
echo.

pip install --upgrade pip >nul 2>&1

echo  Устанавливаю PyQt5...
pip install PyQt5 >nul 2>&1
if errorlevel 1 (
    echo  [ПРЕДУПРЕЖДЕНИЕ] PyQt5 не удалось установить. Попробуй вручную: pip install PyQt5
)

echo  Устанавливаю requests...
pip install requests >nul 2>&1

echo  Устанавливаю python-dotenv...
pip install python-dotenv >nul 2>&1

echo  Устанавливаю google-generativeai...
pip install google-generativeai >nul 2>&1

echo  Устанавливаю selenium (для YouTube авто-клика)...
pip install selenium >nul 2>&1

echo  Устанавливаю pycaw (управление громкостью)...
pip install pycaw comtypes >nul 2>&1

echo  Устанавливаю pyautogui (скриншоты)...
pip install pyautogui >nul 2>&1

:: --- Создаём маркер ---
echo installed > %MARKER%

echo.
echo  [ГОТОВО] Все библиотеки установлены!
echo.

:launch
:: --- Проверяем .env файл ---
if not exist .env (
    echo  [ВНИМАНИЕ] Файл .env не найден!
    echo.
    echo  Создаю .env файл...
    echo GEMINI_API_KEY=ВСТАВЬ_СВОЙ_КЛЮЧ_СЮДА > .env
    echo.
    echo  ┌─────────────────────────────────────────────┐
    echo  │  Открой файл .env в папке с Юки             │
    echo  │  и вставь свой ключ от Google Gemini API    │
    echo  │                                             │
    echo  │  Получить ключ: https://aistudio.google.com │
    echo  └─────────────────────────────────────────────┘
    echo.
    pause
    notepad .env
    echo.
)

:: --- Запуск Юки ---
echo  Запускаю Юки...
start "" pythonw yuki_char.py

:: Если pythonw не сработал — пробуем python
if errorlevel 1 (
    start "" python yuki_char.py
)

exit /b 0
