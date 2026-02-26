import os
import sys

# Насильно заставляем Windows искать плагины там, где нужно
import site

paths = site.getsitepackages()
for p in paths:
    qt_path = os.path.join(p, 'PyQt5', 'Qt5', 'plugins', 'platforms')
    if os.path.exists(qt_path):
        os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = qt_path
        break

# И ТОЛЬКО ПОСЛЕ ЭТОГО импортируем PyQt5 и всё остальное
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QPushButton
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt


# --- Класс нашего кругового меню ---
class RadialMenu(QWidget):
    def __init__(self, parent_yuki):
        super().__init__()
        self.yuki = parent_yuki

        # Магия здесь: Qt.Popup заставляет окно закрываться при клике в любое место мимо него!
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(300, 300)

        # --- Кнопка скина ---
        self.skin_btn = QPushButton("Скин", self)
        self.skin_btn.setFixedSize(60, 60)
        self.skin_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(30, 30, 30, 200);
                color: white; border-radius: 30px; border: 2px solid #ffb6c1; font-weight: bold;
            }
            QPushButton:hover { background-color: rgba(255, 182, 193, 200); color: black; }
        """)
        self.skin_btn.clicked.connect(self.change_skin)

        # --- Кнопка выхода (Новая) ---
        self.close_btn = QPushButton("Выход", self)
        self.close_btn.setFixedSize(60, 60)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(30, 30, 30, 200);
                color: white; border-radius: 30px; border: 2px solid #ff6b6b; font-weight: bold;
            }
            QPushButton:hover { background-color: rgba(255, 107, 107, 200); color: white; }
        """)
        self.close_btn.clicked.connect(self.close_app)

    def show_around(self, x, y):
        self.move(x - self.width() // 2, y - self.height() // 2)

        # Ставим кнопку скина чуть правее
        self.skin_btn.move(self.width() // 2 + 30, self.height() // 2 - 30)

        # Ставим кнопку выхода чуть левее (для симметрии)
        self.close_btn.move(self.width() // 2 - 90, self.height() // 2 - 30)

        self.show()

    def change_skin(self):
        # Меняем скин туда-обратно
        if self.yuki.current_skin == 'default':
            self.yuki.load_image('yuki_skin.png')
            self.yuki.current_skin = 'alt_skin'
        else:
            self.yuki.load_image('yuki.png')
            self.yuki.current_skin = 'default'

        self.hide()

    def close_app(self):
        # Эта команда полностью завершает работу программы
        QApplication.quit()


# --- Основной класс Юки ---
class YukiAssistant(QWidget):
    def __init__(self):
        super().__init__()
        self.current_skin = 'default'
        self.menu = RadialMenu(self)
        self.initUI()

    def initUI(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.label = QLabel(self)
        self.load_image('yuki.png')

        self.oldPos = self.pos()

    def load_image(self, filename):
        try:
            pixmap = QPixmap(filename)
            new_width = pixmap.width() // 3
            new_height = pixmap.height() // 3
            pixmap = pixmap.scaled(new_width, new_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.label.setPixmap(pixmap)
            self.label.resize(pixmap.width(), pixmap.height())
            self.resize(pixmap.width(), pixmap.height())
        except Exception as e:
            print(f"Ошибка загрузки {filename}")

    def mousePressEvent(self, event):
        # Левая кнопка закрывает меню (если оно открыто) и готовит Юки к перетаскиванию
        if event.button() == Qt.LeftButton:
            self.oldPos = event.globalPos()
            self.menu.hide()

    def mouseMoveEvent(self, event):
        # Перетаскиваем Юки только левой кнопкой мыши
        if event.buttons() == Qt.LeftButton:
            delta = event.globalPos() - self.oldPos
            if delta.manhattanLength() > 3:
                self.move(self.x() + delta.x(), self.y() + delta.y())
                self.oldPos = event.globalPos()

    def mouseReleaseEvent(self, event):
        # Отпускаем правую кнопку мыши -> открывается меню
        if event.button() == Qt.RightButton:
            center_x = self.x() + self.width() // 2
            center_y = self.y() + self.height() // 2
            self.menu.show_around(center_x, center_y)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    yuki = YukiAssistant()
    yuki.show()
    sys.exit(app.exec_())