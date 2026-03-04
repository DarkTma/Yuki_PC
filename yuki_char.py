import os
import sys
import site
import tempfile
import requests
import json
import warnings
import winsound
import webbrowser
import subprocess
import urllib.parse
import time
import traceback
import datetime
from threading import Thread
from dotenv import load_dotenv
import google.generativeai as genai



# Скрываем предупреждение от Google, чтобы оно не мусорило в консоли
warnings.filterwarnings("ignore", category=FutureWarning)
import google.generativeai as genai

# Насильно заставляем Windows искать плагины там, где нужно
try:
    paths = site.getsitepackages()
except AttributeError:
    paths = [site.getusersitepackages()]
for p in paths:
    qt_path = os.path.join(p, 'PyQt5', 'Qt5', 'plugins', 'platforms')
    if os.path.exists(qt_path):
        os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = qt_path
        break

# --- Импорты PyQt5 ---
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QPushButton,
                             QSystemTrayIcon, QMenu, QAction, QVBoxLayout,
                             QGraphicsDropShadowEffect, QDialog, QHBoxLayout,
                             QLineEdit, QTextEdit, QScrollArea, QComboBox,
                             QSizePolicy, QFrame)
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint, QThread, pyqtSignal, QUrl, QTimer
from PyQt5.QtGui import QPixmap, QIcon, QColor, QFont, QTextCursor
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint, QThread, pyqtSignal, QUrl
from PyQt5.QtMultimedia import QSoundEffect

# --- НАСТРОЙКА GEMINI ---
load_dotenv()  # загружает переменные из .env файла

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


# =============================================
# --- ГЛОБАЛЬНЫЙ ЛОГГЕР ЮКИ ---
# =============================================

class YukiLogger:
    """
    Глобальный синглтон-логгер.
    Хранит все записи в памяти и пишет в файл yuki.log.
    Категории: INFO, WARNING, ERROR, COMMAND, AI
    """
    _instance = None
    LOG_FILE = "yuki.log"
    MAX_ENTRIES = 500  # максимум записей в памяти

    # Сигнал — чтобы LogWindow обновлялась в реальном времени
    # (не QObject, поэтому используем callback)
    _listeners = []

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.entries = []  # список dict: {time, level, source, message}
        # Перехватываем sys.excepthook — ловим все необработанные исключения
        sys._yuki_orig_excepthook = sys.excepthook
        sys.excepthook = self._excepthook

    def _excepthook(self, exc_type, exc_value, exc_tb):
        msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        self.log("ERROR", "CRASH", msg.strip())
        # Вызываем оригинальный обработчик
        sys._yuki_orig_excepthook(exc_type, exc_value, exc_tb)

    def log(self, level: str, source: str, message: str):
        """level: INFO | WARNING | ERROR | COMMAND | AI"""
        now = datetime.datetime.now().strftime("%H:%M:%S")
        entry = {"time": now, "level": level, "source": source, "message": message}
        self.entries.append(entry)
        if len(self.entries) > self.MAX_ENTRIES:
            self.entries.pop(0)

        # Пишем в файл
        try:
            with open(self.LOG_FILE, "a", encoding="utf-8") as f:
                date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{date}] [{level}] [{source}] {message}\n")
        except Exception:
            pass

        # Уведомляем слушателей (LogWindow)
        for cb in self._listeners:
            try:
                cb(entry)
            except Exception:
                pass

    def add_listener(self, callback):
        self._listeners.append(callback)

    def remove_listener(self, callback):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def clear(self):
        self.entries.clear()
        try:
            open(self.LOG_FILE, "w").close()
        except Exception:
            pass


# Глобальный экземпляр
logger = YukiLogger.get()
logger.log("INFO", "STARTUP", "Yuki started")


# =============================================
# --- ОКНО ЛОГОВ ---
# =============================================

class LogWindow(QWidget):
    """Красивое окно логов в стиле Юки."""

    # Цвета уровней
    LEVEL_COLORS = {
        "INFO":    "#00ffff",
        "WARNING": "#ffdd57",
        "ERROR":   "#ff4d4d",
        "COMMAND": "#a8ff78",
        "AI":      "#cc99ff",
    }

    def __init__(self, skin="default"):
        super().__init__()
        self.skin = skin
        self.current_filter = "ALL"
        self._setup_ui()
        self._apply_theme()
        # Подписываемся на новые записи
        logger.add_listener(self._on_new_entry)
        # Загружаем существующие записи
        self._reload_all()

    def _setup_ui(self):
        self.setWindowTitle("Yuki — Logs")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(700, 450)

        # Центрируем по экрану
        screen = QApplication.primaryScreen().geometry()
        self.move(
            screen.center().x() - 350,
            screen.center().y() - 225
        )

        # --- Основной контейнер ---
        self.container = QWidget(self)
        self.container.setObjectName("container")
        self.container.resize(700, 450)

        root = QVBoxLayout(self.container)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- Заголовок ---
        header = QWidget()
        header.setObjectName("header")
        header.setFixedHeight(44)
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(14, 0, 10, 0)

        title = QLabel("  Yuki — Logs")
        title.setObjectName("title")
        h_lay.addWidget(title)
        h_lay.addStretch()

        # Фильтр по уровню
        self.filter_box = QComboBox()
        self.filter_box.setObjectName("filterBox")
        self.filter_box.addItems(["ALL", "INFO", "WARNING", "ERROR", "COMMAND", "AI"])
        self.filter_box.setFixedWidth(110)
        self.filter_box.currentTextChanged.connect(self._on_filter_changed)
        h_lay.addWidget(self.filter_box)

        # Кнопка копировать
        copy_btn = QPushButton("Copy")
        copy_btn.setObjectName("headerBtn")
        copy_btn.setFixedSize(60, 28)
        copy_btn.clicked.connect(self._copy_logs)
        h_lay.addWidget(copy_btn)

        # Кнопка очистить
        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("headerBtn")
        clear_btn.setFixedSize(60, 28)
        clear_btn.clicked.connect(self._clear_logs)
        h_lay.addWidget(clear_btn)

        # Кнопка закрыть
        close_btn = QPushButton("✕")
        close_btn.setObjectName("closeBtn")
        close_btn.setFixedSize(32, 32)
        close_btn.clicked.connect(self.hide)
        h_lay.addWidget(close_btn)

        root.addWidget(header)

        # --- Разделитель ---
        line = QFrame()
        line.setObjectName("divider")
        line.setFrameShape(QFrame.HLine)
        line.setFixedHeight(1)
        root.addWidget(line)

        # --- Лог-текст ---
        self.log_text = QTextEdit()
        self.log_text.setObjectName("logText")
        self.log_text.setReadOnly(True)
        self.log_text.setLineWrapMode(QTextEdit.NoWrap)
        root.addWidget(self.log_text)

        # --- Строка статуса ---
        self.status_bar = QLabel(" Ready")
        self.status_bar.setObjectName("statusBar")
        self.status_bar.setFixedHeight(24)
        root.addWidget(self.status_bar)

        # Перетаскивание окна
        self._drag_pos = None
        header.mousePressEvent   = self._header_press
        header.mouseMoveEvent    = self._header_move
        header.mouseReleaseEvent = self._header_release

    def _apply_theme(self):
        if self.skin == "default":
            accent = "#00ffff"
            bg     = "rgba(8, 22, 48, 230)"
            hdr    = "rgba(0, 180, 200, 40)"
            div    = "#00aaaa"
        else:
            accent = "#ff69b4"
            bg     = "rgba(48, 8, 22, 230)"
            hdr    = "rgba(200, 0, 100, 40)"
            div    = "#cc3377"

        self.container.setStyleSheet(f"""
            QWidget#container {{
                background-color: {bg};
                border: 2px solid {accent};
                border-radius: 12px;
            }}
            QWidget#header {{
                background-color: {hdr};
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
            }}
            QLabel#title {{
                color: {accent};
                font-family: 'Courier New', monospace;
                font-size: 15px;
                font-weight: bold;
                background: transparent;
            }}
            QComboBox#filterBox {{
                background-color: rgba(0,0,0,120);
                color: {accent};
                border: 1px solid {accent};
                border-radius: 4px;
                font-family: 'Courier New', monospace;
                font-size: 12px;
                padding: 2px 6px;
            }}
            QComboBox#filterBox QAbstractItemView {{
                background-color: rgba(10,20,40,240);
                color: {accent};
                selection-background-color: rgba(0,180,200,80);
            }}
            QPushButton#headerBtn {{
                background-color: rgba(0,0,0,100);
                color: {accent};
                border: 1px solid {accent};
                border-radius: 5px;
                font-family: 'Courier New', monospace;
                font-size: 12px;
            }}
            QPushButton#headerBtn:hover {{
                background-color: {accent};
                color: black;
            }}
            QPushButton#closeBtn {{
                background-color: transparent;
                color: #ff4d4d;
                border: 1px solid #ff4d4d;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton#closeBtn:hover {{
                background-color: #ff4d4d;
                color: white;
            }}
            QFrame#divider {{
                background-color: {div};
            }}
            QTextEdit#logText {{
                background-color: transparent;
                color: #cccccc;
                font-family: 'Courier New', monospace;
                font-size: 12px;
                border: none;
                padding: 6px 10px;
            }}
            QScrollBar:vertical {{
                background: rgba(0,0,0,60);
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {accent};
                border-radius: 4px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QLabel#statusBar {{
                color: rgba(150,150,150,180);
                font-family: 'Courier New', monospace;
                font-size: 11px;
                background: transparent;
                padding-left: 10px;
            }}
        """)

    # --- Перетаскивание ---
    def _header_press(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPos() - self.frameGeometry().topLeft()

    def _header_move(self, e):
        if e.buttons() == Qt.LeftButton and self._drag_pos:
            self.move(e.globalPos() - self._drag_pos)

    def _header_release(self, e):
        self._drag_pos = None

    # --- Логика ---
    def _on_filter_changed(self, value):
        self.current_filter = value
        self._reload_all()

    def _reload_all(self):
        """Перерисовывает все записи с учётом фильтра."""
        self.log_text.clear()
        entries = logger.entries
        if self.current_filter != "ALL":
            entries = [e for e in entries if e["level"] == self.current_filter]
        for entry in entries:
            self._append_entry(entry)
        self._update_status()

    def _on_new_entry(self, entry):
        """Вызывается логгером при новой записи."""
        if not self.isVisible():
            return
        if self.current_filter != "ALL" and entry["level"] != self.current_filter:
            return
        self._append_entry(entry)
        self._update_status()

    def _append_entry(self, entry):
        color = self.LEVEL_COLORS.get(entry["level"], "#cccccc")
        # Форматируем строку с HTML-раскраской
        line = (
            f'<span style="color:#555555">[{entry["time"]}]</span> '
            f'<span style="color:{color};font-weight:bold">[{entry["level"]:7s}]</span> '
            f'<span style="color:#888888">[{entry["source"]}]</span> '
            f'<span style="color:#dddddd">{entry["message"].replace(chr(10), "<br>&nbsp;&nbsp;")}</span>'
        )
        self.log_text.append(line)
        # Прокрутка вниз
        self.log_text.moveCursor(QTextCursor.End)

    def _update_status(self):
        total = len(logger.entries)
        errors = sum(1 for e in logger.entries if e["level"] == "ERROR")
        warns  = sum(1 for e in logger.entries if e["level"] == "WARNING")
        self.status_bar.setText(
            f"  Total: {total}   Errors: {errors}   Warnings: {warns}"
        )

    def _copy_logs(self):
        lines = []
        entries = logger.entries
        if self.current_filter != "ALL":
            entries = [e for e in entries if e["level"] == self.current_filter]
        for e in entries:
            lines.append(f"[{e['time']}] [{e['level']}] [{e['source']}] {e['message']}")
        QApplication.clipboard().setText("\n".join(lines))
        self.status_bar.setText("  Copied to clipboard!")
        QTimer.singleShot(2000, self._update_status)

    def _clear_logs(self):
        logger.clear()
        self.log_text.clear()
        self._update_status()

    def update_skin(self, skin):
        self.skin = skin
        self._apply_theme()

    def closeEvent(self, event):
        logger.remove_listener(self._on_new_entry)
        event.accept()

    def hideEvent(self, event):
        logger.remove_listener(self._on_new_entry)
        super().hideEvent(event)

    def showEvent(self, event):
        # При показе — переподписываемся и обновляем
        if self._on_new_entry not in logger._listeners:
            logger.add_listener(self._on_new_entry)
        self._reload_all()
        super().showEvent(event)


# =============================================
# --- СИСТЕМА КОМАНД ЮКИ ---
# =============================================

class YukiCommands:
    """
    Обрабатывает команды, начинающиеся с 'юки'.
    Возвращает (handled: bool, response_text: str)
    """

    TRIGGERS = ["юки,", "юки"]

    # --- Ключевые слова для каждой команды ---
    MUSIC_KEYS     = ["включи музыку", "включи песню", "поставь музыку",
                      "поставь песню", "включи трек", "сыграй"]
    YOUTUBE_KEYS   = ["открой ютуб", "зайди на ютуб", "включи ютуб"]
    SITE_KEYS      = ["открой сайт", "зайди на", "открой страницу"]
    APP_KEYS       = ["открой программу", "запусти программу",
                      "открой приложение", "запусти приложение"]
    SHUTDOWN_KEYS  = ["выключи компьютер", "выключи пк", "выключи комп",
                      "выключи систему", "shut down"]
    RESTART_KEYS   = ["перезагрузи компьютер", "перезагрузи пк",
                      "перезапусти систему", "restart"]
    SLEEP_KEYS     = ["спящий режим", "усыпи компьютер", "сон"]
    VOLUME_UP_KEYS = ["громче", "увеличь громкость", "прибавь звук"]
    VOLUME_DOWN_KEYS = ["тише", "уменьши громкость", "убавь звук"]
    MUTE_KEYS      = ["выключи звук", "без звука", "тихо"]
    SCREENSHOT_KEYS = ["сделай скриншот", "скриншот", "снимок экрана"]
    NOTEPAD_KEYS   = ["открой блокнот", "запусти блокнот"]
    CALC_KEYS      = ["открой калькулятор", "запусти калькулятор", "калькулятор"]
    EXPLORER_KEYS  = ["открой проводник", "проводник", "мой компьютер"]
    SEARCH_KEYS    = ["найди в гугле", "загугли", "поищи"]
    TIME_KEYS      = ["который час", "сколько времени", "скажи время", "время"]
    DATE_KEYS      = ["какое сегодня число", "скажи дату", "дата", "какой день"]
    HELLO_KEYS     = ["привет", "здравствуй", "хей", "hi", "hello"]

    @classmethod
    def is_yuki_command(cls, text: str) -> bool:
        """Проверяет, начинается ли текст с обращения к Юки."""
        t = text.strip().lower()
        for trigger in cls.TRIGGERS:
            if t.startswith(trigger):
                return True
        return False

    @classmethod
    def extract_body(cls, text: str) -> str:
        """Убирает 'юки' в начале и возвращает остаток."""
        t = text.strip().lower()
        for trigger in ["юки,", "юки"]:
            if t.startswith(trigger):
                return t[len(trigger):].strip()
        return t

    # ---------- помощники ----------
    @staticmethod
    def _starts_with_any(text: str, keys: list) -> tuple:
        """Возвращает (True, suffix) если text начинается с одного из ключей."""
        for k in keys:
            if text.startswith(k):
                return True, text[len(k):].strip()
        return False, ""

    @staticmethod
    def _contains_any(text: str, keys: list) -> tuple:
        """Возвращает (True, keyword) если text содержит одно из ключевых слов."""
        for k in keys:
            if k in text:
                return True, k
        return False, ""

    # ---------- действия ----------
    @staticmethod
    def open_youtube_music(query: str):
        """Открывает YouTube с поиском и авто-кликает первый результат через selenium (если есть).
        Если selenium нет — просто открывает поиск в браузере."""
        search_url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(query)
        try:
            from selenium import webdriver
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.chrome.options import Options

            options = Options()
            options.add_argument("--start-maximized")
            # Не показываем "Chrome управляется автоматически"
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)

            driver = webdriver.Chrome(options=options)
            driver.get(search_url)

            # Ждём появления первого видео и кликаем
            wait = WebDriverWait(driver, 10)
            first_video = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "ytd-video-renderer a#video-title"))
            )
            first_video.click()
        except ImportError:
            # Selenium не установлен — просто открываем поиск
            webbrowser.open(search_url)
        except Exception:
            # Что-то пошло не так — открываем поиск
            webbrowser.open(search_url)

    @staticmethod
    def open_youtube():
        webbrowser.open("https://www.youtube.com")

    @staticmethod
    def open_website(url: str):
        if not url.startswith("http"):
            url = "https://" + url
        webbrowser.open(url)

    @staticmethod
    def search_google(query: str):
        url = "https://www.google.com/search?q=" + urllib.parse.quote(query)
        webbrowser.open(url)

    @staticmethod
    def shutdown_pc():
        subprocess.Popen(["shutdown", "/s", "/t", "5"])

    @staticmethod
    def restart_pc():
        subprocess.Popen(["shutdown", "/r", "/t", "5"])

    @staticmethod
    def sleep_pc():
        subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])

    @staticmethod
    def volume_up():
        try:
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from comtypes import CLSCTX_ALL
            import comtypes
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = interface.QueryInterface(IAudioEndpointVolume)
            current = volume.GetMasterVolumeLevelScalar()
            volume.SetMasterVolumeLevelScalar(min(1.0, current + 0.1), None)
        except Exception:
            # Fallback: нажать клавишу громкости через PowerShell
            subprocess.Popen(["powershell", "-c",
                "(New-Object -comObject WScript.Shell).SendKeys([char]175)"])

    @staticmethod
    def volume_down():
        try:
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from comtypes import CLSCTX_ALL
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = interface.QueryInterface(IAudioEndpointVolume)
            current = volume.GetMasterVolumeLevelScalar()
            volume.SetMasterVolumeLevelScalar(max(0.0, current - 0.1), None)
        except Exception:
            subprocess.Popen(["powershell", "-c",
                "(New-Object -comObject WScript.Shell).SendKeys([char]174)"])

    @staticmethod
    def mute():
        try:
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from comtypes import CLSCTX_ALL
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = interface.QueryInterface(IAudioEndpointVolume)
            current_mute = volume.GetMute()
            volume.SetMute(not current_mute, None)
        except Exception:
            subprocess.Popen(["powershell", "-c",
                "(New-Object -comObject WScript.Shell).SendKeys([char]173)"])

    @staticmethod
    def take_screenshot():
        try:
            import datetime
            pics = os.path.join(os.path.expanduser("~"), "Pictures")
            os.makedirs(pics, exist_ok=True)
            fname = os.path.join(pics, f"yuki_screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            # pyautogui
            import pyautogui
            img = pyautogui.screenshot()
            img.save(fname)
            return fname
        except ImportError:
            # Fallback через PowerShell
            subprocess.Popen(["powershell", "-c",
                "[System.Windows.Forms.SendKeys]::SendWait('%{PRTSC}')"])
            return None

    @staticmethod
    def open_app(name: str):
        """Пытается открыть программу по имени."""
        apps = {
            "блокнот": "notepad.exe",
            "notepad": "notepad.exe",
            "калькулятор": "calc.exe",
            "calculator": "calc.exe",
            "проводник": "explorer.exe",
            "explorer": "explorer.exe",
            "paint": "mspaint.exe",
            "пейнт": "mspaint.exe",
            "браузер": None,  # откроем дефолтный
            "хром": "chrome.exe",
            "chrome": "chrome.exe",
            "файрфокс": "firefox.exe",
            "firefox": "firefox.exe",
            "discord": "Discord.exe",
            "дискорд": "Discord.exe",
            "стим": "Steam.exe",
            "steam": "Steam.exe",
            "word": "WINWORD.EXE",
            "excel": "EXCEL.EXE",
        }
        exe = apps.get(name.lower())
        if exe:
            try:
                subprocess.Popen([exe])
                return True
            except FileNotFoundError:
                # Пробуем через start
                subprocess.Popen(["start", exe], shell=True)
                return True
        else:
            # Пробуем запустить напрямую
            try:
                subprocess.Popen([name], shell=True)
                return True
            except Exception:
                return False

    # ---------- главный обработчик ----------
    @classmethod
    def handle(cls, raw_text: str):
        """
        Главная точка входа.
        raw_text — полный текст пользователя.
        Возвращает (handled: bool, response_text: str)
        """
        if not cls.is_yuki_command(raw_text):
            return False, ""

        body = cls.extract_body(raw_text)

        # --- Приветствие ---
        ok, _ = cls._contains_any(body, cls.HELLO_KEYS)
        if ok:
            import random
            greets = [
                "Привет! Чем могу помочь? 😊",
                "Приветик! Я здесь! ✨",
                "О, привет! Что случилось? 🌸",
                "Здравствуй! Всегда рада тебя видеть! 💙",
            ]
            return True, random.choice(greets)

        # --- Время ---
        ok, _ = cls._contains_any(body, cls.TIME_KEYS)
        if ok:
            import datetime
            now = datetime.datetime.now().strftime("%H:%M")
            return True, f"Сейчас {now} ⏰"

        # --- Дата ---
        ok, _ = cls._contains_any(body, cls.DATE_KEYS)
        if ok:
            import datetime
            MONTHS = ["января","февраля","марта","апреля","мая","июня",
                      "июля","августа","сентября","октября","ноября","декабря"]
            d = datetime.datetime.now()
            return True, f"Сегодня {d.day} {MONTHS[d.month-1]} {d.year} года 📅"

        # --- Музыка на YouTube ---
        ok, suffix = cls._starts_with_any(body, cls.MUSIC_KEYS)
        if ok:
            if suffix:
                Thread(target=cls.open_youtube_music, args=(suffix,), daemon=True).start()
                return True, f"Включаю «{suffix}» на YouTube! 🎵"
            else:
                return True, "Что включить? Скажи название песни! 🎶"

        # --- Открыть YouTube ---
        ok, _ = cls._contains_any(body, cls.YOUTUBE_KEYS)
        if ok:
            Thread(target=cls.open_youtube, daemon=True).start()
            return True, "Открываю YouTube! 📺"

        # --- Поиск в гугле ---
        ok, kw = cls._starts_with_any(body, cls.SEARCH_KEYS)
        if ok:
            if suffix := body[body.index(kw) + len(kw):].strip() if kw in body else "":
                Thread(target=cls.search_google, args=(suffix,), daemon=True).start()
                return True, f"Ищу «{suffix}» в Google! 🔍"
            else:
                # Ещё раз через starts_with
                ok2, q = cls._starts_with_any(body, cls.SEARCH_KEYS)
                if q:
                    Thread(target=cls.search_google, args=(q,), daemon=True).start()
                    return True, f"Ищу «{q}» в Google! 🔍"
                return True, "Что найти в Google? 🔍"

        # --- Открыть сайт ---
        ok, suffix = cls._starts_with_any(body, cls.SITE_KEYS)
        if ok and suffix:
            Thread(target=cls.open_website, args=(suffix,), daemon=True).start()
            return True, f"Открываю {suffix}! 🌐"
        elif ok:
            return True, "Какой сайт открыть? 🌐"

        # --- Открыть приложение ---
        ok, suffix = cls._starts_with_any(body, cls.APP_KEYS)
        if ok:
            if suffix:
                result = cls.open_app(suffix)
                if result:
                    return True, f"Запускаю {suffix}! 💻"
                else:
                    return True, f"Не нашла программу «{suffix}» 😕"
            return True, "Какую программу открыть? 💻"

        # --- Блокнот ---
        ok, _ = cls._contains_any(body, cls.NOTEPAD_KEYS)
        if ok:
            Thread(target=lambda: subprocess.Popen(["notepad.exe"]), daemon=True).start()
            return True, "Открываю Блокнот! 📝"

        # --- Калькулятор ---
        ok, _ = cls._contains_any(body, cls.CALC_KEYS)
        if ok:
            Thread(target=lambda: subprocess.Popen(["calc.exe"]), daemon=True).start()
            return True, "Открываю Калькулятор! 🔢"

        # --- Проводник ---
        ok, _ = cls._contains_any(body, cls.EXPLORER_KEYS)
        if ok:
            Thread(target=lambda: subprocess.Popen(["explorer.exe"]), daemon=True).start()
            return True, "Открываю Проводник! 📁"

        # --- Скриншот ---
        ok, _ = cls._contains_any(body, cls.SCREENSHOT_KEYS)
        if ok:
            def do_screenshot():
                path = cls.take_screenshot()
                return path
            Thread(target=do_screenshot, daemon=True).start()
            return True, "Делаю скриншот! 📸"

        # --- Громкость ---
        ok, _ = cls._contains_any(body, cls.VOLUME_UP_KEYS)
        if ok:
            Thread(target=cls.volume_up, daemon=True).start()
            return True, "Делаю громче! 🔊"

        ok, _ = cls._contains_any(body, cls.VOLUME_DOWN_KEYS)
        if ok:
            Thread(target=cls.volume_down, daemon=True).start()
            return True, "Делаю тише! 🔉"

        ok, _ = cls._contains_any(body, cls.MUTE_KEYS)
        if ok:
            Thread(target=cls.mute, daemon=True).start()
            return True, "Переключаю звук! 🔇"

        # --- Выключить / перезагрузить / спящий режим ---
        ok, _ = cls._contains_any(body, cls.SHUTDOWN_KEYS)
        if ok:
            Thread(target=cls.shutdown_pc, daemon=True).start()
            return True, "Выключаю компьютер через 5 секунд... 🖥️"

        ok, _ = cls._contains_any(body, cls.RESTART_KEYS)
        if ok:
            Thread(target=cls.restart_pc, daemon=True).start()
            return True, "Перезагружаю компьютер через 5 секунд... 🔄"

        ok, _ = cls._contains_any(body, cls.SLEEP_KEYS)
        if ok:
            Thread(target=cls.sleep_pc, daemon=True).start()
            return True, "Перехожу в спящий режим... 😴"

        # Команда с 'юки', но неизвестная → передаём в ИИ
        return False, ""


# =============================================
# --- КОНЕЦ СИСТЕМЫ КОМАНД ---
# =============================================


# --- Класс мозга (работает в фоне) ---
class YukiBrain(QThread):
    reply_ready = pyqtSignal(str, str)
    error_occurred = pyqtSignal(str)

    def __init__(self, prompt, language="ru"):
        super().__init__()
        self.prompt = prompt
        self.language = language
        self.model = genai.GenerativeModel('gemini-2.5-flash')

    def run(self):
        try:
            logger.log("AI", "Gemini", f"Request: {self.prompt[:80]}")
            system_instruction = "Ты Юки, милая и умная ИИ-ассистентка. Отвечай кратко, дружелюбно и по делу."
            full_prompt = f"{system_instruction}\nПользователь: {self.prompt}"
            response = self.model.generate_content(full_prompt)
            ai_text = response.text.strip()
            logger.log("AI", "Gemini", f"Response: {ai_text[:80]}")
            audio_path = self.synthesize_audio(ai_text, self.language)
            if audio_path:
                self.reply_ready.emit(ai_text, audio_path)
            else:
                self.error_occurred.emit("Ошибка синтеза речи.")
        except Exception as e:
            tb = traceback.format_exc()
            logger.log("ERROR", "YukiBrain", f"{e}\n{tb}")
            self.error_occurred.emit(f"Ошибка: {str(e)}")

    def synthesize_audio(self, text, lang):
        try:
            if lang == "ja":
                return self.speak_voicevox(text)
            else:
                return self.speak_coqui(text, lang)
        except Exception as e:
            tb = traceback.format_exc()
            logger.log("ERROR", "TTS", f"{e}\n{tb}")
            return None

    def speak_coqui(self, text, lang):
        url = "http://91.205.196.207:5002/api/tts"
        voice_file = "voices/roxy.wav"
        speed = 1.1
        if lang == "en":
            voice_file = "voices/raiden.wav"
        elif lang == "fr":
            voice_file = "voices/french.wav"
            speed = 0.9

        payload = {"text": text, "language": lang, "speaker_wav": voice_file, "speed": speed}
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()

        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, "yuki_coqui.wav")
        with open(file_path, "wb") as f:
            f.write(response.content)
        return file_path

    def speak_voicevox(self, text):
        base_url = "http://91.205.196.207:50021"
        speaker = "1"
        query_res = requests.post(f"{base_url}/audio_query", params={"speaker": speaker, "text": text})
        query_res.raise_for_status()
        synth_res = requests.post(f"{base_url}/synthesis", params={"speaker": speaker}, json=query_res.json())
        synth_res.raise_for_status()

        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, "yuki_voicevox.wav")
        with open(file_path, "wb") as f:
            f.write(synth_res.content)
        return file_path

class AudioPlayerThread(QThread):
    finished_playing = pyqtSignal()

    def __init__(self, filepath):
        super().__init__()
        self.filepath = filepath

    def run(self):
        # Эта команда проигрывает WAV файл и ждет его окончания
        winsound.PlaySound(self.filepath, winsound.SND_FILENAME)
        # Когда звук закончился, отправляем сигнал
        self.finished_playing.emit()


# --- Класс красивого окна ввода ---
class ChatInputDialog(QDialog):
    def __init__(self, skin):
        super().__init__()
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)

        # Поле ввода текста
        self.input_field = QLineEdit(self)
        self.input_field.setPlaceholderText("Что скажешь?")
        self.input_field.setMinimumHeight(40)
        self.input_field.returnPressed.connect(self.accept) 

        # Кнопка отправки
        self.send_btn = QPushButton("➤", self)
        self.send_btn.setFixedSize(40, 40)
        self.send_btn.clicked.connect(self.accept)

        self.layout.addWidget(self.input_field)
        self.layout.addWidget(self.send_btn)

        self.apply_style(skin)
        
        # Автофокус: курсор сразу ставится в поле ввода при открытии
        self.input_field.setFocus()

    def apply_style(self, skin):
        if skin == 'default':
            main_color = "#00ffff"
            bg_color   = "rgba(0, 80, 120, 210)"   # насыщенный тёмно-голубой
            field_bg   = "rgba(0, 50, 90, 180)"
        else:
            main_color = "#ff69b4"
            bg_color   = "rgba(120, 0, 60, 210)"   # насыщенный тёмно-розовый
            field_bg   = "rgba(90, 0, 45, 180)"

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_color};
                border: 2px solid {main_color};
                border-radius: 15px;
            }}
            QLineEdit {{
                background-color: {field_bg};
                color: white;
                font-family: 'Courier New', monospace;
                font-size: 16px;
                border: 1px solid {main_color};
                border-radius: 8px;
                padding: 5px 10px;
            }}
            QPushButton {{
                background-color: transparent;
                color: {main_color};
                font-size: 20px;
                border: none;
                border-radius: 20px;
            }}
            QPushButton:hover {{
                background-color: {main_color};
                color: black;
            }}
        """)

    def get_text(self):
        return self.input_field.text()


# --- Класс голографического экрана ---
class HolographicScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(15, 15, 15, 15)
        
        self.label = QLabel("", self)
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignLeft | Qt.AlignTop) 
        self.label.setMinimumWidth(250)
        self.label.setMaximumWidth(550)
        self.layout.addWidget(self.label)
        
        self.glow_effect = QGraphicsDropShadowEffect(self)
        self.glow_effect.setBlurRadius(20)
        self.glow_effect.setOffset(0, 0)
        self.setGraphicsEffect(self.glow_effect)

        # Таймер для печатной машинки
        self.type_timer = QTimer(self)
        self.type_timer.timeout.connect(self.type_next_char)
        self.full_text = ""
        self.current_index = 0

        # Таймер для анимации ожидания
        self.loading_timer = QTimer(self)
        self.loading_timer.timeout.connect(self.animate_loading)
        self.dot_count = 0

        # Таймер для авто-скрытия (для команд без TTS)
        self.auto_hide_timer = QTimer(self)
        self.auto_hide_timer.setSingleShot(True)
        self.auto_hide_timer.timeout.connect(self.hide)

    def show_loading(self, skin, x, y):
        self.type_timer.stop()
        self.auto_hide_timer.stop()

        if skin == 'default':
            main_color = "#00ffff"
            bg_color   = "rgba(0, 80, 120, 220)"   # тёмно-голубой
        else:
            main_color = "#ff69b4"
            bg_color   = "rgba(120, 0, 60, 220)"   # тёмно-розовый

        self.setStyleSheet(f"""
            QWidget {{ background-color: {bg_color}; border: 2px solid {main_color}; border-radius: 10px; }}
            QLabel  {{ color: {main_color}; font-family: 'Courier New', monospace; font-size: 28px; font-weight: bold; border: none; background: transparent; }}
        """)
        self.glow_effect.setColor(QColor(main_color))

        self.setMinimumSize(0, 0)
        self.setMaximumSize(16777215, 16777215)
        
        self.label.setText("Думаю")
        self.adjustSize()
        
        self.move(x, y)
        self.show()

        self.dot_count = 0
        self.loading_timer.start(400)

    def animate_loading(self):
        self.dot_count = (self.dot_count + 1) % 4
        dots = "." * self.dot_count
        self.label.setText(f"Думаю{dots}")

    def show_message(self, text, skin, x, y, auto_hide_ms=0):
        """
        Показывает сообщение.
        auto_hide_ms > 0 — автоматически скрыть через N миллисекунд (для команд без TTS).
        """
        self.loading_timer.stop()
        self.type_timer.stop()
        self.auto_hide_timer.stop()

        if skin == 'default':
            main_color = "#00ffff"
            bg_color   = "rgba(0, 80, 120, 220)"   # тёмно-голубой
        else:
            main_color = "#ff69b4"
            bg_color   = "rgba(120, 0, 60, 220)"   # тёмно-розовый

        self.setStyleSheet(f"""
            QWidget {{ background-color: {bg_color}; border: 2px solid {main_color}; border-radius: 10px; }}
            QLabel  {{ color: {main_color}; font-family: 'Courier New', monospace; font-size: 28px; font-weight: bold; border: none; background: transparent; }}
        """)
        self.glow_effect.setColor(QColor(main_color))

        self.setMinimumSize(0, 0)
        self.setMaximumSize(16777215, 16777215)

        self.label.setText(text)
        self.adjustSize()
        
        target_width = self.width()
        target_height = self.height()
        self.setFixedSize(target_width, target_height)

        self.full_text = text
        self.label.setText("")
        self.current_index = 0

        self.move(x, y)
        self.show()

        self.type_timer.start(35)

        if auto_hide_ms > 0:
            self.auto_hide_timer.start(auto_hide_ms)

    def type_next_char(self):
        if self.current_index < len(self.full_text):
            current_text = self.label.text()
            self.label.setText(current_text + self.full_text[self.current_index])
            self.current_index += 1
        else:
            self.type_timer.stop()

# --- Класс кругового меню ---
class RadialMenu(QWidget):
    def __init__(self, parent_yuki):
        super().__init__()
        self.yuki = parent_yuki
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(300, 300)
        self.animations = []

        self.skin_btn = self.create_button("Скин", "#ffb6c1", self.change_skin)
        self.close_btn = self.create_button("Выход", "#ff6b6b", self.close_app)
        self.chibi_btn = self.create_button("Чиби", "#87ceeb", self.toggle_chibi)
        self.chat_btn = self.create_button("Чат", "#a8ff78", self.yuki.ask_yuki)
        self.logs_btn = self.create_button("Логи", "#ffa07a", self.yuki.show_logs)

    def create_button(self, text, color, connect_func):
        btn = QPushButton(text, self)
        btn.setFixedSize(60, 60)
        btn.setStyleSheet(f"""
            QPushButton {{ background-color: rgba(30, 30, 30, 200); color: white; border-radius: 30px; border: 2px solid {color}; font-weight: bold; }}
            QPushButton:hover {{ background-color: {color}; color: black; }}
        """)
        btn.clicked.connect(connect_func)
        return btn

    def show_around(self, x, y):
        self.move(x - self.width() // 2, y - self.height() // 2)
        center_pos = QPoint(self.width() // 2 - 30, self.height() // 2 - 30)

        # 5 кнопок по кругу
        pos_skin  = QPoint(self.width() // 2 + 70, self.height() // 2 - 30)   # право
        pos_close = QPoint(self.width() // 2 - 100, self.height() // 2 - 30)  # лево
        pos_chibi = QPoint(self.width() // 2 - 30, self.height() // 2 - 100)  # верх
        pos_chat  = QPoint(self.width() // 2 - 30, self.height() // 2 + 50)   # низ
        pos_logs  = QPoint(self.width() // 2 + 50, self.height() // 2 + 40)   # право-низ

        self.animate_btn(self.skin_btn,  center_pos, pos_skin)
        self.animate_btn(self.close_btn, center_pos, pos_close)
        self.animate_btn(self.chibi_btn, center_pos, pos_chibi)
        self.animate_btn(self.chat_btn,  center_pos, pos_chat)
        self.animate_btn(self.logs_btn,  center_pos, pos_logs)

        self.show()

    def animate_btn(self, btn, start, end):
        anim = QPropertyAnimation(btn, b"pos")
        anim.setDuration(400)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setEasingCurve(QEasingCurve.OutBack)
        self.animations.append(anim)
        anim.start()

    def change_skin(self):
        self.yuki.current_skin = 'alt_skin' if self.yuki.current_skin == 'default' else 'default'
        self.yuki.update_image()
        self.yuki.log_window.update_skin(self.yuki.current_skin)
        self.hide()

    def toggle_chibi(self):
        self.yuki.is_chibi = not self.yuki.is_chibi
        self.yuki.update_image()
        self.hide()

    def close_app(self):
        self.yuki.save_settings()
        QApplication.quit()

    def show_logs(self):
        self.hide()
        self.yuki.show_logs()


# --- Основной класс Юки ---
class YukiAssistant(QWidget):
    def __init__(self):
        super().__init__()
        self.settings_file = 'yuki_settings.json'
        
        self.load_settings()
        self.menu = RadialMenu(self)
        self.holo_screen = HolographicScreen()
        self.log_window = LogWindow(self.current_skin)

        self.initUI()
        self.init_tray()
        logger.log("INFO", "UI", "Yuki UI initialized")

    def ask_yuki(self):
        self.menu.hide()
        
        dialog = ChatInputDialog(self.current_skin)
        
        dialog_x = self.x() + self.width() // 2 - 125
        dialog_y = self.y() + self.height() + 10
        dialog.move(dialog_x, dialog_y)
        
        if dialog.exec_() == QDialog.Accepted:
            text = dialog.get_text()
            if text.strip():
                self._process_input(text.strip())

    def show_logs(self):
        """Открывает окно логов."""
        self.log_window.update_skin(self.current_skin)
        self.log_window.show()
        self.log_window.raise_()
        self.log_window.activateWindow()

    def _process_input(self, text: str):
        """Обрабатывает ввод: сначала проверяет команды, потом отправляет в ИИ."""
        screen_x = self.x() + self.width() + 10
        screen_y = self.y() + 20

        logger.log("INFO", "Input", f"User: {text}")

        # --- Проверяем команды Юки ---
        handled, response = YukiCommands.handle(text)
        if handled:
            logger.log("COMMAND", "CMD", f"Handled: {text} -> {response}")
            self.holo_screen.show_message(
                response, self.current_skin,
                screen_x, screen_y,
                auto_hide_ms=4000
            )
            return

        # --- Если команда не распознана — отдаём в ИИ ---
        self.holo_screen.show_loading(self.current_skin, screen_x, screen_y)

        self.brain = YukiBrain(prompt=text, language="ru")
        self.brain.reply_ready.connect(self.on_yuki_reply)
        self.brain.error_occurred.connect(self.on_yuki_error)
        self.brain.start()

    def on_yuki_error(self, error_msg):
        logger.log("ERROR", "YukiReply", error_msg)
        screen_x = self.x() + self.width() + 10
        screen_y = self.y() + 20
        self.holo_screen.show_message("Ой, ошибка сети... 😵", self.current_skin, screen_x, screen_y)

    def on_yuki_reply(self, text, audio_path):
        screen_x = self.x() + self.width() + 10
        screen_y = self.y() + 20
        self.holo_screen.show_message(text, self.current_skin, screen_x, screen_y)
        
        self.audio_thread = AudioPlayerThread(audio_path)
        self.audio_thread.finished_playing.connect(self.holo_screen.hide)
        self.audio_thread.start()

    def on_audio_state_changed(self):
        if not self.audio_effect.isPlaying():
            self.holo_screen.hide()

    def load_settings(self):
        try:
            with open(self.settings_file, 'r') as f:
                data = json.load(f)
                self.current_skin = data.get('skin', 'default')
                self.is_chibi = data.get('chibi', False)
                self.start_x = data.get('x', 100)
                self.start_y = data.get('y', 100)
        except (FileNotFoundError, json.JSONDecodeError):
            self.current_skin = 'default'
            self.is_chibi = False
            self.start_x = 100
            self.start_y = 100

    def save_settings(self):
        data = {'skin': self.current_skin, 'chibi': self.is_chibi, 'x': self.x(), 'y': self.y()}
        with open(self.settings_file, 'w') as f:
            json.dump(data, f)

    def init_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        if os.path.exists('yuki.png'):
            self.tray_icon.setIcon(QIcon('yuki.png')) 
        else:
            self.tray_icon.setIcon(QApplication.style().standardIcon(QApplication.style().SP_ComputerIcon))
        
        tray_menu = QMenu()
        show_action = QAction("Показать Юки", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)
        
        quit_action = QAction("Выход", self)
        quit_action.triggered.connect(self.menu.close_app)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def initUI(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.label = QLabel(self)
        self.update_image()
        self.move(self.start_x, self.start_y)
        self.oldPos = self.pos()

    def update_image(self):
        if self.current_skin == 'default':
            filename = 'yuki_chibi.png' if self.is_chibi else 'yuki.png'
        else:
            filename = 'yuki_skin_chibi.png' if self.is_chibi else 'yuki_skin.png'
        self.load_image(filename)

    def load_image(self, filename):
        if not os.path.exists(filename):
            print(f"ВНИМАНИЕ: Файл {filename} не найден!")
            return
            
        try:
            pixmap = QPixmap(filename)
            base_scale = 3 
            new_width = max(1, pixmap.width() // base_scale)
            new_height = max(1, pixmap.height() // base_scale)

            if self.is_chibi:
                chibi_scale = 2
                new_width = max(1, new_width // chibi_scale)
                new_height = max(1, new_height // chibi_scale)
                
            pixmap = pixmap.scaled(new_width, new_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.label.setPixmap(pixmap)
            self.label.resize(pixmap.width(), pixmap.height())
            self.resize(pixmap.width(), pixmap.height())
        except Exception as e:
            print(f"Ошибка загрузки {filename}, {e}")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.oldPos = event.globalPos()
            self.menu.hide()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            delta = event.globalPos() - self.oldPos
            if delta.manhattanLength() > 3:
                self.move(self.x() + delta.x(), self.y() + delta.y())
                if self.holo_screen.isVisible():
                    self.holo_screen.move(self.x() + self.width() + 10, self.y() + 20)
                self.oldPos = event.globalPos()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.RightButton:
            center_x = self.x() + self.width() // 2
            center_y = self.y() + self.height() // 2
            self.menu.show_around(center_x, center_y)
        elif event.button() == Qt.LeftButton:
            self.save_settings()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    QApplication.setQuitOnLastWindowClosed(False)
    yuki = YukiAssistant()
    yuki.show()
    sys.exit(app.exec_())
