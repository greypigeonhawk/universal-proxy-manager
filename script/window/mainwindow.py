import os,random,asyncio,sys,re,platform
from PyQt5.QtWidgets import QMainWindow, QWidget,QAbstractItemView,QHeaderView,QApplication,QSystemTrayIcon
from PyQt5.QtWidgets import QMenu, QAction
from PyQt5.QtGui import QPainter, QMovie, QFont,QPainterPath, QRegion,QPixmap,QIcon
from PyQt5.QtCore import Qt,QTimer,pyqtSignal,QTranslator,QObject,QEvent,QPropertyAnimation, QEasingCurve,QPoint,QRectF
from pathlib import Path
from script.ui.proxy_ui import Ui_MainWindow
from script.utils.util_manager import utils,TerminalCaptureHelper
from script.utils.util_web import Toast
from script.module.app_sys import app_system
from script.module.tool_sys import tool_system
from script.module.func_sys import func_system
from script.module.web_sys import web_system
from script.module.editor_sys import editor_system

current_os = platform.system()

class HoverWatcher(QObject):

    def __init__(self, parent, callback):
        super().__init__(parent)
        self.callback = callback

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Enter:
            self.callback(True)
        elif event.type() == QEvent.Leave:
            self.callback(False)
        return super().eventFilter(obj, event)

@utils.decorate_all_methods(utils.show_error_messagebox)
class MainWindow(QMainWindow):

    main_signal = pyqtSignal(str)

    # init issues

    def __init__(self, data=None):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.ui.setupUi(self)
        self.load_qss(self.app)
        self.apps = app_system(self)
        self.tool = tool_system(self)
        self.func = func_system(self)
        self.web = web_system(self)
        self.edit = editor_system(self)

        self.translator = QTranslator(self)
        self.current_lang = "en"
        self.translation_files = {"en": "localization/en.qm","zh": "localization/zh_CN.qm"}

        self.current_background = None
        self.terminal_background = 0
        self.dark_back = True
        self._is_moving = False
        self.fixed_window = True
        self._start_pos = QPoint(0, 0)
        self.gif_background = False
        self.renew_background = True
        self.config = {}

        self.terminal = TerminalCaptureHelper(self.ui.textBrowser)

        self.init_func()
    
    def init_func(self, data=None):
        self.init_ui()
        self.init_signals()
        self.apps.load_app()
        self.tool.load_tool()
        self.tool.load_ip()
        self.web.load_favorite()
        self.web.load_html() 
        self.trim_timer = QTimer(self)
        self.trim_timer.timeout.connect(lambda: (
            self.trim_textbrowser_lines(self.ui.textBrowser_bottom,400),
            self.trim_textbrowser_lines(self.ui.textBrowser,150)
        ))
        self.trim_timer.start(60 * 1000)
        self.func.load_state()
        
    def init_ui(self, data=None):
        font = QFont()
        font.setFamily("Microsoft YaHei UI, SimHei, WenQuanYi Micro Hei, Heiti TC,Segoe UI Emoji")
        font.setPointSize(9)
        self.setWindowOpacity(0.95)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.ui.textBrowser.setFont(font)
        self.movie = None
        self.ui.frame_auto.hide()
        self.ui.frame_edit.hide()
        self.ui.frame_ip.hide()
        self.ui.frame_spy.hide()
        self.ui.frame_tools.hide()
        self.ui.frame_test.hide()
        self.ui.frame_setting.hide()
        if current_os == 'Windows':
            # self.ui.checkbox_global_os.hide()
            self.ui.pushButton_auto_appimage.hide()
        self.background_set()
        self.wallpaper_timer()
        self.init_bar_animation()
        self.init_tray()
        self.can_hide = False
        QTimer.singleShot(10000, lambda: setattr(self, 'can_hide', True))

    def init_signals(self, data=None):
        self.apps.app_signal.connect(self.tool.tool_receiver)
        self.tool.tool_signal.connect(self.apps.app_receiver)
        self.apps.app_signal.connect(self.func.func_receiver)
        self.apps.app_signal.connect(self.web.web_receiver)
        
        self.ui.pushButton_leftbar_app.clicked.connect(lambda: self.toggle_module(self.ui.frame_app))
        self.ui.pushButton_leftbar_auto.clicked.connect(lambda: self.toggle_module(self.ui.frame_auto))
        self.ui.pushButton_leftbar_edit.clicked.connect(lambda: self.toggle_module(self.ui.frame_edit))
        self.ui.pushButton_leftbar_ip.clicked.connect(lambda: self.toggle_module(self.ui.frame_ip))
        self.ui.pushButton_leftbar_spy.clicked.connect(lambda: self.toggle_module(self.ui.frame_spy))
        self.ui.pushButton_leftbar_tool.clicked.connect(lambda: self.toggle_module(self.ui.frame_tools))
        self.ui.topbar_subtract.clicked.connect(lambda: self.toggle_module(self.ui.leftbar))
        self.ui.topbar_subtract.clicked.connect(lambda: self.toggle_module(self.ui.navbar))
        self.ui.pushButton_leftbar_test.clicked.connect(lambda: self.toggle_module(self.ui.frame_test))
        self.ui.pushButton_leftbar_setting.clicked.connect(lambda: self.toggle_module(self.ui.frame_setting))

        self.ui.topbar_theme.clicked.connect(self.background_set)
        self.ui.topbar_video.clicked.connect(self.animation_set)
        self.ui.horizontalSlider_spy.valueChanged.connect(self.wallpaper_timer)
        self.ui.checkBox_set_image.toggled.connect(lambda checked: self.stop_wallpaper_timer())
        self.ui.checkBox_set_image.toggled.connect(lambda checked: self.func.write_state())

        self.ui.terminal_down.clicked.connect(lambda: self.terminal_move(0))
        self.ui.terminal_up.clicked.connect(lambda: self.terminal_move(1))
        self.ui.terminal_minus.clicked.connect(lambda: self.terminal_fontsize(0))
        self.ui.terminal_plus.clicked.connect(lambda: self.terminal_fontsize(1))
        self.ui.pushButton_leftbar_bars.clicked.connect(self.toggle_bars)

        self.ui.radioButton_terminal.toggled.connect(lambda checked: self.ui.textBrowser_bottom.setFixedHeight(0 if checked else 100))
        self.ui.terminal_theme.clicked.connect(self.terminal_theme)
        self.ui.topbar_language.clicked.connect(self.toggle_language)
        self.ui.topbar_bright.clicked.connect(self.toggle_theme)
        self.ui.checkBox_set_start.toggled.connect(lambda checked: self.set_autostart(1) if checked else self.set_autostart(0))
        self.ui.checkBox_set_start.toggled.connect(lambda checked: self.func.write_state())
        self.ui.checkBox_set_hide.toggled.connect(lambda checked: self.func.write_state())
        self.ui.checkBox_set_proxy.toggled.connect(lambda checked: self.func.write_state())
        self.ui.checkBox_set_app.toggled.connect(lambda checked: self.func.write_state())
        self.ui.checkBox_set_global.toggled.connect(lambda checked: self.func.write_state())
        self.ui.checkBox_auto_sysproxy.toggled.connect(lambda checked: self.func.write_state())
        self.ui.checkBox_auto_http.toggled.connect(lambda checked: self.func.write_state())
        self.ui.checkBox_app_auto.toggled.connect(lambda checked: self.func.write_state())
        self.ui.checkBox_system.toggled.connect(lambda checked: self.func.write_state())
        self.ui.checkBox_http_socket.toggled.connect(lambda checked: self.func.write_state())

        self.ui.topbar_close.clicked.connect(self.close)
        self.ui.topbar_min.clicked.connect(self.showMinimized)
        self.ui.topbar_max.clicked.connect(self.max_window)

        self.ui.btn_web_fav.clicked.connect(self.web.add_favorite)
        self.ui.comboBox_web.currentIndexChanged.connect(self.web.open_favorite)
        self.ui.btn_web_clear.clicked.connect(self.web.delete_favorite)
        
        self.apps.app_ui_signal()
        self.tool.tool_ui_signal()
        self.web.web_ui_signal()
        self.func.func_ui_signals()
        self.edit.editor_ui_signals()
        self.create_tab = lambda web_view: self.web.handle_new_tab_from_view(web_view)

        self.ui.pushButton_test.clicked.connect(
            lambda: asyncio.create_task(self.func.start_test())
        )

    # Rewrite funcs

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.ui.gif_label.setGeometry(0, 0, self.width(), self.height())
        w = self.width()
        h = self.height()
        x = 0
        y = 0
        self.ui.frame_main.setGeometry(int(x), int(y), int(w), int(h))

    def paintEvent(self, event):
        if hasattr(self, 'pixmap') and not self.pixmap.isNull():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            painter.drawPixmap(self.rect(), self.pixmap)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.ui.topbar.underMouse():
            self._is_moving = True
            self._start_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event) 

    def mouseMoveEvent(self, event):
        if self._is_moving:
            self.move(event.globalPos() - self._start_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._is_moving = False
        super().mouseReleaseEvent(event)

    def closeEvent(self, event):
        tray = getattr(self, 'tray_icon', None)
        if tray and tray.isVisible():
            event.ignore()
            if getattr(self, 'trim_timer', None) and self.trim_timer.isActive():
                self.trim_timer.stop()
            if getattr(self, 'timer', None) and self.timer.isActive():
                self.timer.stop()
            if not self.can_hide:
                Toast(self.tr('UI not ready, ignore hide'), 3000, parent=self).show()
                return
            self.hide()
            try:
                tray.showMessage(self.tr('Running in background'), self.tr('Program minimized to tray, click the icon to restore'), QSystemTrayIcon.Information, 3000)
            except Exception:
                pass
        else:
            super().closeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        if getattr(self, 'trim_timer', None) and not self.trim_timer.isActive():
            self.trim_timer.start(60 * 1000)
        if getattr(self, 'timer', None) and not self.timer.isActive():
            x = self.ui.horizontalSlider_spy.value()
            self.timer.start(x * 100)

    # subsystem issues
    
    def trim_textbrowser_lines(self, text_browser, max_lines=200, f=None):
        try:
            plain_text = text_browser.toPlainText()
            log_entries = re.findall(r'(?:🟢|🔴).*?(?=\n🟢|\n🔴|\Z)', plain_text, re.S)
            current_count = len(log_entries)
            if current_count > max_lines:
                trimmed_logs = log_entries[-max_lines:]
                text_browser.setPlainText('\n'.join(trimmed_logs))
                text_browser.moveCursor(text_browser.textCursor().End)
                Toast(self.tr('terminal clean up'), 3000, parent=self).show()
        except Exception as e:
            Toast(self.tr(f"trim_textbrowser_lines error: {e}"), 3000, parent=self).show()

    def init_table(self,f=None):
        table = self.ui.tableWidget
        table.setEditTriggers(QAbstractItemView.NoEditTriggers) 
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
   
    def toggle_module(self, module: QWidget,f=None):
        module.setVisible(not module.isVisible())

    def terminal_move(self, index, f=None):
        min_h = 0
        max_h = 600
        step = 10
        current_h = self.ui.textBrowser_bottom.height()
        if index == 0:
            new_h = current_h - step
        else:
            new_h = current_h + step
        new_h = max(min_h, min(new_h, max_h))
        self.ui.textBrowser_bottom.setFixedHeight(new_h)

    def terminal_fontsize(self, index, f=None):
        current_font = self.ui.textBrowser.font()
        current_size = current_font.pointSize()
        if index == 0:  # decrease
            current_size = max(6, current_size - 1)
        else:  # increase
            current_size = min(72, current_size + 1)
        current_font.setPointSize(current_size)
        self.ui.textBrowser.setFont(current_font)

    def terminal_theme(self, f=None):
        toggle0 = """QTabWidget::pane {background-color: rgba(230, 230, 230, 0);}"""
        toggle1 = """QTabWidget::pane {background-color: rgba(0, 0, 0, 0.7);}"""
        if (self.terminal_background == 0):
            self.ui.tabWidget_main.setStyleSheet(toggle1)
            self.terminal_background = 1
            Toast(self.tr('terminal is in dark mode'), 3000, parent=self).show()
        else:
            self.ui.tabWidget_main.setStyleSheet(toggle0)
            self.terminal_background = 0
            Toast(self.tr('terminal is in light mode'), 3000, parent=self).show()

    def init_bar_animation(self, f=None):
        self.leftbar = self.ui.leftbar
        self.navbar = self.ui.navbar
        self.bar_expanded = False
        self._bar_anims = []
        self.leftbar.setMinimumWidth(40)
        self.navbar.setMaximumWidth(0)
        self.left_buttons = [
            (self.ui.pushButton_leftbar_setting, "Setting"),
            (self.ui.pushButton_leftbar_ip, "IP"),
            (self.ui.pushButton_leftbar_app, "App"),
            (self.ui.pushButton_leftbar_spy, "Spy"),
            (self.ui.pushButton_leftbar_auto, "Auto"),
            (self.ui.pushButton_leftbar_edit, "Edit"),
            (self.ui.pushButton_leftbar_test, "Test"),
            (self.ui.pushButton_leftbar_tool, "Tool"),
        ]
        for btn, _ in self.left_buttons:
            btn.setText("")

    def toggle_bars(self, f=None):
        expand = not self.bar_expanded
        self.bar_expanded = expand
        self._bar_anims.clear()
        leftbar_width = 120 if expand else 40
        navbar_width = 240 if expand else 0
        anim_left = QPropertyAnimation(self.leftbar, b"minimumWidth", self)
        anim_left.setDuration(200)
        anim_left.setStartValue(self.leftbar.width())
        anim_left.setEndValue(leftbar_width)
        anim_left.setEasingCurve(QEasingCurve.InOutQuad)
        anim_nav = QPropertyAnimation(self.navbar, b"maximumWidth", self)
        anim_nav.setDuration(200)
        anim_nav.setStartValue(self.navbar.width())
        anim_nav.setEndValue(navbar_width)
        anim_nav.setEasingCurve(QEasingCurve.InOutQuad)
        def update_texts():
            for btn, text_key in self.left_buttons:
                btn.setText(self.tr(text_key) if expand else '')
        anim_left.finished.connect(update_texts)
        anim_left.start()
        anim_nav.start()
        self._bar_anims.extend([anim_left, anim_nav])

    # global program issues

    def set_label_rounded_mask(self, label, radius=25, data=None):
        rect = QRectF(0, 0, label.width(), label.height())  # 用QRectF替代QRect
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        region = QRegion(path.toFillPolygon().toPolygon())
        label.setMask(region)

    def animation_set(self,data=None):
        if not self.gif_background:
            self.gif_background = True
            self.ui.frame_main.setStyleSheet(f"""QFrame#frame_main {{border: 1px solid #bbb;border-radius: 20px;}}""")
            self.pixmap = QPixmap(None)
            self.ui.frame_main.show()
            self.update()
        folder_path = 'assets/wallpapers'
        if not self.dark_back:
            folder_path = 'assets/wallpapers'
        gif_files = [f for f in os.listdir(folder_path)
            if f.lower().endswith('.gif') and os.path.isfile(os.path.join(folder_path, f))]
        if not gif_files:
            return False
        random_gif = os.path.join(folder_path, random.choice(gif_files))
        if hasattr(self, 'movie') and self.movie:
            self.movie.stop()
        self.movie = QMovie(random_gif)
        if self.movie.state() == QMovie.error:
            return False
        Toast(self.tr('set dynamic wallpaper'), 3000, parent=self).show()
        self.ui.gif_label.setMovie(self.movie)
        self.movie.setScaledSize(self.ui.gif_label.size())
        self.movie.start()
        self.current_wallpaper = random_gif
        self.set_label_rounded_mask(self.ui.gif_label,20)

        return True

    def background_set(self, data=None):
        if self.gif_background:
            self.gif_background = False
            self.movie.stop()
            self.ui.gif_label.setMovie(None)
            self.movie = None
        folder_path = 'assets/pictures/dark'
        if not self.dark_back:
            folder_path = 'assets/pictures/light'
        entries = os.listdir(folder_path)
        files = [entry for entry in entries if os.path.isfile(os.path.join(folder_path, entry))]
        if not files:
            return
        Toast(self.tr('set static wallpaper'), 3000, parent=self).show()
        random_file = random.choice(files)
        random_file_path = os.path.join(folder_path, random_file).replace('\\', '/')
        if self.fixed_window:
            self.ui.frame_main.setStyleSheet(f"""QFrame#frame_main {{border: 1px solid #bbb;border-radius: 20px;
                    background-image: url("{random_file_path}");background-repeat: no-repeat;
                    background-position: center;background-size: 100% 100%;}}""")
            self.ui.frame_main.show()
        else:
            self.pixmap = QPixmap(random_file_path)
        self.update()

    def wallpaper_timer(self, f=None):
        if not self.ui.checkBox_set_image.isChecked():
            return
        x = self.ui.horizontalSlider_spy.value()
        if hasattr(self, "timer") and self.timer.isActive():
            self.timer.stop()
        def update_background():
            if not self.isVisible():
                return
            try:
                if self.gif_background:
                    self.animation_set()
                else:
                    self.background_set()
            except Exception as e:
                self.ui.textBrowser_bottom.append(self.tr("error when updating background:", e))
        self.timer = QTimer(self)
        self.timer.timeout.connect(update_background)
        self.timer.start(x * 100)

    def stop_wallpaper_timer(self, f=None):
        self.timer.stop()

    def toggle_language(self,f=None):
        target_lang = "zh" if self.current_lang == "en" else "en"
        if target_lang not in self.translation_files:
            self.ui.textBrowser_bottom.append(self.tr(f"not supported language: {target_lang}"))
            return
        app = QApplication.instance()
        app.removeTranslator(self.translator)
        if self.translator.load(self.translation_files[target_lang]):
            app.installTranslator(self.translator)
            self.current_lang = target_lang
            self.ui.retranslateUi(self)
            self.ui.textBrowser_bottom.append(self.tr(f"has toggled to{'chinese' if target_lang == 'zh' else 'English'}"))
        else:
            self.ui.textBrowser_bottom.append(self.tr(f"loading translation file failed: {self.translation_files[target_lang]}"))

    def load_qss(self, app, index='dark', f=None):
        qss_path = {'dark': 'assets/style/style.qss','light': 'assets/style/style_light.qss'}
        with open(qss_path[index], "r", encoding="utf-8") as file:
            content = file.read()
        app.setStyleSheet(content)

    def toggle_theme(self, data=None):
        if self.dark_back:
            self.dark_back = False
            self.load_qss(self.app, 'light')
        else:
            self.dark_back = True
            self.load_qss(self.app, 'dark')
        self.background_set()

    def set_autostart(self, flag: int, f=None):
        if current_os == 'Linux':
            app_path = os.path.abspath(os.path.realpath(sys.argv[0]))
            app_name = "myproxy" 
            desktop_filename = f"{app_name}.desktop"
            autostart_dir = Path.home() / ".config" / "autostart"
            autostart_dir.mkdir(parents=True, exist_ok=True) 
            desktop_path = autostart_dir / desktop_filename
            if flag == 1:
                with open(desktop_path, "w") as f:
                    f.write(f"""[Desktop Entry]
                        Type=Application
                        Name={app_name}
                        Comment=Auto-start my proxy application
                        Exec={app_path}
                        Terminal=false
                        Hidden=false
                        NoDisplay=false
                        X-GNOME-Autostart-enabled=true
                        X-KDE-autostart-after=panel
                        """)
                os.chmod(desktop_path, 0o755)
                Toast(self.tr('autostart set'), 3000, parent=self).show()
            else:
                if desktop_path.exists():
                    os.remove(desktop_path)
                    Toast(self.tr('autostart banned'), 3000, parent=self).show()
        elif current_os == 'Windows':
            import winreg
            app_path = os.path.abspath(os.path.realpath(sys.argv[0]))
            app_name = "myproxy"
            try:
                reg_key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Run",
                    0,
                    winreg.KEY_SET_VALUE
                )
                if flag == 1:
                    winreg.SetValueEx(reg_key, app_name, 0, winreg.REG_SZ, app_path)
                    Toast(self.tr('autostart set'), 3000, parent=self).show()
                else:
                    try:
                        winreg.DeleteValue(reg_key, app_name)
                        Toast(self.tr('autostart banned'), 3000, parent=self).show()
                    except FileNotFoundError:
                        pass  
                winreg.CloseKey(reg_key)
            except Exception as e:
                print("Failed to set autostart:", e)

    def max_window(self, f=None):
        size = self.size()
        if self.fixed_window:
            self.fixed_window = False
            self.setWindowFlags(Qt.Window)
            self.ui.frame_main.setStyleSheet("""QFrame#frame_main {border: 1px solid #bbb;border-radius: 20px;}""")
            self.background_set()
        else:
            self.fixed_window = True
            self.setWindowFlags(Qt.FramelessWindowHint)
            self.ui.frame_main.setStyleSheet("""QFrame#frame_main {border: none;border-radius: 0px;}""")
            self.background_set()
            self.animation_set()
        self.show()
        QTimer.singleShot(0, lambda: self.resize(size))

#   system tray

    def init_tray(self, f=None):
        self.tray_icon = QSystemTrayIcon(QIcon("assets/icons/icon.ico"), self)
        tray_menu = QMenu(self)
        show_action = QAction(self.tr('Show'), self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)
        hide_action = QAction(self.tr('Hide'), self)
        hide_action.triggered.connect(self.hide)
        tray_menu.addAction(hide_action)
        tray_menu.addSeparator()
        quit_action = QAction(self.tr('Exit'), self)
        quit_action.triggered.connect(self.cleanup_and_exit)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        try:
            self.tray_icon.show()
        except Exception as e:
            self.ui.textBrowser_bottom.append(self.tr("tray icon show failed:", e))

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.showNormal()
            self.activateWindow()
        elif reason == QSystemTrayIcon.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.showNormal()
                self.activateWindow()

    def cleanup_and_exit(self, f=None):
        self.func.write_state()
        for t in (getattr(self, 'trim_timer', None), getattr(self, 'timer', None)):
            if t and t.isActive():
                t.stop()
        if hasattr(self, 'movie') and self.movie:
            self.movie.stop()
            self.movie = None
        try:
            loop = asyncio.get_event_loop()
            for task in asyncio.all_tasks(loop):
                task.cancel()
        except Exception as e:
            print("asyncio cleanup error:", e)
        if hasattr(self, 'tray_icon'):
            self.tray_icon.hide()
            self.tray_icon.deleteLater()
            self.tray_icon = None
        try:
            if getattr(self.func, 'system_proxy_enabled', False) or self.ui.checkBox_system.isChecked():
                self.func.disable_system_proxy()
                self.func._set_checkbox_state(self.ui.checkBox_system, False)
            self.apps.stop_proxy()
            self.func.stop_global_proxy()
            self.func.stop_http_bridge()
        except Exception as e:
            print("stop proxy error:", e)
        QApplication.quit()
