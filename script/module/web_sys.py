import os,tldextract,sys

from PyQt5.QtWebEngineWidgets import QWebEngineView,QWebEngineProfile,QWebEngineDownloadItem
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PyQt5.QtCore import pyqtSignal,QObject,pyqtSlot,QUrl,QTimer, QDateTime,QIODevice,QFile
from PyQt5.QtWidgets import QFileDialog,QTableWidgetItem,QProgressBar,QToolButton,QMenu,QAction,QMessageBox

from script.utils.file_manager import NetConnDB
from script.utils.util_manager import utils
from script.utils.util_web import Toast

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from script.window.mainwindow import MainWindow

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

@utils.decorate_all_methods(utils.show_error_messagebox)
class web_system(QObject):

    web_signal = pyqtSignal(dict)

    def __init__(self, parent, f=None):
        super().__init__(parent)
        self.parent: 'MainWindow' = parent
        self.fav_dbpath = 'data/favorite.db'
        self.net_dbpath = 'data/netlog.db'
        self.mainwebpage = utils.resource_path("webpage/mainpage.html")
        self.netdb = NetConnDB(self.fav_dbpath, self.net_dbpath)
        self.fav = {}
        self.netlog = {}

        self.web_signal.connect(self.web_receiver)

        self.profile = QWebEngineProfile.defaultProfile()

        self.proxy = ''
        self.html_files = [] 
        self.current_downloads = {} 
        self.active_network_downloads = {}
        self.default_download_path = os.path.join(os.getcwd(), "download")
        
    # browser system

    @pyqtSlot(dict)
    def web_receiver(self, data: dict):
        if data['aim'] == 'web_system' and data['op'] == 'send_proxy':
            self.proxy = data['data']
            if self.proxy:
                self.setup_proxy()
            else:
                self.parent.ui.textBrowser_bottom.append(self.tr('❌ web system does not receive any information'))

    def web_ui_signal(self, f=None):
        self.parent.ui.btn_web_newtab.clicked.connect(self.new_tab)
        self.parent.ui.btn_web_go.clicked.connect(self.navigate)
        self.parent.ui.btn_web_previous.clicked.connect(self.go_back)
        self.parent.ui.btn_web_next.clicked.connect(self.go_forward)
        self.parent.ui.btn_web_refresh.clicked.connect(self.refresh_page)
        self.parent.ui.btn_web_home.clicked.connect(self.go_home)
        self.parent.ui.lineEdit_web.returnPressed.connect(self.navigate)
        self.parent.ui.tabWidget_browser.currentChanged.connect(self.update_ui)
        self.parent.ui.tabWidget_browser.tabCloseRequested.connect(self.close_tab)
        self.profile = QWebEngineProfile.defaultProfile()
        self.profile.downloadRequested.connect(self.on_downloadRequested)
        self.parent.ui.comboBox_defaultweb.currentIndexChanged.connect(self.launch_html)
        self.parent.ui.btn_download_add.clicked.connect(self.start_download)

    def setup_proxy(self):
        proxy_str = self.proxy
        if proxy_str.startswith("socks://"):
            proxy_str = proxy_str[len("socks://"):]
        elif proxy_str.startswith("socks5://"):
            proxy_str = proxy_str[len("socks5://"):]
        elif proxy_str.startswith("http://"):
            proxy_str = proxy_str[len("http://"):]
        elif proxy_str.startswith("https://"):
            proxy_str = proxy_str[len("https://"):]
        if ':' in proxy_str:
            host, port = proxy_str.split(':', 1)
        else:
            host = proxy_str
            port = '1080'
        pac_script = f"function FindProxyForURL(url, host) {{ return 'SOCKS5 {host}:{port}'; }}"
        data_url = QUrl("data:," + pac_script)
        profile = QWebEngineProfile.defaultProfile()
        # profile.setProxyAutoConfigUrl(data_url)

    def handle_new_tab_from_view(self, web_view):
        web_view.load(QUrl.fromLocalFile(self.mainwebpage))
        web_view.urlChanged.connect(self.update_address_bar)
        web_view.loadFinished.connect(lambda: self.update_tab_title(web_view))
        index = self.parent.ui.tabWidget_browser.addTab(web_view, "loading...")
        self.parent.ui.tabWidget_browser.setCurrentIndex(index)

    def new_tab(self, url=None, f=None):
        web_view = WebEngineView(self.parent)
        if url:
            web_view.load(QUrl(url))
        else:
            web_view.load(QUrl.fromLocalFile(self.mainwebpage))
        web_view.urlChanged.connect(self.update_address_bar)
        web_view.loadFinished.connect(lambda: self.update_tab_title(web_view))
        web_view.iconChanged.connect(lambda icon, wv=web_view: self.update_tab_icon(wv, icon))
        index = self.parent.ui.tabWidget_browser.addTab(web_view, "loading...")
        self.parent.ui.tabWidget_browser.setCurrentIndex(index)
        return web_view

    def update_tab_icon(self, web_view, icon):
        tab_widget = self.parent.ui.tabWidget_browser
        index = tab_widget.indexOf(web_view)
        if index != -1:
            tab_widget.setTabIcon(index, icon)

    def close_tab(self, index, f=None):
        tab_widget = self.parent.ui.tabWidget_browser
        if tab_widget.count() == 1:
            current_web = self.get_current_webview()
            if current_web:
                current_web.load(QUrl.fromLocalFile(self.mainwebpage))
            return
        webview = tab_widget.widget(index)
        if webview:
            webview.setUrl(QUrl("about:blank"))
            tab_widget.removeTab(index)
            webview.deleteLater()

    def navigate(self, f=None):
        current_web = self.get_current_webview()
        if current_web:
            url_text = self.parent.ui.lineEdit_web.text().strip()
            if not url_text.startswith(('http://', 'https://')):
                url_text = f'https://{url_text}'
            current_web.load(QUrl(url_text))

    def go_back(self, f=None):
        current_web = self.get_current_webview()
        if current_web and current_web.history().canGoBack():
            current_web.back()

    def go_forward(self, f=None):
        current_web = self.get_current_webview()
        if current_web and current_web.history().canGoForward():
            current_web.forward()

    def refresh_page(self, f=None):
        current_web = self.get_current_webview()
        if current_web:
            current_web.reload()

    def go_home(self, f=None):
        current_web = self.get_current_webview()
        if current_web:
            current_web.load(QUrl.fromLocalFile(self.mainwebpage))

    def update_address_bar(self, url, f=None):
        self.parent.ui.lineEdit_web.setText(url.toString())

    def update_tab_title(self, web_view, f=None):
        index = self.parent.ui.tabWidget_browser.indexOf(web_view)
        if index != -1:
            title = web_view.page().title()
            display_title = title[:20] + "..." if len(title) > 20 else title
            self.parent.ui.tabWidget_browser.setTabText(index, display_title)

    def update_ui(self, f=None):
        current_web = self.get_current_webview()
        if current_web:
            try:
                self.parent.ui.lineEdit_web.setText(current_web.url().toString())
                self.parent.ui.btn_web_previous.setEnabled(current_web.history().canGoBack())
                self.parent.ui.btn_web_next.setEnabled(current_web.history().canGoForward())
            except:
                self.parent.ui.textBrowser_bottom.append(self.tr('❌ can not update the webview'))

    def get_current_webview(self, f=None):
        current_index = self.parent.ui.tabWidget_browser.currentIndex()
        if current_index != -1:
            return self.parent.ui.tabWidget_browser.widget(current_index)
        return None
    
    # manage system

    def load_favorite(self, f=None):
        if not os.path.exists(self.fav_dbpath):
            self.netdb.initialize_fav_db()
        self.fav = self.netdb.get_all_favorites()
        box = self.parent.ui.comboBox_web
        box.clear()
        for fav_id, fav in self.fav.items():
            box.addItem(fav['name'], fav_id)

    def add_favorite(self, f=None):
        web = self.get_current_webview()
        if not web:
            return
        url = web.url().toString()
        if not url.startswith(('http://', 'https://')):
            return
        for fav in self.netdb.get_all_favorites().values():
            if fav['url'] == url:
                return
        name = tldextract.extract(url).domain or "site"
        new_id = self.netdb.add_favorite(name, url)
        if new_id:
            self.load_favorite()

    def delete_favorite(self, f=None):
        fav_id = self.parent.ui.comboBox_web.currentData()
        if fav_id is not None:
            self.netdb.remove_favorite(fav_id)
            self.load_favorite()

    def open_favorite(self, f=None):
        fav_id = self.parent.ui.comboBox_web.currentData()
        if fav_id and fav_id in self.fav:
            self.new_tab(self.fav[fav_id]['url'])

    def load_html(self, path='./webpage/'):
        self.html_files.clear()
        self.parent.ui.comboBox_defaultweb.clear()
        if not os.path.exists(path):
            return
        for file in os.listdir(path):
            if file.lower().endswith('.html'):
                full_path = os.path.join(path, file)
                self.html_files.append(full_path)
                self.parent.ui.comboBox_defaultweb.addItem(file)

    def launch_html(self, index=None):
        if index is None:
            index = self.parent.ui.comboBox_defaultweb.currentIndex()
        if index < 0 or index >= len(self.html_files):
            return
        html = self.html_files[index]
        html_path = utils.resource_path(html)
        url = QUrl.fromLocalFile(html_path)
        current_web = self.get_current_webview()
        if current_web is not None and hasattr(current_web, 'setUrl'):
            current_web.setUrl(url)
        else:
            self.new_tab(url.toString())

    def add_download_task(self, filename, size=0, status="waiting",f = None):
        row = self.parent.ui.tableWidget_download.rowCount()
        self.parent.ui.tableWidget_download.insertRow(row)
        self.parent.ui.tableWidget_download.setItem(row, 0, QTableWidgetItem(filename))
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
        self.parent.ui.tableWidget_download.setCellWidget(row, 1, progress_bar)
        self.parent.ui.tableWidget_download.setItem(row, 2, QTableWidgetItem(status))
        self.parent.ui.tableWidget_download.setItem(row, 3, QTableWidgetItem("0 KB/s"))
        self.parent.ui.tableWidget_download.setItem(row, 4, QTableWidgetItem(f"{size/1024/1024:.2f} MB"))
        btn_pause = QToolButton()
        btn_pause.setText("Actions")
        menu = QMenu(btn_pause)
        act_pause = QAction("Pause", self)
        act_resume = QAction("Resume", self)
        act_stop = QAction("Stop", self)
        act_remove = QAction("Remove", self)
        act_path = QAction("Path", self)
        menu.addAction(act_pause)
        menu.addAction(act_resume)
        menu.addAction(act_stop)
        menu.addAction(act_remove)
        menu.addAction(act_path)
        btn_pause.setMenu(menu)
        btn_pause.setPopupMode(QToolButton.InstantPopup)
        self.parent.ui.tableWidget_download.setCellWidget(row, 5, btn_pause)
        self.parent.ui.tableWidget_download.setItem(row, 6, QTableWidgetItem("--"))
        return row
    
    def start_download(self, url=None):
        if not url:
            url = self.parent.ui.lineEdit_download_url.text().strip()
        if not url:
            QMessageBox.warning(self.parent, "Invalid URL", "Please enter a valid URL!")
            return
        filename = os.path.basename(url.split("?")[0]) or "New_File"
        path = os.path.join(self.default_download_path, filename)
        os.makedirs(self.default_download_path, exist_ok=True)
        row = self.add_download_task(filename, size=0, status="waiting")
        file_handle = QFile(path)
        if not file_handle.open(QIODevice.WriteOnly):
            QMessageBox.warning(self.parent, "Error", "Cannot open file for writing!")
            return
        manager = QNetworkAccessManager(self)
        request = QNetworkRequest(QUrl(url))
        reply = manager.get(request)
        start_time = QDateTime.currentDateTime()
        self.active_network_downloads[row] = {
            'file': file_handle,
            'manager': manager,
            'reply': reply,
            'path': path,
        }
        reply.readyRead.connect(lambda r=reply, f=file_handle: f.write(r.readAll()))
        reply.downloadProgress.connect(lambda received, total, download_row=row, started=start_time: self._update_progress_bar(download_row, received, total, started))
        reply.finished.connect(lambda download_row=row: self._download_finished(download_row))

    def on_downloadRequested(self, download: QWebEngineDownloadItem):
        path = os.path.join(self.default_download_path, download.downloadFileName())
        os.makedirs(self.default_download_path, exist_ok=True)
        download.setPath(path)
        download.accept()
        self.setup_download_task(download)
        Toast(self.tr('start downloading'), 3000, parent=self.parent).show()

    def setup_download_task(self, download):
        row = self.add_download_task(download.downloadFileName(), download.totalBytes())
        self.current_downloads[row] = download
        last_bytes = 0
        timer = QTimer(self)  

        def update_progress():
            nonlocal last_bytes
            received = download.receivedBytes()
            total = download.totalBytes() if download.totalBytes() > 0 else 1
            speed = (received - last_bytes) / 1024 / 0.5
            last_bytes = received
            percent = int(received / total * 100)
            progress_bar = self.parent.ui.tableWidget_download.cellWidget(row, 1)
            progress_bar.setValue(percent)
            self.parent.ui.tableWidget_download.setItem(row, 2, QTableWidgetItem("downloading"))
            self.parent.ui.tableWidget_download.setItem(row, 3, QTableWidgetItem(self._fmt_speed(speed)))

        timer.timeout.connect(update_progress)  
        timer.start(500)

        def download_finished():
            if timer.isActive():  
                timer.stop()     
            self.parent.ui.tableWidget_download.setItem(row, 2, QTableWidgetItem("finished"))
            self.parent.ui.tableWidget_download.setItem(row, 3, QTableWidgetItem("0 KB/s"))
            progress_bar = self.parent.ui.tableWidget_download.cellWidget(row, 1)
            progress_bar.setValue(100)

        download.finished.connect(download_finished)
        self.current_downloads[row] = (download, timer) 

    def _update_progress_bar(self, row, received, total, start_time):
        if total == 0:
            percent = 0
        else:
            percent = int(received / total * 100)

        progress_bar = self.parent.ui.tableWidget_download.cellWidget(row, 1)
        progress_bar.setValue(percent)

        elapsed = start_time.msecsTo(QDateTime.currentDateTime()) / 1000
        speed = (received / 1024) / elapsed if elapsed > 0 else 0

        def fmt_speed(val):
            return f"{val/1024:.2f} MB/s" if val > 1024 else f"{val:.2f} KB/s"

        self.parent.ui.tableWidget_download.setItem(row, 2, QTableWidgetItem("downloading"))
        self.parent.ui.tableWidget_download.setItem(row, 3, QTableWidgetItem(fmt_speed(speed)))

    def _fmt_speed(self, speed_kb, f=None):
        return f"{speed_kb / 1024:.2f} MB/s" if speed_kb >= 1024 else f"{speed_kb:.2f} KB/s"

    def _download_finished(self, row):
        download_info = self.active_network_downloads.pop(row, None)
        if not download_info:
            return
        file_handle = download_info['file']
        reply = download_info['reply']
        if file_handle.isOpen():
            file_handle.close()
        reply.deleteLater()
        self.parent.ui.tableWidget_download.setItem(row, 2, QTableWidgetItem("finished"))
        self.parent.ui.tableWidget_download.setItem(row, 3, QTableWidgetItem("0 KB/s"))
        progress_bar = self.parent.ui.tableWidget_download.cellWidget(row, 1)
        progress_bar.setValue(100)
        Toast(self.tr('download finished'), 3000, parent=self.parent).show()



    


