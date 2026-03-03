import os
import sys
import site
import tempfile
import requests
import json
import warnings
import winsound


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
                             QGraphicsDropShadowEffect, QDialog, QHBoxLayout, QLineEdit)
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint, QThread, pyqtSignal, QUrl, QTimer
from PyQt5.QtGui import QPixmap, QIcon, QColor, QFont
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint, QThread, pyqtSignal, QUrl
from PyQt5.QtMultimedia import QSoundEffect

# --- НАСТРОЙКА GEMINI ---
# Вставь сюда свой ключ!
genai.configure(api_key="AIzaSyDPCxSR4u4bNA4aB3Sc_JllH5yFrWuGPhI")

# --- Класс мозга (работает в фоне) ---
class YukiBrain(QThread):
    reply_ready = pyqtSignal(str, str)
    error_occurred = pyqtSignal(str)

    def __init__(self, prompt, language="ru"):
        super().__init__()
        self.prompt = prompt
        self.language = language
        self.model = genai.GenerativeModel('gemini-3-flash-preview')

    def run(self):
        try:
            system_instruction = "Ты Юки, милая и умная ИИ-ассистентка. Отвечай кратко, дружелюбно и по делу."
            full_prompt = f"{system_instruction}\nПользователь: {self.prompt}"
            response = self.model.generate_content(full_prompt)
            ai_text = response.text.strip()
            audio_path = self.synthesize_audio(ai_text, self.language)
            if audio_path:
                self.reply_ready.emit(ai_text, audio_path)
            else:
                self.error_occurred.emit("Ошибка синтеза речи.")
        except Exception as e:
            self.error_occurred.emit(f"Ошибка: {str(e)}")

    def synthesize_audio(self, text, lang):
        try:
            if lang == "ja":
                return self.speak_voicevox(text)
            else:
                return self.speak_coqui(text, lang)
        except Exception as e:
            print(f"TTS Error: {e}")
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
        self.input_field.setMinimumHeight(40) # <--- ДЕЛАЕМ ПОЛЕ ТОЛЩЕ
        self.input_field.returnPressed.connect(self.accept) 

        # Кнопка отправки
        self.send_btn = QPushButton("➤", self)
        self.send_btn.setFixedSize(40, 40) # <--- Чуть увеличили кнопку для пропорций
        self.send_btn.clicked.connect(self.accept)

        self.layout.addWidget(self.input_field)
        self.layout.addWidget(self.send_btn)

        self.apply_style(skin)
        
        # <--- АВТОФОКУС: курсор сразу ставится в поле ввода при открытии
        self.input_field.setFocus()

    def apply_style(self, skin):
        if skin == 'default':
            main_color = "#00ffff" # Голубой
            bg_color = "rgba(10, 30, 60, 150)" 
        else:
            main_color = "#ff69b4" # Розовый
            bg_color = "rgba(60, 10, 30, 150)" 

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_color};
                border: 2px solid {main_color};
                border-radius: 15px;
            }}
            QLineEdit {{
                background-color: transparent;
                color: white;
                font-family: 'Courier New', monospace;
                font-size: 16px; /* <--- Увеличили шрифт для удобства */
                border: none;
                padding: 5px 10px; /* <--- Добавили внутренние отступы */
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
        self.label.setMinimumWidth(200)
        self.label.setMaximumWidth(350)
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

        # --- НОВОЕ: Таймер для анимации ожидания ---
        self.loading_timer = QTimer(self)
        self.loading_timer.timeout.connect(self.animate_loading)
        self.dot_count = 0

    def show_loading(self, skin, x, y):
        # Останавливаем печать, если она шла
        self.type_timer.stop()
        
        if skin == 'default':
            main_color = "#00ffff"
            bg_color = "rgba(10, 30, 60, 150)"
        else:
            main_color = "#ff69b4"
            bg_color = "rgba(60, 10, 30, 150)"

        self.setStyleSheet(f"""
            QWidget {{ background-color: {bg_color}; border: 2px solid {main_color}; border-radius: 10px; }}
            QLabel {{ color: {main_color}; font-family: 'Courier New', monospace; font-size: 14px; font-weight: bold; border: none; background: transparent; }}
        """)
        self.glow_effect.setColor(QColor(main_color))

        # Снимаем фиксацию размера
        self.setMinimumSize(0, 0)
        self.setMaximumSize(16777215, 16777215)
        
        self.label.setText("Думаю")
        self.adjustSize()
        
        self.move(x, y)
        self.show()

        # Запускаем анимацию мигающих точек (каждые 400 мс)
        self.dot_count = 0
        self.loading_timer.start(400)

    def animate_loading(self):
        # Добавляем от 0 до 3 точек
        self.dot_count = (self.dot_count + 1) % 4
        dots = "." * self.dot_count
        self.label.setText(f"Думаю{dots}")

    def show_message(self, text, skin, x, y):
        # --- НОВОЕ: Останавливаем анимацию ожидания ---
        self.loading_timer.stop()
        self.type_timer.stop()

        if skin == 'default':
            main_color = "#00ffff"
            bg_color = "rgba(10, 30, 60, 150)"
        else:
            main_color = "#ff69b4"
            bg_color = "rgba(60, 10, 30, 150)"

        self.setStyleSheet(f"""
            QWidget {{ background-color: {bg_color}; border: 2px solid {main_color}; border-radius: 10px; }}
            QLabel {{ color: {main_color}; font-family: 'Courier New', monospace; font-size: 14px; font-weight: bold; border: none; background: transparent; }}
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
        
        pos_skin = QPoint(self.width() // 2 + 30, self.height() // 2 - 30)  
        pos_close = QPoint(self.width() // 2 - 90, self.height() // 2 - 30) 
        pos_chibi = QPoint(self.width() // 2 - 30, self.height() // 2 - 90) 
        pos_chat = QPoint(self.width() // 2 - 30, self.height() // 2 + 30)  

        self.animate_btn(self.skin_btn, center_pos, pos_skin)
        self.animate_btn(self.close_btn, center_pos, pos_close)
        self.animate_btn(self.chibi_btn, center_pos, pos_chibi)
        self.animate_btn(self.chat_btn, center_pos, pos_chat)

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
        self.hide()

    def toggle_chibi(self):
        self.yuki.is_chibi = not self.yuki.is_chibi
        self.yuki.update_image()
        self.hide()

    def close_app(self):
        self.yuki.save_settings()
        QApplication.quit()


# --- Основной класс Юки ---
class YukiAssistant(QWidget):
    def __init__(self):
        super().__init__()
        self.settings_file = 'yuki_settings.json'
        
        self.load_settings()
        self.menu = RadialMenu(self)
        self.holo_screen = HolographicScreen()

        self.initUI()
        self.init_tray()

    def ask_yuki(self):
        self.menu.hide()
        
        dialog = ChatInputDialog(self.current_skin)
        
        dialog_x = self.x() + self.width() // 2 - 125
        dialog_y = self.y() + self.height() + 10
        dialog.move(dialog_x, dialog_y)
        
        if dialog.exec_() == QDialog.Accepted:
            text = dialog.get_text()
            if text.strip():
                # --- НОВОЕ: Запускаем анимацию "Думаю..." ---
                screen_x = self.x() + self.width() + 10
                screen_y = self.y() + 20
                self.holo_screen.show_loading(self.current_skin, screen_x, screen_y)
                
                # Запускаем генерацию ответа
                self.brain = YukiBrain(prompt=text, language="ru")
                self.brain.reply_ready.connect(self.on_yuki_reply)
                self.brain.error_occurred.connect(self.on_yuki_error)
                self.brain.start()

    def on_yuki_error(self, error_msg):
        print(error_msg)
        # Если произошла ошибка (нет интернета и т.д.), выводим её на экран
        screen_x = self.x() + self.width() + 10
        screen_y = self.y() + 20
        self.holo_screen.show_message("Ой, ошибка сети... 😵", self.current_skin, screen_x, screen_y)

    def on_yuki_reply(self, text, audio_path):
        screen_x = self.x() + self.width() + 10
        screen_y = self.y() + 20
        self.holo_screen.show_message(text, self.current_skin, screen_x, screen_y)
        
        # Запускаем воспроизведение звука через наш новый поток
        self.audio_thread = AudioPlayerThread(audio_path)
        # Когда звук закончится, прячем голографический экран
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