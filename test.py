class WindowTracker(QThread):
    def run(self):
        # Միանում ենք Windows-ի համակարգային API-ին՝ պատուհանների հետ աշխատելու համար
        user32 = ctypes.windll.user32

        while self._running:
            self.msleep(150)  # 150 մվ դադար՝ պրոցեսորը չծանրաբեռնելու համար

            # Ստուգում ենք՝ արդյոք պատուհանը գոյություն ունի և տեսանելի է էկրանին
            if not user32.IsWindow(self.hwnd) or not user32.IsWindowVisible(self.hwnd):
                self.window_closed.emit()  # Ազդանշան՝ պատուհանը փակված է
                return

            # Ստանում ենք պատուհանի ընթացիկ կոորդինատները (սահմանները)
            r = get_hwnd_rect(self.hwnd)
            if r is None:SpeechThread
                self.window_closed.emit()
                return

            l, t, ri, b = r  # Առանձնացնում ենք կոորդինատները՝ left, top, right, bottom

            # Հաշվարկում ենք նոր դիրքը և ուղարկում ազդանշան UI-ը թարմացնելու համար
            x, y = self._calc_pos(l, t, ri, b)
            self.position_changed.emit(x, y)


            Д