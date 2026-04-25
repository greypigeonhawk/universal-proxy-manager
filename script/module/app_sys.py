import os, subprocess, sys,platform
from PyQt5.QtWidgets import QMessageBox, QTableWidgetItem
from PyQt5.QtCore import pyqtSignal, QObject

from script.utils.util_manager import utils
from script.utils.util_web import Toast
from script.utils.file_manager import AppLauncherDB, ToolConfigDB

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from script.window.mainwindow import MainWindow

current_os = platform.system()

@utils.decorate_all_methods(utils.show_error_messagebox)
class app_system(QObject):

    app_signal = pyqtSignal(dict)

    # basic issues

    def __init__(self, parent, f=None):
        super().__init__()
        self.parent: MainWindow = parent
        self.apps = {}
        self.latest_app_id = None
        self.selected_app_id = None
        self.db_path = "data/app_launcher.db"
        self.db = AppLauncherDB(self.db_path)
        self.tool_dbpath = "data/tools.db"
        self.tooldb = ToolConfigDB(self.tool_dbpath)
        self.img_path = ''

        self.tool = {}
        self.proxy = ''
        self.proxy_name = ''
        self.app_signal.connect(self.app_receiver)

    def app_ui_signal(self, f=None):
        self.parent.ui.comboBox_app.currentIndexChanged.connect(self.select_app)
        self.parent.ui.tableWidget.doubleClicked.connect(self.select_app)
        self.parent.ui.pushButton_app_add.clicked.connect(self.add_app)
        self.parent.ui.lineEdit_app.textChanged.connect(self.search_app)
        self.parent.ui.pushButton_app_delete.clicked.connect(self.delete_app)
        self.parent.ui.pushButton_app_launch.clicked.connect(self.launch_app)
        self.parent.ui.pushButton_tool.clicked.connect(self.launch_tool)
        self.parent.ui.pushButton_tool_off.clicked.connect(self.stop_proxy)
        self.parent.ui.pushButton_app_addimage.clicked.connect(self.add_icon)

    # app storage and manage sys

    def load_app(self, f=None):
        self.db.create_tables()
        all_apps = self.db.get_all_apps()
        self.apps = {app['id']: app for app in all_apps}
        self.latest_app_id = self.db.get_latest_app_id()
        self.selected_app_id = self.latest_app_id
        combo = self.parent.ui.comboBox_app
        combo.clear()
        for app in all_apps:
            combo.addItem(app['name'], app['id']) 
        if self.latest_app_id and self.latest_app_id in self.apps:
            index = combo.findData(self.latest_app_id)
            if index != -1:
                combo.setCurrentIndex(index)
                utils.display_image(self.parent.ui.graphicsView_app,self.apps[self.latest_app_id]['icon'],160, 160)

    def add_app(self, f=None):
        exe_path = utils.open_file(self.parent,self.tr('Select Application File'),'',self.tr('All Files (*)'),False)
        exe_path = utils.resolve_lnk_to_exe(exe_path)
        if not exe_path:
            return
        if not os.access(exe_path, os.X_OK):
            self.parent.ui.textBrowser_bottom.append(self.tr('❌ Selected file is not executable'))
            return
        name = os.path.basename(exe_path)
        icon_data = None
        if current_os == 'Linux':
            default_icon_path = utils.get_icon_from_desktop(exe_path)
            if not default_icon_path:
                default_icon_path = "assets/icons/icon2.ico"
            if os.path.exists(default_icon_path):
                with open(default_icon_path, "rb") as f:
                    icon_data = f.read()
        elif current_os == 'Windows':
            icon_data = utils.extract_icon(exe_path)
        utils.display_image(self.parent.ui.graphicsView_app, icon_data, 160, 160)
        app_id = self.db.add_app(name, exe_path, icon_data)
        if app_id:
            self.parent.ui.textBrowser_bottom.append(self.tr('✅ App added successfully'))
            if self.latest_app_id is None:
                self.update_latest_app(app_id)
            self.load_app()
        else:
            self.parent.ui.textBrowser_bottom.append(self.tr('❌ App already exists'))

    def select_app(self, f=None):
        combo = self.parent.ui.comboBox_app
        if combo.currentIndex() >= 0:
            self.selected_app_id = combo.currentData()
        if self.selected_app_id:
            self.parent.ui.textBrowser_bottom.append(self.tr('🟢 app selected:{}'.format(self.apps[self.selected_app_id]['name'])))
            utils.display_image(self.parent.ui.graphicsView_app, self.apps[self.selected_app_id]['icon'], 160, 160)

    def delete_app(self, f=None):
        if self.selected_app_id:
            self.db.delete_app(self.selected_app_id)
            if self.selected_app_id == self.latest_app_id:
                self.latest_app_id = None
            self.selected_app_id = None
            self.load_app()
            self.parent.ui.textBrowser_bottom.append(self.tr('✅app deleted successfully'))
        else:
            QMessageBox.warning(self.parent, self.tr('No App Selected'),self.tr('Please select an app first'))

    def update_latest_app(self, id, f=None):
        self.latest_app_id = id
        self.db.save_latest_app(id)

    def add_icon(self,data = None):
        if self.selected_app_id is None:
            QMessageBox.warning(self.parent, self.tr('no app selected'), self.tr('please select an app needs to add image'))
            return
        file_path = utils.open_file(self.parent,self.tr('Select Application icon'),'',self.tr("image file (*.png *.jpg *.bmp *.ico *.gif)"),False)
        if not file_path:
            return  
        try:
            with open(file_path, "rb") as file:
                icon_data = file.read()
            self.db.update_app_icon(self.selected_app_id, icon_data)
            Toast(self.tr('image added for the app'), 3000, parent=self.parent).show()
        except Exception as e:
            QMessageBox.critical(self.parent, self.tr('error'), self.tr(f"icon saving failed:{str(e)}"))

    # app and proxy issues

    def launch_app(self, f=None):
        if self.selected_app_id and self.selected_app_id in self.apps:
            app_path = self.apps[self.selected_app_id]['path']
            try:
                if not self.parent.ui.checkBox_app_auto.isChecked():
                    if current_os == 'Linux':
                        subprocess.Popen(['xdg-open', app_path])
                    elif current_os == 'Windows':
                        os.startfile(app_path)
                    self.parent.ui.textBrowser_bottom.append(self.tr('🟢app {} started without proxy').format(app_path))
                else:
                    data = {'aim': 'tool_system','op': 'get_tool',}
                    self.app_signal.emit(data)
                    if self.tool:
                        self.launch_proxy()
                        self.proxy_app()
                        self.parent.ui.textBrowser_bottom.append(self.tr('🟢app {} started with proxy'.format(app_path)))
                    else:
                        QMessageBox.warning(self.parent, self.tr('connection error'), self.tr('no info received from tool system'))
                    pass
                self.db.update_launch_stats(self.selected_app_id)
                self.update_latest_app(self.selected_app_id)
                self.load_app()
            except Exception as e:
                QMessageBox.warning(self.parent, self.tr('Launch Failed'), self.tr(f'Could not launch app: {str(e)}'))

    def search_app(self, f=None):
        combo = self.parent.ui.comboBox_app
        combo.clear()
        search = self.parent.ui.lineEdit_app.text().lower()
        for app in self.apps.values():
            app_name = app['name'].lower()
            if search in app_name:
                combo.addItem(app['name'], app['id'])

    def app_receiver(self, data: dict, f=None):
        if data['aim'] == 'app_system' and data['op'] == 'send_tool':
            if self.tool:
                current_proxy = self.tool['name']
                future_proxy = data['data']['name']
                if current_proxy != future_proxy:
                    self.stop_proxy()
                    self.tool = data['data']
                else:
                    self.parent.ui.textBrowser.append(self.tr('🔴 you already launched the proxy'))
            else:
                self.tool = data['data']

    def launch_tool(self, f=None):
        data = {'aim': 'tool_system','op': 'get_tool',}
        self.app_signal.emit(data)
        self.launch_proxy()

    def combine_proxy(self, f=None):
        proxy_type = self.tool['agency']
        proxy_port = self.tool['port']
        if not proxy_type or not proxy_port:
            self.parent.ui.textBrowser_bottom.append(self.tr("❌ Error: port or type of the proxy is not set"))
            return
        proxy_prefix = f"{proxy_type}://" if proxy_type else ""
        self.proxy = f"{proxy_prefix}127.0.0.1:{proxy_port}"
        return self.proxy

    def proxy_app(self, f=None):
        if not self.proxy:
            self.combine_proxy()
        app_path = self.apps[self.selected_app_id]['path']
        app_name = self.apps[self.selected_app_id]['name']
        try:
            if current_os == 'Linux':
                env = os.environ.copy()
                if self.proxy.startswith(('http://', 'https://')):
                    env["http_proxy"] = self.proxy
                    env["https_proxy"] = self.proxy
                else:
                    env["all_proxy"] = self.proxy
                if app_path.endswith('.desktop'):
                    command = ['xdg-open', app_path]
                else:
                    command = [app_path]
                subprocess.Popen(command, env=env)
            elif current_os == 'Windows':
                command = [app_path, f"--proxy-server={self.proxy}"]
                subprocess.Popen(command)
            self.parent.ui.textBrowser_bottom.append(self.tr(f"🟢 started: {app_name}, proxy: {self.proxy}"))
        except Exception as e:
            self.parent.ui.textBrowser_bottom.append(self.tr(f"🔴 start app failed: {str(e)}"))

    def normalize_path_param(self,p: str, base_dir: str,f=None) -> str:
        if not p:
            return ''
        p = p.strip()
        is_path = '/' in p or '\\' in p or p.endswith(('.json', '.conf', '.yaml', '.ini'))
        if not is_path:
            return p
        p = p.replace('\\', '/')
        if os.path.isabs(p):
            return os.path.normpath(p)
        combined = os.path.normpath(os.path.abspath(os.path.join(base_dir, p)))
        base_dir = os.path.normpath(base_dir)
        base_last = os.path.basename(base_dir)
        combined_parts = combined.split(os.sep)
        for i in range(len(combined_parts) - 1):
            if combined_parts[i] == base_last and combined_parts[i+1] == base_last:
                new_parts = combined_parts[:i+1] + combined_parts[i+2:]
                combined = os.sep.join(new_parts)
                combined = os.path.normpath(combined)
                break
        return combined

    def launch_proxy(self):
        exe_path = self.tool.get('path', '')
        if not exe_path:
            self.parent.ui.textBrowser_bottom.append(self.tr("🔴 Error: tool['path'] is empty."))
            return
        if exe_path == self.proxy_name:
            self.parent.ui.textBrowser_bottom.append(self.tr('🔴 This proxy is already working'))
            return
        if self.proxy_name:
            self.stop_proxy()
        base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        exe_abs_path = os.path.abspath(os.path.join(base_dir, exe_path))
        working_dir = os.path.dirname(exe_abs_path)
        if not os.path.exists(exe_abs_path):
            self.parent.ui.textBrowser_bottom.append(self.tr(f"🔴 Error: program not found: {exe_abs_path}"))
            return
        raw_params = [self.tool.get('para1', ''), self.tool.get('para2', ''), self.tool.get('para3', '')]
        valid_params = [self.normalize_path_param(p, working_dir) for p in raw_params if p]
        command = [exe_abs_path] + valid_params
        self.stop_known_proxy_processes(
            exclude_process=os.path.basename(exe_abs_path),
            ports_to_clear=[self.tool.get('port')]
        )
        self.combine_proxy()
        self.emit_msg()
        if os.path.basename(exe_abs_path).lower() == 'mieru.exe' and valid_params[:2] == ['apply', 'config']:
            apply_result = subprocess.run(
                command,
                cwd=working_dir,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0) if current_os == 'Windows' else 0
            )
            if apply_result.stdout:
                self.parent.terminal.append_text(apply_result.stdout)
            if apply_result.stderr:
                self.parent.terminal.append_text(apply_result.stderr)
            if apply_result.returncode != 0:
                self.parent.ui.textBrowser_bottom.append(
                    self.tr(f"mieru apply config failed: exit code {apply_result.returncode}")
                )
                return
            command = [exe_abs_path, 'start']
        self.parent.terminal.run_subprocess(args=command, cwd=working_dir, shell=False)
        self.proxy_name = exe_path
        self.parent.ui.textBrowser_bottom.append(
            self.tr(f"🟢 Launched: {os.path.basename(exe_abs_path)}\n"
                    f"Parameters: {' '.join(valid_params)}\n"
                    f"Working path: {working_dir}"))

    def stop_proxy(self, f=None):
        self.parent.func.stop_global_proxy()
        if self.parent.ui.checkBox_system.isChecked():
            self.parent.func.disable_system_proxy()
            self.parent.func._set_checkbox_state(self.parent.ui.checkBox_system, False)
        self.parent.ui.label_test_proxy.setText('proxy:None')
        self.parent.func._set_proxy_footer_status('off', '')
        if self.proxy_name != '':
            process_name = os.path.basename(self.proxy_name)
            if current_os == 'Linux':
                result = subprocess.run(["pkill", "-9", "-f", process_name], capture_output=True, text=True)
            elif current_os == 'Windows':
                result = subprocess.run(["taskkill", "/f", "/im", process_name], capture_output=True, text=True)
            if result.returncode == 0:
                self.parent.ui.textBrowser_bottom.append(self.tr(f"{process_name} stopped"))
                self.proxy_name = ''
                self.proxy = ''
                self.emit_msg()
            else:
                error_msg = result.stderr if result.stderr else result.stdout
                self.parent.ui.textBrowser_bottom.append(self.tr(f"stopping proxy failed: {error_msg}"))

    def stop_known_proxy_processes(self, exclude_process='', ports_to_clear=None, f=None):
        if current_os != 'Windows':
            return
        known_processes = [
            'juicity-client.exe',
            'xray.exe',
            'sing-box.exe',
            'shadowquic.exe',
            'naive.exe',
            'mieru.exe',
            'hysteria2.exe',
            'hysteria-tun-windows-6.0-386.exe',
            'clash.meta-windows-386.exe',
        ]
        current_pid = os.getpid()
        for port in ports_to_clear or []:
            if not port:
                continue
            try:
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     f"Get-NetTCPConnection -LocalPort {int(port)} -ErrorAction SilentlyContinue | "
                     f"Where-Object {{$_.State -eq 'Listen' -and $_.OwningProcess -ne {current_pid}}} | "
                     "ForEach-Object { taskkill /f /t /pid $_.OwningProcess | Out-Null; "
                     "Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"],
                    capture_output=True,
                    text=True,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                )
                if result.stderr:
                    self.parent.ui.textBrowser_bottom.append(result.stderr.strip())
            except Exception as e:
                self.parent.ui.textBrowser_bottom.append(self.tr(f"clear proxy port failed: {e}"))
        exclude_process = (exclude_process or '').lower()
        for process_name in known_processes:
            if process_name.lower() == exclude_process:
                continue
            subprocess.run(
                ["taskkill", "/f", "/im", process_name],
                capture_output=True,
                text=True,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            )

    def emit_msg(self, f=None):
        if not self.proxy:
            self.proxy = self.combine_proxy()
        data = {'aim': 'func_system','op': 'send_proxy','data': self.proxy,}
        data2 = {'aim': 'web_system','op': 'send_proxy','data': self.proxy,}
        self.app_signal.emit(data)
        self.app_signal.emit(data2)
