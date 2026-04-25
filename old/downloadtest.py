import os
import sys
import pathlib
import threading
import requests
import time
import math
import subprocess
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QTabWidget
from PyQt5.QtCore import QUrl, QObject, pyqtSlot, pyqtSignal, QThread
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile

# ==== 软件渲染环境 ====
os.environ["QT_OPENGL"] = "software"
os.environ["QTWEBENGINE_DISABLE_GPU"] = "1"
os.environ["QT_QUICK_BACKEND"] = "software"
os.environ["QT_XCB_GL_INTEGRATION"] = "none"

class WebEngineView(QWebEngineView):

    def __init__(self, mainwindow, parent=None):
        super(WebEngineView, self).__init__(parent)
        self.mainwindow = mainwindow
        self.page().fullScreenRequested.connect(self.handle_fullscreen_request)

    def createWindow(self, QWebEnginePage_WebWindowType):
        new_webview = WebEngineView(self.mainwindow)
        self.mainwindow.create_tab(new_webview)
        return new_webview
    
    def handle_fullscreen_request(self, request):
        if request.toggleOn():
            self.window().showFullScreen()
        else:
            self.window().showNormal()
        request.accept()

# ==== 下载线程 ====
class Downloader(QThread):
    progress = pyqtSignal(float, float, float)  # 已下载, 总大小, 当前速度
    stateChanged = pyqtSignal(str)
    
    def __init__(self, url, path, threads=4):
        super().__init__()
        self.url = url
        self.path = path
        self.threads = threads
        self._pause = False
        self._stop = False

    def run(self):
        self.start_time = time.time()
        try:
            r = requests.head(self.url)
            total_size = int(r.headers.get("Content-Length", 0))
            part = total_size // self.threads

            # 创建空文件
            with open(self.path, "wb") as f:
                f.truncate(total_size)

            downloaded = 0
            lock = threading.Lock()

            def download_range(start, end):
                nonlocal downloaded
                headers = {"Range": f"bytes={start}-{end}"}
                res = requests.get(self.url, headers=headers, stream=True)
                with open(self.path, "r+b") as f:
                    f.seek(start)
                    for chunk in res.iter_content(1024):
                        if self._stop:
                            return
                        while self._pause:
                            time.sleep(0.1)
                        if chunk:
                            f.write(chunk)
                            with lock:
                                downloaded += len(chunk)
                                elapsed = time.time() - self.start_time
                                speed = downloaded / elapsed if elapsed > 0 else 0
                                self.progress.emit(downloaded, total_size, speed)

            threads = []
            for i in range(self.threads):
                start = i * part
                end = total_size - 1 if i == self.threads - 1 else (i + 1) * part - 1
                t = threading.Thread(target=download_range, args=(start, end))
                t.start()
                threads.append(t)

            for t in threads:
                t.join()

            if not self._stop:
                self.stateChanged.emit(f"✅ 下载完成: {self.path}")
            else:
                self.stateChanged.emit(f"❌ 下载已停止")

        except Exception as e:
            self.stateChanged.emit(f"❗ 错误: {str(e)}")

    def pause(self):
        self._pause = True
        self.stateChanged.emit("⏸️ 已暂停")

    def resume(self):
        self._pause = False
        self.stateChanged.emit("▶️ 继续下载")

    def stop(self):
        self._stop = True
        self.stateChanged.emit("⏹️ 停止下载并删除文件")
        if os.path.exists(self.path):
            os.remove(self.path)

# ==== PyQt ↔ HTML 桥 ====
class Bridge(QObject):
    progressChanged = pyqtSignal(float, float, float)
    stateChanged = pyqtSignal(str)
    pathChanged = pyqtSignal(str)
    startTimeChanged = pyqtSignal(str)

    def __init__(self, view):
        super().__init__()
        self.view = view
        self.default_download_path = str(pathlib.Path.home() / "Downloads")
        self.dl = None

    @pyqtSlot()
    def selectFolder(self):
        folder = QFileDialog.getExistingDirectory(None, "选择下载目录", self.default_download_path)
        if folder:
            self.default_download_path = folder
            self.view.page().runJavaScript(f"updatePath('{folder}')")

    @pyqtSlot(str)
    def startDownload(self, url):
        self._start(url)

    def _start(self, url):
        filename = url.split("/")[-1] or "download.tmp"
        path = os.path.join(self.default_download_path, filename)
        self.pathChanged.emit(path)
        start_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        self.startTimeChanged.emit(start_time_str)

        self.dl = Downloader(url, path)
        self.dl.progress.connect(lambda done, total, speed: self.progressChanged.emit(done, total, speed))
        self.dl.stateChanged.connect(lambda msg: self.stateChanged.emit(msg))
        self.dl.start()

    # 🚀 新增接口：直接从 Python 启动下载
    def startDownloadFromPython(self, url):
        self._start(url)

# ==== 主窗口 ====
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.resize(1200, 700)
        self.setWindowTitle("双页面浏览+下载器")

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # ===== 百度页 =====
        self.webview_baidu = QWebEngineView()
        self.webview_baidu.load(QUrl("https://www.baidu.com"))
        self.tabs.addTab(self.webview_baidu, "百度")

        # 下载请求拦截
        profile = QWebEngineProfile.defaultProfile()
        profile.downloadRequested.connect(self.on_downloadRequested)

        # ===== 下载页 =====
        self.webview_download = QWebEngineView()
        self.tabs.addTab(self.webview_download, "下载器")

        # 加载下载器 HTML
        html_path = os.path.abspath("download.html")
        self.webview_download.load(QUrl.fromLocalFile(html_path))

        # QWebChannel 绑定
        from PyQt5.QtWebChannel import QWebChannel
        self.channel = QWebChannel(self.webview_download.page())
        self.bridge = Bridge(self.webview_download)
        self.channel.registerObject("bridge", self.bridge)
        self.webview_download.page().setWebChannel(self.channel)

    # ===== 拦截百度下载 =====
    def on_downloadRequested(self, download):
        url = download.url().toString()  # 获取下载链接
        # 自动发送到下载器开始下载
        self.tabs.setCurrentWidget(self.webview_download)
        self.bridge.startDownloadFromPython(url)
        download.cancel()  # 阻止默认下载行为

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
