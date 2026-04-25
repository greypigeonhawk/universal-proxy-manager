import traceback,os,re,shlex,functools,sys,psutil,configparser,platform,queue
from typing import Dict, Any
from PyQt5.QtWidgets import QMessageBox,QFileDialog, QWidget,QGraphicsScene, QLabel, QGraphicsView
from PyQt5.QtGui import QPixmap, QImage,QStandardItem,QStandardItemModel,QTextCursor,QFont
from PyQt5.QtCore import Qt,pyqtSignal,pyqtSlot,QThread,QByteArray, QBuffer,QIODevice, QTimer

if platform.system() == 'Windows':
    import win32gui,win32ui,win32com.client

# specific utils 

class utils():
    
    # error management
    
    @staticmethod
    def show_error_messagebox(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_info = traceback.format_exc()
                msg_box = QMessageBox()
                msg_box.setIcon(QMessageBox.Critical)
                msg_box.setWindowTitle("error")
                msg_box.setText(f"function {func.__name__} error: {str(e)}")
                msg_box.setDetailedText(error_info)
                msg_box.setStandardButtons(QMessageBox.Ok)
                msg_box.exec_()
        return wrapper
    
    @staticmethod
    def decorate_all_methods(decorator):
        def wrapper(cls):
            original_methods = {}
            for name, attr in cls.__dict__.items():
                if callable(attr) and not name.startswith("__"):
                    original_methods[name] = attr
            for name, method in original_methods.items():
                if name in ["event", "timerEvent", "paintEvent", "closeEvent", "init", "new", "setState", "childEvent", "classInit"]:
                    continue
                if isinstance(method, staticmethod) or isinstance(method, classmethod):
                    continue
                if isinstance(method, pyqtSignal):
                    continue
                is_pyqt_slot = hasattr(method, '__pyqtSignature__')
                if is_pyqt_slot:
                    try:
                        slot_args = getattr(method, '__args__', ())
                        if not slot_args:
                            signature = getattr(method, '__pyqtSignature__', '')
                            if signature:
                                slot_args = (signature,)
                        original_func = getattr(method, '__func__', method)
                        decorated = decorator(original_func)
                        setattr(cls, name, pyqtSlot(*slot_args)(decorated))
                    except Exception as e:
                        setattr(cls, name, decorator(method))
                else:
                    setattr(cls, name, decorator(method))
            return cls
        return wrapper

    @staticmethod
    def get_icon_from_desktop(desktop_path):
        if not os.path.exists(desktop_path) or not desktop_path.endswith('.desktop'):
            return None
        config = configparser.ConfigParser(interpolation=None)
        config.optionxform = str
        try:
            config.read(desktop_path, encoding='utf-8')
        except Exception as e:
            return str(e)
        icon_name = None
        if 'Desktop Entry' in config:
            icon_name = config['Desktop Entry'].get('Icon')
        if not icon_name:
            return None
        if os.path.isabs(icon_name) and os.path.exists(icon_name):
            return icon_name
        desktop_dir = os.path.dirname(desktop_path)
        relative_icon = os.path.join(desktop_dir, icon_name)
        if os.path.exists(relative_icon):
            return relative_icon
        icon_dirs = [
            os.path.expanduser('~/.icons'),
            '/usr/share/icons',
            '/usr/local/share/icons',
            '/usr/share/pixmaps'  
        ]
        icon_sizes = ['scalable', '256x256', '128x128', '64x64', '48x48', '32x32', '24x24', '16x16']
        extensions = ['.png', '.svg', '.xpm', '']
        for icon_dir in icon_dirs:
            for size in icon_sizes:
                for ext in extensions:
                    possible_paths = [
                        os.path.join(icon_dir, size, 'apps', f"{icon_name}{ext}"),
                        os.path.join(icon_dir, 'hicolor', size, 'apps', f"{icon_name}{ext}"),
                        os.path.join(icon_dir, f"{icon_name}{ext}")
                    ]
                    for path in possible_paths:
                        if os.path.exists(path) and os.path.isfile(path):
                            return path
        return None

    @staticmethod
    def display_image(widget, image_data, width=128, height=128,f=None):
        if isinstance(image_data, bytes):
            image = QImage.fromData(image_data)
            if image.isNull():
                raise ValueError("cannot load image from data")
        elif isinstance(image_data, QImage):
            image = image_data
        else:
            raise TypeError("image_data must be bytes or QImage")
        pixmap = QPixmap.fromImage(image)
        scaled_pixmap = pixmap.scaled(
            width, height,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        if isinstance(widget, QGraphicsView):
            scene = QGraphicsScene()
            scene.addPixmap(scaled_pixmap)
            widget.setScene(scene)
            widget.fitInView(scene.itemsBoundingRect(), Qt.KeepAspectRatio)
        elif isinstance(widget, QLabel):
            widget.setPixmap(scaled_pixmap)
            widget.setAlignment(Qt.AlignCenter)
        else:
            raise TypeError("widget must be QGraphicsView or QLabel类型")
        widget.show()

    @staticmethod
    def extract_icon(exe_path, f=None):
        try:
            if not os.path.exists(exe_path):
                return None
            large_icons, small_icons = win32gui.ExtractIconEx(exe_path, 0)
            icon_handle = None
            max_size = 0
            if large_icons:
                for hdl in large_icons:
                    info = win32gui.GetIconInfo(hdl)
                    bmp = win32gui.GetObject(info[3])
                    size = bmp.bmWidth * bmp.bmHeight
                    if size > max_size:
                        max_size = size
                        icon_handle = hdl
            if not icon_handle and small_icons:
                for hdl in small_icons:
                    info = win32gui.GetIconInfo(hdl)
                    bmp = win32gui.GetObject(info[3])
                    size = bmp.bmWidth * bmp.bmHeight
                    if size > max_size:
                        max_size = size
                        icon_handle = hdl
            if not icon_handle:
                return None
            icon_info = win32gui.GetIconInfo(icon_handle)
            icon_bitmap = icon_info[3]
            bmp_info = win32gui.GetObject(icon_bitmap)
            width, height = bmp_info.bmWidth, bmp_info.bmHeight
            desktop_dc = win32gui.GetDC(0)
            hdc = win32ui.CreateDCFromHandle(desktop_dc)
            hbmp = win32ui.CreateBitmap()
            hbmp.CreateCompatibleBitmap(hdc, width, height)
            hdc_mem = hdc.CreateCompatibleDC()
            try:
                hdc_mem.SelectObject(hbmp)
                win32gui.DrawIconEx(hdc_mem.GetHandleOutput(), 0, 0, icon_handle, width, height, 0, None, 0x0003)
                bmpstr = hbmp.GetBitmapBits(True)
                image = QImage(bmpstr, width, height, QImage.Format_ARGB32_Premultiplied)
                byte_array = QByteArray()
                buffer = QBuffer(byte_array)
                buffer.open(QIODevice.WriteOnly)
                image.save(buffer, "PNG")
                buffer.close()
                return byte_array.data()
            finally:
                win32gui.DestroyIcon(icon_handle)
                win32gui.DeleteObject(hbmp.GetHandle())
                hdc_mem.DeleteDC()
                hdc.DeleteDC()
                win32gui.ReleaseDC(None, desktop_dc)
        except Exception as e:
            return f"error when extracting: {str(e)}"

    def resolve_lnk_to_exe(lnk_path):
        if not os.path.exists(lnk_path):
            return lnk_path
        if not lnk_path.lower().endswith('.lnk'):
            return lnk_path
        try:
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortcut(lnk_path)
            target_path = shortcut.TargetPath
            if target_path.lower().endswith('.exe') and os.path.exists(target_path):
                return target_path
            else:
                return lnk_path
        except Exception as e:
            return str(e)

    # Qt general

    @staticmethod
    def open_file(
        parent: QWidget = None,
        caption: str = "Select File",
        directory: str = "",
        filter: str = "All Files (*);;Executable Files (*.exe)",
        multiple: bool = False,
        f=None
    ):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        if multiple:
            files, _ = QFileDialog.getOpenFileNames(parent, caption, directory, filter, options=options)
            return files
        else:
            file, _ = QFileDialog.getOpenFileName(parent, caption, directory, filter, options=options)
            return file

    @staticmethod
    def open_folder(
        parent: QWidget = None,
        caption: str = "Select Folder",
        directory: str = "",
        f=None,
    ):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        folder = QFileDialog.getExistingDirectory(parent, caption, directory, options=options)
        return folder
    
    @staticmethod
    def resource_path(relative_path):
        if hasattr(sys, '_MEIPASS'):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.abspath(".")
        exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        external_path = os.path.join(exe_dir, relative_path)
        if os.path.exists(external_path):
            return external_path
        else:
            return os.path.join(base_path, relative_path)

    # text treatment
    
    @staticmethod
    def parse_cmd_file(cmd_path: str, exe_path: str) -> Dict[str, Any]:
        result = {
            'agency': '',
            'port': 0,
            'para1': '',
            'para2': '',
            'para3': '',
            'folder_name': '',
        }
        if not os.path.exists(cmd_path):
            return result
        try:
            with open(cmd_path, 'r', encoding='gbk') as f:
                lines = f.readlines()
        except Exception:
            try:
                with open(cmd_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            except: return result
        exe_name = os.path.basename(exe_path).lower()
        for line in lines:
            line_strip = line.strip()
            if 'start' in line_strip.lower() and exe_name in line_strip.lower():
                d_match = re.search(r'/D\s+"?([^"]+)"?', line_strip, re.I)
                if d_match:
                    result['folder_name'] = os.path.basename(d_match.group(1).replace('%~dp0', '').strip('\\/'))
                try:
                    parts = shlex.split(line_strip, posix=False)
                    exe_idx = next((i for i, p in enumerate(parts) if exe_name in p.lower()), -1)
                    if exe_idx != -1:
                        raw_args = parts[exe_idx + 1:]
                        clean_args = []
                        for arg in raw_args:
                            arg = arg.strip('"')
                            if '\\' in arg or '/' in arg or '%~dp0' in arg:
                                clean_args.append(os.path.basename(arg))
                            else:
                                clean_args.append(arg)
                        
                        clean_args += [''] * (3 - len(clean_args))
                        result['para1'], result['para2'], result['para3'] = clean_args[:3]
                except:
                    pass
                if not result['folder_name']:
                    folder_match = re.search(r'([^\\]+)\\[^\\]+\.json', line_strip)
                    if folder_match:
                        result['folder_name'] = folder_match.group(1)
                break
        return result
       
    @staticmethod  
    def dat_analysis(ip_folder,f=None):
        urls = []
        if not os.path.exists(ip_folder):
            return urls
        if not os.path.isdir(ip_folder):
            return urls
        url_pattern = re.compile(r'https?://[^\s]+')
        for f in os.listdir(ip_folder):
            if f.lower().endswith('.bat'):
                file_path = os.path.join(ip_folder, f)
                try:
                    with open(file_path, 'r', encoding='gbk') as f:
                        content = f.read()
                except UnicodeDecodeError:
                    print('UnicodeDecodeError')
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                    except Exception as e:
                        print(e)
                        continue
                except Exception as e:
                    print(e)
                    continue
                found_urls = url_pattern.findall(content)
                for url in found_urls:
                    if url.strip(): 
                        urls.append(url.strip())
        unique_urls = []
        seen = set()
        for url in urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)
        return unique_urls

    @staticmethod
    def dict_to_tree(data_dict: dict, tree_view):
        def build_tree(data, parent_item):
            if isinstance(data, dict):
                for key, value in data.items():
                    key_item = QStandardItem(str(key))
                    parent_item.appendRow(key_item)
                    build_tree(value, key_item)
            else:
                value_item = QStandardItem(str(data))
                parent_item.appendRow(value_item)
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(["value"])
        root_item = model.invisibleRootItem()
        build_tree(data_dict, root_item)
        tree_view.setModel(model)
        tree_view.expandAll()

    @staticmethod
    def get_self_and_children_stats(self,f=None):
        process = psutil.Process(os.getpid())
        children = process.children(recursive=True)
        processes = [process] + children
        total_cpu = 0.0
        total_mem = 0
        total_read = 0
        total_write = 0
        for p in processes:
            try:
                cpu = p.cpu_percent(interval=0.0)
                mem = p.memory_info().rss
                io = p.io_counters()
                total_cpu += cpu
                total_mem += mem
                total_read += io.read_bytes
                total_write += io.write_bytes
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return {
            "cpu": total_cpu,
            "mem": total_mem / (1024 ** 2),  # MB
            "read": total_read / (1024 ** 2),  # MB
            "write": total_write / (1024 ** 2)
        }

# redisplay the terminal to a widget

class StreamRedirector:

    def __init__(self, emit_func):
        self.emit_func = emit_func

    def write(self, text):
        if text.strip():
            self.emit_func(text)

    def flush(self):
        pass

class SubprocessReaderThread(QThread):

    output_signal = pyqtSignal(str)

    def __init__(self, args, cwd=None, shell=False, parent=None, hide_window=True):
        super().__init__(parent)
        self.args = args
        self.cwd = cwd
        self.shell = shell
        self.hide_window = hide_window

    def run(self):
        import subprocess, threading
        try:
            popen_kwargs = {
                'args': self.args,
                'cwd': self.cwd,
                'shell': self.shell,
                'stdout': subprocess.PIPE,
                'stderr': subprocess.PIPE,
                'text': True,
                'encoding': 'utf-8',
                'bufsize': 1
            }
            if sys.platform.startswith('win32') and self.hide_window:
                import subprocess
                popen_kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            process = subprocess.Popen(**popen_kwargs)

            def read_stream(stream):
                for line in iter(stream.readline, ''):
                    self.output_signal.emit(line)
                stream.close()
            threading.Thread(target=read_stream, args=(process.stdout,), daemon=True).start()
            threading.Thread(target=read_stream, args=(process.stderr,), daemon=True).start()
            process.wait()
        except Exception as e:
            self.output_signal.emit(f"[Subprocess error] {e}\n")

class TerminalCaptureHelper:

    _RE_ANSI    = re.compile(r'\x1b\[[0-9;]*[A-Za-z]|\x1b\][^\x07]*\x07')
    _RE_URL     = re.compile(r'(https?://[^\s<>"]+)')
    _RE_TIME    = re.compile(r'\b(\d{2}:\d{2}:\d{2})\b')
    _RE_DATE    = re.compile(r'\b(\d{4}-\d{2}-\d{2})\b')
    _RE_IP      = re.compile(r'\b(\d{1,3}(?:\.\d{1,3}){3})\b')
    _RE_PORT    = re.compile(r':(\d{2,5})\b')
    _RE_LEVEL   = re.compile(r'\b(INF|INFO|DBG|DEBUG|WRN|WARN|ERR|ERROR|FTL|FATAL)\b')
    _RE_PROTO   = re.compile(r'\b(TCP|UDP|SOCKS5|SOCKS|HTTP|HTTPS|TLS|DNS)\b')
    _RE_FAIL    = re.compile(r'\b(error|failed|refused|timeout|denied|fatal|warning)\b', re.I)
    _RE_SUCCESS = re.compile(r'\b(connected|success|started|launched)\b', re.I)

    def __init__(self, text_browser, max_lines=500):
        self.text_browser = text_browser
        self.max_lines = max_lines
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        self._queue = queue.Queue(maxsize=500)

        self.text_browser.setStyleSheet("""
            QTextBrowser {
                background: transparent;
                color: #CCCCCC;
                border: none;
                padding: 6px;
            }
        """)
        self.text_browser.setFont(QFont("Consolas", 13))

        sys.stdout = StreamRedirector(self.append_text)
        sys.stderr = StreamRedirector(self.append_text)

        self._flush_timer = QTimer()
        self._flush_timer.setInterval(200)
        self._flush_timer.timeout.connect(self._flush_to_ui)
        self._flush_timer.start()

    def append_text(self, text):
        clean = self._RE_ANSI.sub('', text)
        for line in clean.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                self._queue.put_nowait(line)
            except queue.Full:
                try:
                    self._queue.get_nowait()
                    self._queue.put_nowait(line)
                except:
                    pass

    @classmethod
    def _colorize(cls, line: str) -> tuple:
        is_error = bool(cls._RE_FAIL.search(line))
        is_ok    = bool(cls._RE_SUCCESS.search(line))
        if is_error:
            icon, base = '🔴', '#FF5555'
        elif is_ok:
            icon, base = '🟢', '#CCCCCC'
        else:
            icon, base = '·', '#CCCCCC'

        s = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        s = cls._RE_URL.sub(
            r"<span style='color:#61AFEF;text-decoration:underline;'>\1</span>", s)
        s = cls._RE_DATE.sub(
            r"<span style='color:#5C6370;'>\1</span>", s)       
        s = cls._RE_TIME.sub(
            r"<span style='color:#98C379;'>\1</span>", s)        
        s = cls._RE_IP.sub(
            r"<span style='color:#56B6C2;'>\1</span>", s)       
        s = cls._RE_PORT.sub(
            r":<span style='color:#E5C07B;'>\1</span>", s)      
        s = cls._RE_LEVEL.sub(
            r"<span style='color:#C678DD;font-weight:bold;'>\1</span>", s) 
        s = cls._RE_PROTO.sub(
            r"<span style='color:#E06C75;'>\1</span>", s)      

        return icon, f"<span style='color:{base};'>{s}</span>"

    def _flush_to_ui(self):
        if self._queue.empty():
            return
        lines = []
        try:
            for _ in range(20):
                lines.append(self._queue.get_nowait())
        except queue.Empty:
            pass
        if not lines:
            return
        html = '<br>'.join(
            f"<span style='white-space:pre;'>"
            f"<span style='color:#444;'>{icon} </span>{colored}"
            f"</span>"
            for line in lines
            for icon, colored in [self._colorize(line)]
        ) + '<br>'
        self.text_browser.insertHtml(html)
        self.text_browser.moveCursor(QTextCursor.End)
        self._trim_excess_lines()

    def _trim_excess_lines(self):
        doc = self.text_browser.document()
        if doc.blockCount() <= self.max_lines:
            return
        cursor = QTextCursor(doc)
        cursor.movePosition(QTextCursor.Start)
        cursor.movePosition(
            QTextCursor.Down,
            QTextCursor.KeepAnchor,
            doc.blockCount() - self.max_lines
        )
        cursor.removeSelectedText()

    def restore(self):
        self._flush_timer.stop()
        sys.stdout = self._original_stdout
        sys.stderr = self._original_stderr

    def run_subprocess(self, args, cwd=None, shell=False):
        thread = SubprocessReaderThread(args=args, cwd=cwd, shell=shell)
        thread.output_signal.connect(self.append_text)
        thread.start()
        if not hasattr(self, '_threads'):
            self._threads = []
        self._threads.append(thread)