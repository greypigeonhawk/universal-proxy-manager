from PyQt5 import QtWidgets, QtCore

class CustomToolTip(QtWidgets.QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)

        self.setStyleSheet("""
            QFrame {
                background-color: rgba(0, 0, 0, 180);
                border-radius: 8px;
            }
            QLabel {
                color: white;
                padding: 6px 12px;
                font-size: 12px;
            }
        """)

        self.label = QtWidgets.QLabel("", self)
        layout = QtWidgets.QHBoxLayout(self)
        layout.addWidget(self.label)
        layout.setContentsMargins(0,0,0,0)

        self.opacity_effect = QtWidgets.QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.fade_anim = QtCore.QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_anim.setDuration(200)
        self.fade_anim.finished.connect(self.hide)

    def setText(self, text):
        self.label.setText(text)
        self.adjustSize()

    def show_above_widget(self, widget, text):
        self.setText(text)
        rect = widget.rect()
        parent_pos = widget.mapToParent(rect.topLeft())
        w, h = self.width(), self.height()
        x = parent_pos.x() + (rect.width() - w)//2
        y = parent_pos.y() - h - 6
        self.move(x, y)

        self.fade_anim.stop()
        self.opacity_effect.setOpacity(0.0)
        self.show()
        self.fade_anim.setStartValue(0.0)
        self.fade_anim.setEndValue(1.0)
        self.fade_anim.start()

    def hide_with_fade(self):
        self.fade_anim.stop()
        self.fade_anim.setStartValue(self.opacity_effect.opacity())
        self.fade_anim.setEndValue(0.0)
        self.fade_anim.start()


class Demo(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setMouseTracking(True)

        layout = QtWidgets.QVBoxLayout(self)

        # 多按钮
        self.buttons = []
        for i in range(1, 4):
            btn = QtWidgets.QPushButton(f"按钮{i}")
            btn.setMouseTracking(True)
            layout.addWidget(btn)
            self.buttons.append(btn)

        self.tooltip = CustomToolTip(self)

        # 显示延迟定时器
        self.hover_timer = QtCore.QTimer(self)
        self.hover_timer.setSingleShot(True)
        self.hover_timer.timeout.connect(self.show_tooltip)

        # 隐藏延迟定时器
        self.close_timer = QtCore.QTimer(self)
        self.close_timer.setSingleShot(True)
        self.close_timer.timeout.connect(self.hide_tooltip)

        # 最短显示时间定时器
        self.min_show_timer = QtCore.QTimer(self)
        self.min_show_timer.setSingleShot(True)
        self.min_show_timer.timeout.connect(self.on_min_show_elapsed)
        self.min_show_elapsed = True

        self.current_widget = None
        self.pending_hide = False

        # 安装事件过滤器
        for btn in self.buttons:
            btn.installEventFilter(self)

    def show_tooltip(self):
        if self.current_widget:
            text = f"这是 {self.current_widget.text()} 的提示"
            self.tooltip.show_above_widget(self.current_widget, text)
            # 启动最短显示时间（1秒）
            self.min_show_elapsed = False
            self.min_show_timer.start(1000)

    def on_min_show_elapsed(self):
        self.min_show_elapsed = True
        if self.pending_hide:
            self.tooltip.hide_with_fade()
            self.pending_hide = False

    def hide_tooltip(self):
        # 如果最短显示时间没到，延迟隐藏
        if not self.min_show_elapsed:
            self.pending_hide = True
        else:
            self.tooltip.hide_with_fade()
            self.pending_hide = False

    def eventFilter(self, obj, event):
        if obj in self.buttons:
            if event.type() == QtCore.QEvent.Enter:
                self.current_widget = obj
                self.hover_timer.start(500)  # 延迟显示
                self.close_timer.stop()
                self.pending_hide = False
            elif event.type() == QtCore.QEvent.Leave:
                # 延迟隐藏
                self.close_timer.start(200)
        return super().eventFilter(obj, event)


if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    win = Demo()
    win.setWindowTitle("稳定版 Tooltip（最短显示时间策略）")
    win.resize(300, 200)
    win.show()
    app.exec_()
