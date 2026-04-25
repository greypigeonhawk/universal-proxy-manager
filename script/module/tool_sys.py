import os,shutil,asyncio,aiohttp,weakref,platform,sys,io

import qrcode
import sip

from PyQt5.QtWidgets import QMessageBox, QGraphicsScene, QDialog, QVBoxLayout, QLabel
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtCore import pyqtSignal,QObject,QTimer

from script.utils.util_manager import utils
from script.utils.file_manager import ToolConfigDB

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from script.window.mainwindow import MainWindow

current_os = platform.system()

@utils.decorate_all_methods(utils.show_error_messagebox)
class tool_system(QObject):

    tool_signal = pyqtSignal(dict)

    def __init__(self, parent,f=None):
        super().__init__()
        self.parent: 'MainWindow' = parent
        self.latest_tool = self.selected_tool_id = self.port = self.latest_tool_id = self.ip_index = None
        self.exe_path = self.cmd_path = self.agency = self.folder_name = self.para1 = self.para2 = self.para3 = ''
        self.to_path = self.appimage_path = ''
        self.urls = []
        self.tool_dbpath = "data/tools.db"
        self.tooldb = ToolConfigDB(self.tool_dbpath)
        self.tools = {}
        self.qrcode_preview = None
        self.qrcode_payload = ''
        self.qrcode_payload_label = ''
        self.qrcode_request_token = 0
        self.tool_signal.connect(self.tool_receiver)

    def tool_ui_signal(self, f=None):
        self.parent.ui.pushButton_auto_config.clicked.connect(self.cmd_analysis)
        self.parent.ui.pushButton_auto_analysis.clicked.connect(self.add_auto_tool)
        self.parent.ui.pushButton_auto_appimage.clicked.connect(self.appimage_file_path)
        self.parent.ui.pushButton_auto_open.clicked.connect(self.exe_file_path)
        self.parent.ui.pushButton_auto_copy.clicked.connect(self.copy_folder)
        self.parent.ui.lineEdit_tool.textChanged.connect(self.search_tool)
        self.parent.ui.pushButton_edit_delete.clicked.connect(self.delete_tools)
        self.parent.ui.comboBox_edit.currentIndexChanged.connect(self.select_tool)
        self.parent.ui.comboBox_tool.currentIndexChanged.connect(self.select_tool)
        self.parent.ui.comboBox_ip.currentIndexChanged.connect(self.select_ip)
        self.parent.ui.comboBox_ip.currentTextChanged.connect(self.schedule_qrcode_view_update)
        self.parent.ui.radioButton_qrcode_url.toggled.connect(self.schedule_qrcode_view_update)
        self.parent.ui.radioButton_qrcode_config.toggled.connect(self.schedule_qrcode_view_update)
        self.parent.ui.pushButton_edit_addurl.clicked.connect(self.add_url)
        self.parent.ui.pushButton_edit_delurl.clicked.connect(self.del_url)
        self.parent.ui.pushButton_edit_confirm.clicked.connect(self.edit_command)
        self.parent.ui.pushButton_ip.clicked.connect(lambda: asyncio.create_task(self.update_ip()))
        self.parent.ui.pushButton_ip_auto.clicked.connect(lambda: asyncio.create_task(self.update_all_ip()))
        self.parent.ui.graphicsView_qrcode.viewport().installEventFilter(self)
        self.parent.ui.graphicsView_qrcode.show()
        self.schedule_qrcode_view_update()

    def eventFilter(self, obj, event, f=None):
        view = getattr(self.parent.ui, 'graphicsView_qrcode', None)
        if view is None or sip.isdeleted(view):
            return False
        viewport = view.viewport()
        if viewport is None or sip.isdeleted(viewport):
            return False
        if obj == viewport and event.type() == QEvent.MouseButtonPress:
            if event.button() == Qt.LeftButton:
                self.show_large_qrcode()
                return True
        return super().eventFilter(obj, event)

    # basic tool issues

    def load_tool(self, f=None):
        if not os.path.exists(self.tool_dbpath):
            self.tooldb.initialize_db()
        self.tools = self.tooldb.load_all_tools()
        self.latest_tool_id = self.tooldb.get_latest_toolid()
        if self.latest_tool_id not in self.tools:
            self.latest_tool_id = None
        self.search_tool()
        self.load_ip()
        if self.latest_tool_id:
            self.selected_tool_id = self.latest_tool_id
            combo = self.parent.ui.comboBox_tool
            index = combo.findData(self.latest_tool_id)
            if index != -1:
                combo.setCurrentIndex(index)
                tool_name = self.tools[self.latest_tool_id]['name']
                self.parent.ui.textBrowser_bottom.append(self.tr(f"🟢 Loaded latest tool: {tool_name}"))

    def select_tool(self, f=None):
        combo = self.parent.ui.comboBox_tool
        if combo.currentIndex() >= 0:
            self.selected_tool_id = combo.currentData()
            tool_name = self.tools[self.selected_tool_id]['name']
            self.parent.ui.textBrowser_bottom.append(self.tr(f'🟢 Tool selected: {tool_name}'))
            self.load_ip()

    def search_tool(self, f=None):
        combo = self.parent.ui.comboBox_tool
        combo.clear()
        self.parent.ui.comboBox_edit.clear()
        search = self.parent.ui.lineEdit_tool.text().lower()
        for tool_id, tool in self.tools.items():
            self.parent.ui.comboBox_edit.addItem(tool['name'], tool_id)
            if search in tool['name'].lower():
                combo.addItem(tool['name'], tool_id)

    def add_url(self, f=None):
        new_url = self.parent.ui.lineEdit_edit_url.text()
        new_url_index = self.parent.ui.spinBox_edit.value()
        if not new_url or not new_url_index:
            self.parent.ui.textBrowser_bottom.append(self.tr('🔴 input the url and index first'))
            return
        if self.selected_tool_id:
            tool = self.tools[self.selected_tool_id]
            urls = list(self._normalize_urls(tool.get('url', [])).values())
            if new_url in urls:
                self.parent.ui.textBrowser_bottom.append(self.tr('🔴 url already exists'))
                return
            insert_index = max(0, min(new_url_index - 1, len(urls)))
            urls.insert(insert_index, new_url)
            tool['url'] = urls
            self.tooldb.save_tool(tool)
            self.tools[self.selected_tool_id] = tool
            self.load_ip()
            self.parent.ui.textBrowser_bottom.append(self.tr('🟢 add url successfully'))
        else:
            self.parent.ui.textBrowser_bottom.append(self.tr('🔴 select the tool first to edit'))

    def del_url(self,f=None):
        if self.selected_tool_id:
            tool = self.tools[self.selected_tool_id]
            tool['url'] = []
            self.tooldb.save_tool(tool)
            self.parent.ui.textBrowser_bottom.append(self.tr('🟢 all url deleted'))
        else:
            self.parent.ui.textBrowser_bottom.append(self.tr('🔴 select a tool to delete all urls'))

    def edit_command(self,f=None):
        if self.selected_tool_id:
            tool = self.tools[self.selected_tool_id]
            tool['agency'] = self.parent.ui.lineEdit_edit_agency.text()
            tool['address'] = self.parent.ui.lineEdit_edit_address.text().strip()
            tool['port'] = self.parent.ui.lineEdit_port.text()
            tool['para1'] = self.parent.ui.lineEdit_command.text()
            tool['para2'] = self.parent.ui.lineEdit_command2.text()
            tool['para3'] = self.parent.ui.lineEdit_command3.text()
            if tool['agency'] != '' and tool['port'] != '':
                self.tooldb.save_tool(tool)
                self.tools[self.selected_tool_id] = tool
                self.parent.ui.textBrowser_bottom.append(self.tr('🟢 all command updated'))
            else:
                self.parent.ui.textBrowser_bottom.append(self.tr('🔴 finish the messages first'))
        else:
            self.parent.ui.textBrowser_bottom.append(self.tr('🔴 please select the tool first'))

    def _resolve_tool_directory(self, tool, f=None):
        tool_path = tool.get('path', '')
        if not tool_path:
            return ''
        if os.path.isabs(tool_path):
            return os.path.dirname(tool_path)
        base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        return os.path.dirname(os.path.abspath(os.path.join(base_dir, tool_path)))

    def copy_folder(self, f=None):
        browser = self.parent.ui.textBrowser_bottom
        main_folder = os.path.dirname(self.exe_path)
        exe_name = os.path.basename(self.exe_path)
        self.to_path = ('tools/{}'.format(self.folder_name))
        if main_folder and exe_name:
            if not os.path.exists(self.to_path):
                shutil.copytree(main_folder, self.to_path)
                browser.append(self.tr('🟢 folder copied'))
            else:
                browser.append(self.tr('🔴 folder already exist'))
        else:
            browser.append(self.tr('🔴 select the exe file first'))

    def delete_tools(self, f=None):
        if self.selected_tool_id:
            toolname = self.tools[self.selected_tool_id]['name']
            reply = QMessageBox.question(self.parent, self.tr("delete tool"),
                                         self.tr("Are you sure you want to delete {}?").format(toolname),
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                                         )
            if reply == QMessageBox.No:
                return
            else:
                folder_path = self._resolve_tool_directory(self.tools[self.selected_tool_id])
                self.tooldb.delete_tool(self.selected_tool_id)
                if self.selected_tool_id == self.latest_tool_id:
                    self.latest_tool_id = None
                    self.tooldb.save_latest_tool(None)
                self.selected_tool_id = None
                if os.path.exists(folder_path):
                    shutil.rmtree(folder_path)
                else:
                    QMessageBox.critical(self.parent, self.tr('error'), self.tr('file to delete doesnot exist'))
                self.load_tool()
                self.parent.ui.textBrowser_bottom.append(
                    self.tr('🟢 tool {} deleted successfully,file removed'.format(toolname)))
        else:
            QMessageBox.warning(self.parent, self.tr('No tool Selected'), self.tr('Please select a tool first'))

    # automation of tool

    def exe_file_path(self, f=None):
        self.exe_path = utils.open_file(self.parent, 'select exe file', '', 'exe files(*exe)', False)
        if os.path.exists(self.exe_path):
            self.parent.ui.lineEdit_auto.setText(self.exe_path)
            self.parent.ui.textBrowser_bottom.append(self.tr('🟢 exe file path found:{}'.format(self.exe_path)))
        else:
            self.parent.ui.textBrowser_bottom.append(self.tr('🔴 exe file selection failed,try again'))
    # Linux
    def appimage_file_path(self, f=None):
        self.appimage_path = utils.open_file(self.parent,'Select Executable File','','All Files (*)',False)
        if self.appimage_path and os.path.exists(self.appimage_path):
            name = os.path.basename(self.appimage_path)
            if self.to_path:
                dest_path = os.path.join(self.to_path, f"{name}")
                try:
                    shutil.copy2(self.appimage_path, dest_path)
                    self.parent.ui.textBrowser_bottom.append(
                        self.tr(f'🟢 AppImage copied to: {dest_path}')
                    )
                except Exception as e:
                    self.parent.ui.textBrowser_bottom.append(
                        self.tr(f'🔴 Failed to copy AppImage: {str(e)}')
                    )
            else:
                self.parent.ui.textBrowser_bottom.append(
                    self.tr(f'🟢 AppImage file path selected: {self.appimage_path}')
                )
        else:
            self.parent.ui.textBrowser_bottom.append(
                self.tr('🔴 AppImage file selection failed, try again.')
            )

    def cmd_analysis(self, f=None):
        self.cmd_path = utils.open_file(self.parent, 'select cmd file', '', 'cmd files(*cmd)', False)
        self.port = 0
        self.agency = self.para1 = self.para2 = self.para3 = self.folder_name = ''
        if not os.path.exists(self.exe_path):
            self.parent.ui.textBrowser_bottom.append(self.tr('🔴 select the exe file first'))
            return
        else:
            self.parent.ui.textBrowser_bottom.append(self.tr(f'✅ exe file path found:{self.exe_path}'))
            dict = utils.parse_cmd_file(self.cmd_path, self.exe_path)
            self.agency, self.port, self.para1, self.para2, self.para3, self.folder_name = dict.values()
            self.parent.ui.textBrowser_bottom.append(
                self.tr(f'✅ cmd file {self.cmd_path} analysis succeeded:\n'f'agency:{self.agency}\nport:{self.port}\n'f'para1:{self.para1}, para2:{self.para2}, para3:{self.para3},folder name:{self.folder_name}'))
    # Linux and Windows
    def add_auto_tool(self, f=None):
        self.urls = []
        if (not getattr(self, "exe_path", None)) or (not getattr(self, "cmd_path", None)):
            self.parent.ui.textBrowser_bottom.append(self.tr('❌ select exe and cmd file first'))
        else:
            main_folder = os.path.dirname(self.exe_path)
            ip_folder = '{}/ip_Update'.format(main_folder)
            tool_name = ''
            if current_os == 'Linux':
                tool_name = os.path.basename(self.appimage_path)
            elif current_os == 'Windows':
                tool_name = os.path.basename(self.exe_path)
            self.urls = utils.dat_analysis(ip_folder)
            self.parent.ui.textBrowser_bottom.append(self.tr('✅ urls found:'))
            for i in self.urls:
                self.parent.ui.textBrowser_bottom.append(i)
            tool_path = 'tools/{}/{}'.format(self.folder_name, tool_name)
            dict = {
                'name': tool_name, 'path': tool_path, 'url': self.urls, 'agency': self.agency, 'port': self.port,
                'para1': self.para1,'para2': self.para2, 'para3': self.para3, 'launch_times': 0, 'latest_launch_time': ''
            }
            if not os.path.exists(tool_path):
                self.copy_folder()
                tool_id = self.tooldb.save_tool(dict)
                self.load_tool()
            else:
                QMessageBox.critical(self.parent, self.tr('error'), self.tr('tool already exist,please delete it to reinstall'))
                return False
            self.parent.ui.textBrowser_bottom.append(self.tr('✅ successfully added tool {}'.format(tool_name)))
            if not self.latest_tool_id:
                self.latest_tool_id = tool_id
                self.tooldb.save_latest_tool(tool_id)

    def tool_receiver(self, data: dict):
        if data['aim'] == 'tool_system' and data['op'] == 'get_tool':
            if self.selected_tool_id:
                tool = self.tools[self.selected_tool_id]
                self.latest_tool_id = self.selected_tool_id
                self.tooldb.save_latest_tool(self.latest_tool_id)
                self.tooldb.update_launch(self.selected_tool_id)
                response = {'aim': 'app_system', 'op': 'send_tool', 'data': tool}
            else:
                response = {'aim': 'app_system', 'op': 'send_tool', 'data': {}}
            self.tool_signal.emit(response)

    # ip issues

    def load_ip(self, f=None):
        combo = self.parent.ui.comboBox_ip
        combo.clear()
        if self.selected_tool_id:
            urls = self._normalize_urls(self.tools[self.selected_tool_id]['url'])
            for url in urls.values():
                combo.addItem(url)
        if combo.count() > 0:
            self.ip_index = 0
            combo.setCurrentIndex(0)
        else:
            self.ip_index = None
        self.schedule_qrcode_view_update()

    def select_ip(self, f=None):
        self.ip_index = self.parent.ui.comboBox_ip.currentIndex()
        self.parent.ui.textBrowser_bottom.append('url selected')
        self.schedule_qrcode_view_update()

    def clear_qrcode_view(self, f=None):
        scene = QGraphicsScene(self.parent.ui.graphicsView_qrcode)
        self.parent.ui.graphicsView_qrcode.setScene(scene)

    def build_qrcode_image(self, text, box_size=8, border=2, f=None):
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=box_size,
            border=border,
        )
        qr.add_data(text)
        qr.make(fit=True)
        image = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        return buffer.getvalue()

    def _set_qrcode_payload(self, payload, label='', f=None):
        self.qrcode_payload = payload or ''
        self.qrcode_payload_label = label or ''

    def _get_selected_url(self, f=None):
        return self.parent.ui.comboBox_ip.currentText().strip()

    def _render_qrcode_payload(self, payload, label='', f=None):
        self.parent.ui.graphicsView_qrcode.show()
        self._set_qrcode_payload(payload, label)
        if not payload:
            self.clear_qrcode_view()
            return
        image_data = self.build_qrcode_image(payload)
        utils.display_image(self.parent.ui.graphicsView_qrcode, image_data, 120, 120)

    def _decode_config_payload(self, content, f=None):
        for encoding in ('utf-8', 'utf-8-sig', 'latin-1'):
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        return content.decode('utf-8', errors='replace')

    async def fetch_config_payload(self, url, f=None):
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=False),
            timeout=timeout,
        ) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    raise Exception(f"HTTP {resp.status}")
                content = await resp.read()
        return self._decode_config_payload(content)

    def show_large_qrcode(self, f=None):
        payload = self.qrcode_payload.strip()
        if not payload:
            return
        image_data = self.build_qrcode_image(payload, box_size=32, border=4)
        image = QImage.fromData(image_data)
        if image.isNull():
            return
        pixmap = QPixmap.fromImage(image).scaled(
            1024,
            1024,
            Qt.KeepAspectRatio,
            Qt.FastTransformation
        )
        dialog = QDialog(self.parent)
        title = self.qrcode_payload_label or self.tr("QR Code Preview")
        dialog.setWindowTitle(title)
        dialog.setMinimumSize(1024, 1024)
        dialog.resize(1024, 1024)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        label = QLabel(dialog)
        label.setAlignment(Qt.AlignCenter)
        label.setPixmap(pixmap)
        layout.addWidget(label)
        self.qrcode_preview = dialog
        dialog.show()

    def schedule_qrcode_view_update(self, f=None):
        url = self._get_selected_url()
        if not url:
            self._render_qrcode_payload('', '')
            return
        if self.parent.ui.radioButton_qrcode_url.isChecked():
            self._render_qrcode_payload(url, self.tr("URL QR Code"))
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            QTimer.singleShot(0, self.schedule_qrcode_view_update)
            return
        loop.create_task(self.update_qrcode_view())

    async def update_qrcode_view(self, f=None):
        self.qrcode_request_token += 1
        request_token = self.qrcode_request_token
        url = self._get_selected_url()
        if not url:
            self._render_qrcode_payload('', '')
            return
        if self.parent.ui.radioButton_qrcode_url.isChecked():
            self._render_qrcode_payload(url, self.tr("URL QR Code"))
            return
        self._set_qrcode_payload('', self.tr("Config QR Code"))
        scene = QGraphicsScene(self.parent.ui.graphicsView_qrcode)
        scene.addText(self.tr("loading config..."))
        self.parent.ui.graphicsView_qrcode.setScene(scene)
        try:
            payload = await self.fetch_config_payload(url)
        except Exception as e:
            if request_token != self.qrcode_request_token:
                return
            self._set_qrcode_payload('', self.tr("Config QR Code"))
            self.clear_qrcode_view()
            self.parent.ui.textBrowser_bottom.append(
                self.tr(f"[QR] failed to load config for qr code: {e}")
            )
            return
        if request_token != self.qrcode_request_token:
            return
        if not payload.strip():
            self._render_qrcode_payload('', self.tr("Config QR Code"))
            self.parent.ui.textBrowser_bottom.append(
                self.tr("[QR] downloaded config is empty")
            )
            return
        self._render_qrcode_payload(payload, self.tr("Config QR Code"))

    def _normalize_urls(self, urls_raw) -> dict:
        if isinstance(urls_raw, dict):
            return {k: v for k, v in urls_raw.items() if v}
        elif isinstance(urls_raw, list):
            return {i: u for i, u in enumerate(urls_raw) if u}
        return {}

    async def update_ip(self):
        if self.selected_tool_id is None or self.ip_index is None:
            QMessageBox.warning(self.parent, self.tr('error'), self.tr('please select the tool and url first'))
            return False
        exe_dir = self._resolve_tool_directory(self.tools[self.selected_tool_id])
        config_path = os.path.join(exe_dir, 'config.json')
        urls = self._normalize_urls(self.tools[self.selected_tool_id]['url'])
        url = list(urls.values())[self.ip_index]
        QTimer.singleShot(0, lambda: self.parent.ui.textBrowser_bottom.append(
            self.tr(f"⏳ downloading config file from {url}")
        ))
        return await self.async_download_config(url, config_path)

    async def async_download_config(self, url, config_path) -> bool:
        content = await self.fetch_config_payload(url)
        if os.path.exists(config_path):
            os.remove(config_path)
        with open(config_path, 'w', encoding='utf-8', newline='') as f:
            f.write(content)
        return True

    async def update_all_ip(self):
        success_count = 0
        fail_log = [] 
        for tool_id, tool in self.tools.items():
            tool_name = tool['name']
            urls = self._normalize_urls(tool.get('url', []))
            if not urls:
                fail_log.append(f"⚠️ {tool_name}: no urls configured")
                continue
            exe_dir = self._resolve_tool_directory(tool)
            config_path = os.path.join(exe_dir, 'config.json')
            updated = False
            for index, url in urls.items():
                QTimer.singleShot(0, lambda t=tool_name, u=url: 
                    self.parent.ui.textBrowser_bottom.append(self.tr(f"⏳ [{t}] trying: {u}"))
                )
                try:
                    ok = await asyncio.wait_for(
                        self.async_download_config(url, config_path),
                        timeout=15  
                    )
                except asyncio.TimeoutError:
                    fail_log.append(f"🔴 [{tool_name}] timeout: {url}")
                    continue
                except Exception as e:
                    fail_log.append(f"🔴 [{tool_name}] error: {url} → {e}")
                    continue
                if ok:
                    success_count += 1
                    updated = True
                    QTimer.singleShot(0, lambda t=tool_name, u=url:
                        self.parent.ui.textBrowser_bottom.append(self.tr(f"✅ [{t}] updated from: {u}"))
                    )
                    break  
                else:
                    fail_log.append(f"🔴 [{tool_name}] failed: {url}")
            if not updated:
                fail_log.append(f"❌ [{tool_name}]: all urls failed")
        QTimer.singleShot(0, lambda: self.parent.ui.textBrowser_bottom.append(
            self.tr(f"✅ update finished: {success_count} succeeded, {len(fail_log)} failed")
        ))
        for msg in fail_log:
            QTimer.singleShot(0, lambda m=msg:self.parent.ui.textBrowser_bottom.append(m))
