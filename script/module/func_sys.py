import os,stat,subprocess,psutil,math,yaml,platform,shutil
from datetime import datetime
from PyQt5.QtCore import pyqtSignal,QObject,pyqtSlot,QTimer
from PyQt5.QtWidgets import QMessageBox
from script.utils.util_manager import utils,SubprocessReaderThread
from script.utils.util_web import NetworkTester
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from script.window.mainwindow import MainWindow

current_os = platform.system()

@utils.decorate_all_methods(utils.show_error_messagebox)
class func_system(QObject):

    func_signal = pyqtSignal(dict)

    def __init__(self, parent, f=None):
        super().__init__(parent)
        self.parent: 'MainWindow' = parent
        self.proxy = ''
        self.func_signal.connect(self.func_receiver)
        self.tester = NetworkTester()
        self.subprocess = SubprocessReaderThread
        self._latest_info = ""
        self.global_proxy = False
        self.system_proxy_enabled = False
        self.system_proxy_backup = None
        self.system_proxy_http_owned = False
        self.loading_state = False
        
        self.http_proxy = ''
        self.http_proxy_running = False
        self.http_proxy_process = None
        self.http_proxy_config_path = ''
        self.http_proxy_default_host = '127.0.0.1'
        self.privoxy_relative_path = os.path.join('core', 'Privoxy', 'privoxy.exe' if current_os == 'Windows' else 'privoxy')

        self.interface = None
        self.interval_ms = 1000
        self.prev_counters = self.get_net_counters()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_speed)
        self.timer.start(self.interval_ms)
        self._set_proxy_footer_status('off', '')
        self._set_tun_footer_status('off', 'Off')
        self._set_system_proxy_status(False)
        self._set_http_footer_status('off', 'Off')

    def func_ui_signals(self, f=None):
        self.parent.ui.pushButton_test.clicked.connect(self.start_test)
        self.parent.ui.pushButton_test_stop.clicked.connect(self.tester.cancel_all)
        self.parent.ui.checkbox_global.toggled.connect(lambda checked: self.start_global_proxy() if checked else self.stop_global_proxy())
        self.parent.ui.checkBox_system.toggled.connect(lambda checked: self.enable_system_proxy() if checked else self.disable_system_proxy())
        # self.parent.ui.checkbox_global_os.stateChanged.connect(lambda state: self.set_global_permanent() if state else self.remove_global_proxy())
        self.tester.testError.connect(self._on_error)
        self.tester.speedTestProgress.connect(self._on_speed_progress)
        self.tester.speedTestFinished.connect(self._on_speed_finished)
        self.tester.pingTestProgress.connect(self._on_ping_progress)
        self.tester.pingTestFinished.connect(self._on_ping_finished)
        self.tester.latencyTestProgress.connect(self._on_latency_progress)
        self.tester.latencyTestFinished.connect(self._on_latency_finished)
        self.tester.geolocationTestProgress.connect(self._on_geolocation_progress)
        self.tester.geolocationTestFinished.connect(self._on_geolocation_finished)
        self.parent.ui.checkBox_http_socket.toggled.connect(lambda checked: self.start_http_bridge() if checked else self.stop_http_bridge())

    # global tun system issues

    # Linux and windows
    def start_global_proxy(self, f=None):
        clash_path = ''
        if current_os == 'Linux':
            clash_path = os.path.abspath('core/clash/clash-linux')
        elif current_os == 'Windows':
            clash_path = os.path.abspath('core/clash/clash-win64.exe')
        config_path = os.path.abspath('core/clash/config1.yaml')
        if not (os.path.exists(clash_path) and os.path.exists(config_path)):
            self.parent.ui.textBrowser_bottom.append(self.tr("❌ Clash file not found"))
            return
        if not os.access(clash_path, os.X_OK):
            os.chmod(clash_path, os.stat(clash_path).st_mode | stat.S_IEXEC)
        try:
            cmd = ['pkexec', clash_path, '-f', config_path] if current_os == 'Linux' else [clash_path, '-f', config_path]
            self.parent.terminal.run_subprocess(args=cmd, cwd=os.path.dirname(clash_path))
            self.parent.ui.textBrowser_bottom.append(self.tr("✅ Clash has launched"))
            self.global_proxy = True
            self._set_tun_footer_status('running', 'On')
        except Exception as e:
            self.parent.ui.checkbox_global.setChecked(False)
            self._set_tun_footer_status('error', 'Error')
            self.parent.ui.textBrowser_bottom.append(self.tr(f"❌ launch failed: {e}")) #l#
    # Linux and windows
    def stop_global_proxy(self, f=None):
        if not self.global_proxy:
            self.parent.ui.textBrowser_bottom.append(self.tr("ℹ️ Clash is not running"))
            return
        try:
            if current_os == 'Linux':
                result = subprocess.run(["pkill", "-f", "clash-linux"],capture_output=True,text=True)
                if result.returncode != 0:
                    subprocess.run(["pkill", "-9", "-f", "clash-linux"],capture_output=True)
            elif current_os == 'Windows':
                subprocess.run(["taskkill", "/f", "/im", "clash-win64.exe"], capture_output=True)
            self.parent.ui.checkbox_global.setChecked(False)
            self.global_proxy = False
            self.parent.ui.textBrowser_bottom.append(self.tr("✅ Clash has been closed"))
            self._set_tun_footer_status('off', 'Off')
        except Exception as e:
            self._set_tun_footer_status('error', 'Error')
            self.parent.ui.textBrowser_bottom.append(self.tr(f"❌ Failed to stop Clash: {e}"))
    # Linux
    def set_global_permanent(self, f=None):
        if not self.proxy:
            QMessageBox.information(self.parent, self.tr('error'), self.tr('no tool launched'))
            return
        try:
            proxy_conf = f"""
    [proxy]
    method=manual
    socks=127.0.0.1:1080
    """
            conf_path = "/etc/NetworkManager/conf.d/proxy.conf"
            import tempfile
            with tempfile.NamedTemporaryFile('w', delete=False) as tmp:
                tmp.write(proxy_conf)
                tmp_path = tmp.name
            subprocess.run(["pkexec", "cp", tmp_path, conf_path], check=True)
            os.unlink(tmp_path)
            subprocess.run(["pkexec", "systemctl", "restart", "NetworkManager"], check=True)
            self.reconnect_network()
            self.parent.ui.textBrowser_bottom.append(self.tr('✅global socks5 launched'))
        except subprocess.CalledProcessError as e:
            QMessageBox.critical(self.parent, self.tr("error"), self.tr(f"operation failed:{e}"))
    # Linux
    def remove_global_proxy(self, f=None):
        try:
            conf_path = "/etc/NetworkManager/conf.d/proxy.conf"
            subprocess.run(["pkexec", "rm", "-f", conf_path], check=True)
            subprocess.run(["pkexec", "systemctl", "restart", "NetworkManager"], check=True)
            self.reconnect_network()
            self.parent.ui.textBrowser_bottom.append(self.tr('✅successfully return to direct connection'))
        except subprocess.CalledProcessError as e:
            QMessageBox.critical(self.parent, self.tr("error"), self.tr(f"operation filed:{e}"))
    # Linux
    def reconnect_network(self, use_pkexec=False, f=None):
        env = os.environ.copy()
        if "DISPLAY" not in env:
            env["DISPLAY"] = ":0"
        if "XAUTHORITY" not in env:
            env["XAUTHORITY"] = os.path.expanduser("~/.Xauthority")

        try:
            result = subprocess.run(
                ["nmcli", "-t", "-f", "NAME,DEVICE", "connection", "show", "--active"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            lines = result.stdout.strip().split("\n")
            if not lines or lines == ['']:
                QMessageBox.warning(self.parent, self.tr("warning"),
                                    self.tr("active internet activities not found, you may need to reconnect manually"))
                return
            for line in lines:
                if line.strip():
                    name, device = line.split(":")
                    cmd_down = ["nmcli", "connection", "down", name]
                    cmd_up = ["nmcli", "connection", "up", name]
                    if use_pkexec:
                        cmd_down.insert(0, "pkexec")
                        cmd_up.insert(0, "pkexec")
                    proc_down = subprocess.run(cmd_down, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
                    if proc_down.returncode != 0:
                        QMessageBox.warning(self.parent, self.tr("warning"),
                                            self.tr(f"Failed to bring down connection {name}:\n{proc_down.stderr}"))
                        return
                    proc_up = subprocess.run(cmd_up, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
                    if proc_up.returncode != 0:
                        QMessageBox.warning(self.parent, self.tr("warning"),
                                            self.tr(f"Failed to bring up connection {name}:\n{proc_up.stderr}"))
                        return
        except Exception as e:
            QMessageBox.warning(self.parent, self.tr("warning"),
                                self.tr(f"internet reconnection failed: {e}"))

    # socks to http proxy 

    def _set_checkbox_state(self, checkbox, checked, f=None):
        checkbox.blockSignals(True)
        checkbox.setChecked(checked)
        checkbox.blockSignals(False)

    def _log_bottom(self, message, f=None):
        self.parent.ui.textBrowser_bottom.append(self.tr(message))

    def _format_proxy_compact(self, proxy_str, fallback='Off', f=None):
        if not proxy_str:
            return fallback
        value = str(proxy_str).strip()
        if not value:
            return fallback
        if '://' in value:
            scheme, rest = value.split('://', 1)
            scheme = scheme.lower().strip()
        else:
            scheme, rest = 'proxy', value
        endpoint = rest.split('/', 1)[0].strip()
        if ':' not in endpoint:
            return f'{scheme}:{endpoint}'
        host, port = endpoint.rsplit(':', 1)
        host = host.strip()
        port = port.strip()
        if host in ('127.0.0.1', 'localhost', '::1'):
            return f'{scheme}:{port}'
        return f'{scheme}:{host}:{port}'

    def _set_status_label(self, label, prefix, state, detail='Off', f=None):
        dots = {'running': '🟢', 'off': '⚪', 'error': '🔴'}
        label.setText(f"{dots.get(state, '⚪')}{prefix}:{detail}")

    def _set_proxy_footer_status(self, state, proxy_text='', f=None):
        detail = self._format_proxy_compact(proxy_text, fallback='socks5:Off') if proxy_text else 'socks5:Off'
        self._set_status_label(self.parent.ui.label_bottom_proxy, '', state, detail)

    def _set_tun_footer_status(self, state, detail='Off', f=None):
        self._set_status_label(self.parent.ui.label_bottom_tun, 'tun', state, detail)

    def _set_system_proxy_status(self, enabled, proxy_text='', f=None):
        self.system_proxy_enabled = enabled
        status = 'On' if enabled else 'Off'
        self._set_status_label(
            self.parent.ui.label_bottom_sysproxy,
            'sys',
            'running' if enabled else 'off',
            status,
        )

    def _set_http_footer_status(self, state, proxy_text='', f=None):
        detail = self._format_proxy_compact(proxy_text, fallback='http:Off') if proxy_text else 'http:Off'
        self._set_status_label(self.parent.ui.label_bottom_http, '', state, detail)

    def _set_status_label(self, label, prefix, state, detail='Off', f=None):
        dots = {'running': '\U0001F7E2', 'off': '\u26AA', 'error': '\U0001F534'}
        text = detail if not prefix else f"{prefix}:{detail}"
        label.setText(dots.get(state, '\u26AA') + text)

    def _run_command(self, command, check=True, f=None):
        startupinfo = None
        creationflags = 0
        if current_os == 'Windows':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
            creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        return subprocess.run(
            command,
            check=check,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )

    def _capture_proxy_env(self, f=None):
        keys = (
            'all_proxy', 'ALL_PROXY',
            'http_proxy', 'HTTP_PROXY',
            'https_proxy', 'HTTPS_PROXY',
        )
        return {key: os.environ.get(key) for key in keys}

    def _restore_proxy_env(self, backup_env, f=None):
        for key in (
            'all_proxy', 'ALL_PROXY',
            'http_proxy', 'HTTP_PROXY',
            'https_proxy', 'HTTPS_PROXY',
        ):
            value = (backup_env or {}).get(key)
            if value:
                os.environ[key] = value
            else:
                os.environ.pop(key, None)

    def _sync_runtime_proxy_env(self, host, port, enabled, http_host=None, http_port=None, f=None):
        if enabled:
            socks_proxy = f'socks5://{host}:{port}'
            os.environ['all_proxy'] = socks_proxy
            os.environ['ALL_PROXY'] = socks_proxy
            if http_host and http_port:
                http_proxy = f'http://{http_host}:{http_port}'
                os.environ['http_proxy'] = http_proxy
                os.environ['HTTP_PROXY'] = http_proxy
                os.environ['https_proxy'] = http_proxy
                os.environ['HTTPS_PROXY'] = http_proxy
            else:
                os.environ['http_proxy'] = socks_proxy
                os.environ['HTTP_PROXY'] = socks_proxy
                os.environ['https_proxy'] = socks_proxy
                os.environ['HTTPS_PROXY'] = socks_proxy
        else:
            self._restore_proxy_env({})

    def _backup_windows_proxy(self, f=None):
        import winreg
        reg_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_READ) as key:
            try:
                enable_value, enable_type = winreg.QueryValueEx(key, "ProxyEnable")
            except FileNotFoundError:
                enable_value, enable_type = 0, winreg.REG_DWORD
            try:
                server_value, server_type = winreg.QueryValueEx(key, "ProxyServer")
            except FileNotFoundError:
                server_value, server_type = '', winreg.REG_SZ
            try:
                override_value, override_type = winreg.QueryValueEx(key, "ProxyOverride")
            except FileNotFoundError:
                override_value, override_type = '', winreg.REG_SZ
        return {
            'ProxyEnable': (enable_value, enable_type),
            'ProxyServer': (server_value, server_type),
            'ProxyOverride': (override_value, override_type),
        }

    def _broadcast_windows_proxy_change(self, f=None):
        import ctypes
        internet_set_option = ctypes.windll.wininet.InternetSetOptionW
        internet_set_option(0, 39, 0, 0)
        internet_set_option(0, 37, 0, 0)

    def _apply_windows_system_proxy(self, host, port, http_host=None, http_port=None, f=None):
        import winreg
        reg_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        if self.system_proxy_backup is None or self.system_proxy_backup.get('type') != 'windows':
            self.system_proxy_backup = {
                'type': 'windows',
                'values': self._backup_windows_proxy(),
            }
        proxy_parts = []
        if http_host and http_port:
            proxy_parts.extend([
                f"http={http_host}:{http_port}",
                f"https={http_host}:{http_port}",
            ])
        proxy_parts.append(f"socks={host}:{port}")
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, ";".join(proxy_parts))
            winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, "<local>")
        self._broadcast_windows_proxy_change()

    def _restore_windows_system_proxy(self, f=None):
        backup = self.system_proxy_backup or {}
        values = backup.get('values') or self._backup_windows_proxy()
        import winreg
        reg_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_SET_VALUE) as key:
            for name, (value, reg_type) in values.items():
                winreg.SetValueEx(key, name, 0, reg_type, value)
        self._broadcast_windows_proxy_change()

    def _run_gsettings(self, args, check=True, f=None):
        return self._run_command(['gsettings', *args], check=check)

    def _backup_linux_proxy(self, f=None):
        backup = {'type': 'env', 'values': self._capture_proxy_env()}
        if not shutil.which('gsettings'):
            return backup
        backup = {'type': 'linux', 'env': self._capture_proxy_env()}
        queries = {
            'mode': ['get', 'org.gnome.system.proxy', 'mode'],
            'http_host': ['get', 'org.gnome.system.proxy.http', 'host'],
            'http_port': ['get', 'org.gnome.system.proxy.http', 'port'],
            'https_host': ['get', 'org.gnome.system.proxy.https', 'host'],
            'https_port': ['get', 'org.gnome.system.proxy.https', 'port'],
            'host': ['get', 'org.gnome.system.proxy.socks', 'host'],
            'port': ['get', 'org.gnome.system.proxy.socks', 'port'],
        }
        for key, command in queries.items():
            try:
                result = self._run_gsettings(command)
                backup[key] = result.stdout.strip()
            except Exception:
                backup[key] = None
        return backup

    def _apply_linux_system_proxy(self, host, port, http_host=None, http_port=None, f=None):
        if self.system_proxy_backup is None or self.system_proxy_backup.get('type') not in ('linux', 'env'):
            self.system_proxy_backup = self._backup_linux_proxy()
        if shutil.which('gsettings'):
            self._run_gsettings(['set', 'org.gnome.system.proxy', 'mode', 'manual'])
            self._run_gsettings(['set', 'org.gnome.system.proxy.socks', 'host', host])
            self._run_gsettings(['set', 'org.gnome.system.proxy.socks', 'port', str(port)])
            if http_host and http_port:
                self._run_gsettings(['set', 'org.gnome.system.proxy.http', 'host', http_host])
                self._run_gsettings(['set', 'org.gnome.system.proxy.http', 'port', str(http_port)])
                self._run_gsettings(['set', 'org.gnome.system.proxy.https', 'host', http_host])
                self._run_gsettings(['set', 'org.gnome.system.proxy.https', 'port', str(http_port)])
        self._sync_runtime_proxy_env(host, port, True, http_host=http_host, http_port=http_port)

    def _restore_linux_system_proxy(self, f=None):
        backup = self.system_proxy_backup or {}
        if backup.get('type') == 'linux' and shutil.which('gsettings'):
            if backup.get('mode'):
                self._run_gsettings(['set', 'org.gnome.system.proxy', 'mode', backup['mode']], check=False)
            if backup.get('http_host') is not None:
                self._run_gsettings(['set', 'org.gnome.system.proxy.http', 'host', backup['http_host']], check=False)
            if backup.get('http_port') is not None:
                self._run_gsettings(['set', 'org.gnome.system.proxy.http', 'port', backup['http_port']], check=False)
            if backup.get('https_host') is not None:
                self._run_gsettings(['set', 'org.gnome.system.proxy.https', 'host', backup['https_host']], check=False)
            if backup.get('https_port') is not None:
                self._run_gsettings(['set', 'org.gnome.system.proxy.https', 'port', backup['https_port']], check=False)
            if backup.get('host') is not None:
                self._run_gsettings(['set', 'org.gnome.system.proxy.socks', 'host', backup['host']], check=False)
            if backup.get('port') is not None:
                self._run_gsettings(['set', 'org.gnome.system.proxy.socks', 'port', backup['port']], check=False)
            self._restore_proxy_env(backup.get('env'))
            return
        self._restore_proxy_env(backup.get('values') or backup.get('env'))

    def parse_http_proxy(self, proxy_str, f=None):
        if not proxy_str:
            return None, None
        proxy_str = str(proxy_str).strip()
        if not proxy_str:
            return None, None
        raw = proxy_str
        if '://' in raw:
            scheme, rest = raw.split('://', 1)
            scheme = scheme.lower().strip()
            if scheme not in ('http', 'https'):
                return None, None
            raw = rest.strip()
        raw = raw.split('/')[0].strip()
        if ':' not in raw:
            return None, None
        host, port_str = raw.rsplit(':', 1)
        host = host.strip()
        port_str = port_str.strip()
        if not host:
            return None, None
        try:
            port = int(port_str)
        except ValueError:
            return None, None
        if not (1 <= port <= 65535):
            return None, None
        return host, port

    def _ensure_http_proxy_for_system(self, auto_start_http=True, f=None):
        if self.http_proxy_running and self.http_proxy:
            http_host, http_port = self.parse_http_proxy(self.http_proxy)
            if http_host and http_port:
                return http_host, http_port
        return None, None

    def _compose_system_proxy_text(self, socks_host, socks_port, http_host=None, http_port=None, f=None):
        parts = [f"socks5://{socks_host}:{socks_port}"]
        if http_host and http_port:
            parts.append(f"http://{http_host}:{http_port}")
        return " | ".join(parts)

    def enable_system_proxy(self, auto_start_http=True, f=None):
        socks_host, socks_port = self.parse_socks_proxy(self.proxy)
        if not socks_host or not socks_port:
            self._log_bottom("[System Proxy] socks proxy is not ready yet")
            self._set_checkbox_state(self.parent.ui.checkBox_system, False)
            self._set_system_proxy_status(False)
            return
        http_host, http_port = self._ensure_http_proxy_for_system(auto_start_http=auto_start_http)
        try:
            if current_os == 'Windows':
                self._apply_windows_system_proxy(socks_host, socks_port, http_host=http_host, http_port=http_port)
            elif current_os == 'Linux':
                self._apply_linux_system_proxy(socks_host, socks_port, http_host=http_host, http_port=http_port)
            else:
                raise NotImplementedError(f"unsupported system: {current_os}")
            proxy_text = self._compose_system_proxy_text(socks_host, socks_port, http_host, http_port)
            self._set_system_proxy_status(True, proxy_text)
            self._log_bottom(f"[System Proxy] enabled: {proxy_text}")
        except Exception as e:
            self._set_checkbox_state(self.parent.ui.checkBox_system, False)
            self._set_system_proxy_status(False)
            self._log_bottom(f"[System Proxy] enable failed: {e}")

    def disable_system_proxy(self, f=None):
        try:
            if current_os == 'Windows':
                self._restore_windows_system_proxy()
            elif current_os == 'Linux':
                self._restore_linux_system_proxy()
            self._log_bottom("[System Proxy] disabled")
        except Exception as e:
            self._log_bottom(f"[System Proxy] disable failed: {e}")
        finally:
            self.system_proxy_backup = None
            self._restore_proxy_env({})
            self.system_proxy_enabled = False
            self.system_proxy_http_owned = False
            self._set_system_proxy_status(False)

    def get_privoxy_paths(self):
        base = os.path.abspath('.')
        privoxy_exe = os.path.join(base, 'core', 'Privoxy', 'privoxy.exe')
        config_path = os.path.join(base, 'core', 'Privoxy', 'config.txt')
        return privoxy_exe, config_path
    
    def get_project_root(self, f=None):
        return os.path.abspath('.')

    def parse_socks_proxy(self, proxy_str, f=None):
        if not proxy_str:
            return None, None
        proxy_str = str(proxy_str).strip()
        if not proxy_str:
            return None, None
        raw = proxy_str
        lower = raw.lower()
        if '://' in raw:
            scheme, rest = raw.split('://', 1)
            scheme = scheme.lower().strip()
            if scheme not in ('socks5', 'socks'):
                return None, None
            raw = rest.strip()
        raw = raw.split('/')[0].strip()
        if ':' not in raw:
            return None, None
        host, port_str = raw.rsplit(':', 1)
        host = host.strip()
        port_str = port_str.strip()
        if not host:
            return None, None
        try:
            port = int(port_str)
        except ValueError:
            return None, None
        if not (1 <= port <= 65535):
            return None, None
        return host, port

    def is_port_in_use(self, host, port, f=None):
        import socket
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.5)
                return sock.connect_ex((host, int(port))) == 0
        except Exception:
            return False

    def build_privoxy_config(self, http_host, http_port, socks_host, socks_port, f=None):
        return (f"listen-address  {http_host}:{http_port}\n"f"forward-socks5t / {socks_host}:{socks_port} .\n")

    def start_http_bridge(self, f=None):
        if self.http_proxy_running:
            self.parent.ui.textBrowser_bottom.append(self.tr("[HTTP] already running"))
            return
        port_text = self.parent.ui.lineEdit_http_socket.text().strip()
        if not port_text:
            port_text = '8118'
            self.parent.ui.lineEdit_http_socket.setText(port_text)
        try:
            http_port = int(port_text)
        except ValueError:
            self.parent.ui.textBrowser_bottom.append(self.tr("[HTTP] invalid port"))
            self._set_http_footer_status('error', 'Error')
            self.parent.ui.checkBox_http_socket.blockSignals(True)
            self.parent.ui.checkBox_http_socket.setChecked(False)
            self.parent.ui.checkBox_http_socket.blockSignals(False)
            return
        if not (1 <= http_port <= 65535):
            self.parent.ui.textBrowser_bottom.append(self.tr(f"[HTTP] port out of range: {http_port}"))
            self._set_http_footer_status('error', 'Error')
            self.parent.ui.checkBox_http_socket.blockSignals(True)
            self.parent.ui.checkBox_http_socket.setChecked(False)
            self.parent.ui.checkBox_http_socket.blockSignals(False)
            return
        http_host = self.http_proxy_default_host
        if self.is_port_in_use(http_host, http_port):
            self.parent.ui.textBrowser_bottom.append(
                self.tr(f"[HTTP] port already in use: {http_host}:{http_port}")
            )
            self._set_http_footer_status('error', 'Error')
            self.parent.ui.checkBox_http_socket.blockSignals(True)
            self.parent.ui.checkBox_http_socket.setChecked(False)
            self.parent.ui.checkBox_http_socket.blockSignals(False)
            return
        socks_host, socks_port = self.parse_socks_proxy(self.proxy)
        if not socks_host or not socks_port:
            self.parent.ui.textBrowser_bottom.append(
                self.tr("[HTTP] upstream socks proxy is not ready yet")
            )
            self._set_http_footer_status('off', 'Off')
            self.parent.ui.checkBox_http_socket.blockSignals(True)
            self.parent.ui.checkBox_http_socket.setChecked(False)
            self.parent.ui.checkBox_http_socket.blockSignals(False)
            return
        privoxy_path, config_path = self.get_privoxy_paths()
        if not os.path.exists(privoxy_path):
            self.parent.ui.textBrowser_bottom.append(f"[HTTP] privoxy not found: {privoxy_path}")
            return
        if not os.path.exists(config_path):
            self.parent.ui.textBrowser_bottom.append(f"[HTTP] config not found: {config_path}")
            return
        try:
            if current_os != 'Windows' and not os.access(privoxy_path, os.X_OK):
                os.chmod(privoxy_path, os.stat(privoxy_path).st_mode | stat.S_IEXEC)
        except Exception as e:
            self.parent.ui.textBrowser_bottom.append(
                self.tr(f"[HTTP] failed to chmod privoxy: {e}")
            )
            self._set_http_footer_status('error', 'Error')
            self.parent.ui.checkBox_http_socket.blockSignals(True)
            self.parent.ui.checkBox_http_socket.setChecked(False)
            self.parent.ui.checkBox_http_socket.blockSignals(False)
            return
        try:
            if current_os == 'Windows':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0
                self.parent.ui.textBrowser_bottom.append(f"[HTTP] privoxy_path = {privoxy_path}")
                self.parent.ui.textBrowser_bottom.append(f"[HTTP] config_path = {config_path}")
                self.http_proxy_process = subprocess.Popen(
                    [privoxy_path, config_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    shell=False,
                    cwd=os.path.dirname(privoxy_path),
                )
            else:
                self.http_proxy_process = subprocess.Popen(
                    [privoxy_path, self.http_proxy_config_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    cwd=os.path.dirname(privoxy_path),
                )
        except Exception as e:
            self.http_proxy_process = None
            self.parent.ui.textBrowser_bottom.append(
                self.tr(f"[HTTP] launch failed: {e}")
            )
            self._set_http_footer_status('error', 'Error')
            self.parent.ui.checkBox_http_socket.blockSignals(True)
            self.parent.ui.checkBox_http_socket.setChecked(False)
            self.parent.ui.checkBox_http_socket.blockSignals(False)
            return
        import time
        time.sleep(0.4)
        if self.http_proxy_process.poll() is not None:
            try:
                output = self.http_proxy_process.stdout.read()
            except Exception:
                output = ''
            self.parent.ui.textBrowser_bottom.append(
                self.tr(f"[HTTP] privoxy exited unexpectedly: {output}")
            )
            self.http_proxy_process = None
            self._set_http_footer_status('error', 'Error')
            self.parent.ui.checkBox_http_socket.blockSignals(True)
            self.parent.ui.checkBox_http_socket.setChecked(False)
            self.parent.ui.checkBox_http_socket.blockSignals(False)
            return
        self.http_proxy = f"http://{http_host}:{http_port}"
        self.http_proxy_running = True
        self._set_http_footer_status('running', self.http_proxy)
        self.parent.ui.textBrowser_bottom.append(
            self.tr(f"[HTTP] launched: {self.http_proxy} -> socks5://{socks_host}:{socks_port}")
        )
        if self.parent.ui.checkBox_system.isChecked() and self.system_proxy_enabled:
            self.enable_system_proxy(auto_start_http=False)

    def stop_http_bridge(self, f=None):
        if self.http_proxy_process is not None:
            try:
                if self.http_proxy_process.poll() is None:
                    self.http_proxy_process.terminate()
                    try:
                        self.http_proxy_process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        self.http_proxy_process.kill()
                        self.http_proxy_process.wait(timeout=2)
            except Exception as e:
                self.parent.ui.textBrowser_bottom.append(
                    self.tr(f"[HTTP] stop failed: {e}")
                )
        self.http_proxy_process = None
        self.http_proxy_running = False
        self.http_proxy = ''
        self._set_http_footer_status('off', 'Off')
        self.parent.ui.textBrowser_bottom.append(self.tr("[HTTP] closed"))
        if self.parent.ui.checkBox_system.isChecked() and self.system_proxy_enabled:
            self.enable_system_proxy(auto_start_http=False)

    @pyqtSlot(dict)
    def func_receiver(self, data: dict, f=None):
        if data['aim'] == 'func_system' and data['op'] == 'send_proxy':
            old_proxy = self.proxy
            self.proxy = data['data']
            if self.proxy:
                compact = self._format_proxy_compact(self.proxy, fallback='Off')
                self.parent.ui.label_test_proxy.setText(compact)
                self._set_proxy_footer_status('running', self.proxy)
            else:
                self.parent.ui.label_test_proxy.setText('proxy:none')
                self._set_proxy_footer_status('off', '')
            if self.http_proxy_running and old_proxy != self.proxy:
                self.stop_http_bridge()
                self.parent.ui.checkBox_http_socket.blockSignals(True)
                self.parent.ui.checkBox_http_socket.setChecked(False)
                self.parent.ui.checkBox_http_socket.blockSignals(False)
                self.parent.ui.textBrowser_bottom.append(self.tr("[HTTP] upstream socks changed, http bridge stopped"))
            if self.parent.ui.checkBox_system.isChecked() and old_proxy != self.proxy:
                if self.proxy:
                    self.enable_system_proxy(
                        auto_start_http=self.parent.ui.checkBox_http_socket.isChecked() or self.system_proxy_http_owned
                    )
                    self._log_bottom("[System Proxy] updated to latest app endpoint")
                else:
                    self.disable_system_proxy()
                    self._set_checkbox_state(self.parent.ui.checkBox_system, False)

    # Internet test issues

    async def start_test(self, f=None):
        proxy = ''
        url = self.parent.ui.lineEdit_test_website.text()
        if not url:
            url = 'https://google.com'
        if self.proxy and self.parent.ui.checkBox_test_proxy.isChecked():
            proxy = self.proxy
        host = self.parent.ui.lineEdit_test_host.text()
        if not host:
            host = '8.8.8.8'
        if self.parent.ui.radioButton_test_speed.isChecked():
            self._append_test_info(self.tr("speed test"), url, proxy)
            await self.tester.test_download_speed(url, proxy)
        elif self.parent.ui.radioButton_test_ping.isChecked():
            self._append_test_info(self.tr("Ping test"), host, None)
            await self.tester.test_ping(host)
        elif self.parent.ui.radioButton_test_latency.isChecked():
            self._append_test_info(self.tr("latency test"), url, proxy)
            await self.tester.test_http_latency(url, proxy)
        elif self.parent.ui.radioButton_test_location.isChecked():
            self._append_test_info(self.tr("geolocation test"), self.tr("local IP"), proxy)
            await self.tester.test_geolocation(proxy)

    def _on_error(self, message, f=None):
        self._append_test_info(f"❗ error: {message}", '', '')
    # create the progress bar for graphes
    def _make_bar(self, value, max_value, length=100, mode='speed', alert=False, f=None):
        def log_ratio(v, max_v):
            v = max(0.0, min(v, max_v * 10))
            x = v / max_v
            return math.log(1 + 9 * x) / math.log(10)
        ratio = log_ratio(value, max_value)
        filled_len = length if alert else int(length * ratio)
        empty_len = 0 if alert else length - filled_len
        if mode == 'speed':
            r = int(255 * (1 - ratio))
            g = int(255 * ratio)
            b = 128
        elif mode == 'ping':
            r = int(255 * ratio)
            g = int(255 * (1 - ratio))
            b = 64
        else:
            r = int(255 * ratio)
            g = int(200 * (1 - ratio))
            b = 80
        color = f'rgb({r},{g},{b})'
        bar_filled = f'<span style="color:{color}; font-weight:bold;">{"█" * filled_len}</span>'
        bar_empty = f'<span style="color:#333;">{"░" * empty_len}</span>'
        mark = " ❗" if alert else ""
        return f'{bar_filled}{bar_empty}{mark}'

    def _append_test_info(self, kind, url_or_host, proxy, f=None):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        parts = [f"<b>▶ type:</b> {kind}"]
        if timestamp:
            parts.append(f"<b>time:</b> {timestamp}<br>")
        if url_or_host:
            parts.append(f"<b>● address:</b> {url_or_host}")
        if proxy:
            parts.append(f"<b>proxy:</b> {proxy}")
        parts.append("<br><br>")
        self._latest_info = " ".join(parts)

    def _on_speed_progress(self, value, f=None):
        bar = self._make_bar(value, 50.0, mode='speed')
        self.parent.ui.textBrowser.clear()
        html = (self._latest_info +self.tr(f"<b>download speed:</b> {value:.2f} Mbps<br>{bar}"))
        self.parent.ui.textBrowser.insertHtml(html)

    def _on_speed_finished(self, data, f=None):
        bar = self._make_bar(data['avg'], 50.0, mode='speed')
        self.parent.ui.textBrowser.clear()
        html = (self._latest_info +
            self.tr(f"<b>download speed:</b> average {data['avg']:.2f} Mbps,max {data['max']:.2f},min {data['min']:.2f}<br>{bar}"))
        self.parent.ui.textBrowser.insertHtml(html)

    def _on_ping_progress(self, index, value, f=None):
        alert = value is None
        shown_val = self.tr("out time" if alert else f"{value:.1f} ms")
        val = 500 if alert else value
        bar = self._make_bar(val, 500, mode='ping', alert=alert)
        self.parent.ui.textBrowser.clear()
        html = (self._latest_info +self.tr(f"<b>Ping {index}:</b> {shown_val}<br>{bar}"))
        self.parent.ui.textBrowser.insertHtml(html)

    def _on_ping_finished(self, d, f=None):
        bar = self._make_bar(d['avg'], 500, mode='ping')
        self.parent.ui.textBrowser.clear()
        html = (self._latest_info +
            self.tr(f"<b>Ping finished:</b> average {d['avg']:.1f} ms,max {d['max']:.1f},min {d['min']:.1f},lost rate: {d['loss']:.1%}<br>{bar}"))
        self.parent.ui.textBrowser.insertHtml(html)

    def _on_latency_progress(self, index, value, f=None):
        alert = value is None or value >= 3500
        shown_val = self.tr("out time") if value is None else f"{value:.1f} ms"
        val = 3500 if value is None else value
        bar = self._make_bar(val, 3500, mode='latency', alert=alert)
        self.parent.ui.textBrowser.clear()
        html = (self._latest_info +self.tr(f"<b>latency:{index}:</b> {shown_val}<br>{bar}"))
        self.parent.ui.textBrowser.insertHtml(html)

    def _on_latency_finished(self, d, f=None):
        bar = self._make_bar(d['avg'], 3500, mode='latency')
        self.parent.ui.textBrowser.clear()
        html = (self._latest_info +
                self.tr(f"<b>latency test finished:</b> average {d['avg']:.1f} ms,max {d['max']:.1f},min {d['min']:.1f}<br>{bar}"))
        self.parent.ui.textBrowser.insertHtml(html)

    def _on_geolocation_progress(self, message, f=None):
        self.parent.ui.textBrowser.clear()
        html = self._latest_info + self.tr(f"<b>progress:</b> {message}<br>")
        self.parent.ui.textBrowser.insertHtml(html)

    def _on_geolocation_finished(self, data, f=None):
        self.parent.ui.textBrowser.clear()
        html = self._latest_info
        html += self.tr(f"<b>IPaddress:</b> {data['ip']}<br><b>country:</b> {data['country']}<br>")
        html += self.tr(f"<b>region:</b> {data['region']}<br><b>city:</b> {data['city']}<br>")
        html += self.tr(f"<b>Internet service provider:</b> {data['isp']}<br>")
        if data['latitude'] and data['longitude']:
            html += self.tr(f"<b>latitude and longitude:</b> {data['latitude']}, {data['longitude']}<br>")
        if data['proxy_used']:
            html += self.tr(f"<b>proxy used:</b> {data['proxy_used']}<br>")
        self.parent.ui.textBrowser.insertHtml(html)

    # speed indicator system

    def get_net_counters(self,f=None):
        if self.interface:
            counters = psutil.net_io_counters(pernic=True)
            if self.interface in counters:
                return counters[self.interface]
            else:return None
        else:return psutil.net_io_counters()

    def update_speed(self,f=None):
        current = self.get_net_counters()
        if current is None or self.prev_counters is None:
            return
        delta_download = current.bytes_recv - self.prev_counters.bytes_recv
        delta_upload = current.bytes_sent - self.prev_counters.bytes_sent
        speed_down = delta_download / (self.interval_ms / 1000) / 1024
        speed_up = delta_upload / (self.interval_ms / 1000) / 1024
        self.parent.ui.label_bottom_netspeed.setText(f"🔼:{speed_up:.2f}KB/s 🔽:{speed_down:.2f}KB/s")
        self.prev_counters = current

    # initialization system

    def write_state(self,f=None):
        if self.loading_state:
            return
        default = {
            'autostart':0,
            'autoproxy':1,
            'autolaunch':0,
            'auto_wallpaper_toggle':1,
            'self_hide':0,
            'language':'en',
            'animation':False,
            'theme':0,
            'wallpaper_time':600,
            'app_proxy':2,
            'auto_app_launch':0,
            'auto_global_proxy':0,
            'auto_system_proxy':0,
            'auto_http_proxy':0,
        }
        self.config['autostart'] = int(self.parent.ui.checkBox_set_start.checkState())
        self.config['autoproxy'] = int(self.parent.ui.checkBox_set_proxy.checkState())
        self.config['auto_wallpaper_toggle'] = int(self.parent.ui.checkBox_set_image.checkState())
        self.config['language'] = self.parent.current_lang
        self.config['animation'] = self.parent.gif_background
        self.config['wallpaper_time'] = self.parent.ui.horizontalSlider_spy.value()
        self.config['app_proxy'] = int(self.parent.ui.checkBox_app_auto.checkState())
        self.config['auto_app_launch'] = int(self.parent.ui.checkBox_set_app.checkState())
        self.config['auto_global_proxy'] = int(self.parent.ui.checkBox_set_global.checkState())
        self.config['auto_system_proxy'] = int(self.parent.ui.checkBox_auto_sysproxy.checkState())
        self.config['auto_http_proxy'] = int(self.parent.ui.checkBox_auto_http.checkState())
        self.config['self_hide'] = int(self.parent.ui.checkBox_set_hide.checkState())
        self.config['terminal_back'] = self.parent.terminal_background
        self.config = {**default, **self.config}
        with open('data/config.yaml','w') as file:
            yaml.safe_dump(self.config,file)

    def load_state(self,f = None):
        if not os.path.exists('data/config.yaml'):
            return
        self.loading_state = True
        with open('data/config.yaml','r') as file:
            self.config = yaml.safe_load(file) or {}
        default = {
            'autostart': 0,
            'autoproxy': 1,
            'auto_wallpaper_toggle': 1,
            'language': 'en',
            'animation': False,
            'wallpaper_time': 600,
            'app_proxy': 2,
            'auto_app_launch': 0,
            'auto_global_proxy': 0,
            'auto_system_proxy': 0,
            'auto_http_proxy': 0,
            'self_hide': 0,
            'terminal_back': 0,
        }
        self.config = {**default, **self.config}
        try:
            # restore checkbox visuals without triggering save hooks
            self._set_checkbox_state(self.parent.ui.checkBox_set_start, self.config.get('autostart') == 2)
            self._set_checkbox_state(self.parent.ui.checkBox_set_proxy, self.config['autoproxy'] == 2)
            self._set_checkbox_state(self.parent.ui.checkBox_set_image, self.config['auto_wallpaper_toggle'] == 2)
            self._set_checkbox_state(self.parent.ui.checkBox_app_auto, self.config['app_proxy'] == 2)
            self._set_checkbox_state(self.parent.ui.checkBox_set_app, self.config['auto_app_launch'] == 2)
            self._set_checkbox_state(self.parent.ui.checkBox_set_global, self.config['auto_global_proxy'] == 2)
            self._set_checkbox_state(self.parent.ui.checkBox_set_hide, self.config['self_hide'] == 2)
            self._set_checkbox_state(self.parent.ui.checkBox_auto_http, self.config['auto_http_proxy'] == 2)
            self._set_checkbox_state(self.parent.ui.checkBox_auto_sysproxy, self.config['auto_system_proxy'] == 2)
            self._set_checkbox_state(self.parent.ui.checkBox_http_socket, False)
            self._set_checkbox_state(self.parent.ui.checkBox_system, False)

            # config language
            if self.config['language'] == 'zh':
                self.parent.toggle_language()
            # config animation
            if self.config['animation']:
                self.parent.animation_set()
            self.parent.ui.horizontalSlider_spy.setValue(self.config['wallpaper_time'])
            # config self hide
            if self.config['self_hide'] == 2:
                QTimer.singleShot(0, self.parent.hide)
            # config terminal background
            if self.config['terminal_back'] == 1:
                self.parent.terminal_theme()
        finally:
            self.loading_state = False

        if self.config['autoproxy'] == 2:
            QTimer.singleShot(300, self.parent.apps.launch_tool)
            if self.config['auto_http_proxy'] == 2:
                QTimer.singleShot(700, lambda: self.parent.ui.checkBox_http_socket.setChecked(True))
            if self.config['auto_system_proxy'] == 2:
                QTimer.singleShot(900, lambda: self.parent.ui.checkBox_system.setChecked(True))

class downloader():

    def __init__(self):
        pass
