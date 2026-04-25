import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QToolButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QProgressBar, QLabel, QTreeWidget, QTreeWidgetItem, QAbstractItemView
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon, QColor, QPalette

class EnhancedDownloadManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("增强版下载器 - FDM 风格")
        self.resize(1000, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # 顶部工具栏
        toolbar_layout = QHBoxLayout()
        self.btn_add = self.create_toolbutton("添加", "icons/add.png", "添加新下载任务")
        self.btn_pause_all = self.create_toolbutton("暂停全部", "icons/pause.png", "暂停所有任务")
        self.btn_resume_all = self.create_toolbutton("开始全部", "icons/play.png", "恢复所有任务")
        self.btn_delete_all = self.create_toolbutton("删除全部", "icons/delete.png", "删除所有任务")
        toolbar_layout.addWidget(self.btn_add)
        toolbar_layout.addWidget(self.btn_pause_all)
        toolbar_layout.addWidget(self.btn_resume_all)
        toolbar_layout.addWidget(self.btn_delete_all)
        toolbar_layout.addStretch()
        main_layout.addLayout(toolbar_layout)

        # 中间区域
        middle_layout = QHBoxLayout()
        main_layout.addLayout(middle_layout)

        # 左侧任务分类
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setDragDropMode(QAbstractItemView.InternalMove)  # 支持拖拽排序
        categories = ["全部任务", "下载中", "已完成"]
        for cat in categories:
            QTreeWidgetItem(self.tree, [cat])
        self.tree.setMaximumWidth(180)
        middle_layout.addWidget(self.tree)

        # 右侧任务表格
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["文件名", "进度", "状态", "速度", "大小", "操作"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        middle_layout.addWidget(self.table)

        # 底部状态栏
        status_layout = QHBoxLayout()
        self.lbl_status = QLabel("任务: 0 | 下载中: 0 | 已完成: 0 | 总速度: 0 KB/s")
        status_layout.addWidget(self.lbl_status)
        status_layout.addStretch()
        main_layout.addLayout(status_layout)

        # 模拟添加测试任务
        for i in range(5):
            self.add_download_task(f"文件_{i+1}.zip", size=100 + i*50)

        # 模拟进度更新
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_progress)
        self.timer.start(500)

    def create_toolbutton(self, text, icon_path, tooltip):
        btn = QToolButton()
        btn.setText(text)
        btn.setIcon(QIcon(icon_path))
        btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        btn.setToolTip(tooltip)
        return btn

    def add_download_task(self, filename, size=100):
        row = self.table.rowCount()
        self.table.insertRow(row)

        # 文件名
        self.table.setItem(row, 0, QTableWidgetItem(filename))

        # 进度条
        progress_bar = QProgressBar()
        progress_bar.setValue(0)
        progress_bar.setTextVisible(True)
        progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #bbb;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #37a;
                width: 10px;
                margin: 0.5px;
            }
        """)
        self.table.setCellWidget(row, 1, progress_bar)

        # 状态
        self.table.setItem(row, 2, QTableWidgetItem("下载中"))

        # 下载速度
        self.table.setItem(row, 3, QTableWidgetItem("0 KB/s"))

        # 文件大小
        self.table.setItem(row, 4, QTableWidgetItem(f"{size} MB"))

        # 操作按钮组
        btn_pause = QToolButton()
        btn_pause.setText("暂停")
        btn_pause.clicked.connect(lambda _, r=row: print(f"暂停第{r}个任务"))
        self.table.setCellWidget(row, 5, btn_pause)

    def update_progress(self):
        total_speed = 0
        completed = 0
        for row in range(self.table.rowCount()):
            progress_bar = self.table.cellWidget(row, 1)
            if progress_bar.value() < 100:
                progress_bar.setValue(progress_bar.value() + 2)
                speed = 500 + row*50
                self.table.setItem(row, 3, QTableWidgetItem(f"{speed} KB/s"))
                total_speed += speed
            else:
                self.table.setItem(row, 2, QTableWidgetItem("已完成"))
                completed += 1
        self.lbl_status.setText(f"任务: {self.table.rowCount()} | 下载中: {self.table.rowCount()-completed} | 已完成: {completed} | 总速度: {total_speed} KB/s")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = EnhancedDownloadManager()
    window.show()
    sys.exit(app.exec_())
