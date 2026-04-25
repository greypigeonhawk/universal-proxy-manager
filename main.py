import sys
import traceback
import os
import asyncio
import platform
from qasync import QEventLoop
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QtMsgType, qInstallMessageHandler
from PyQt5.QtWidgets import QApplication
from script.window.mainwindow import MainWindow
from script.utils.util_web import ToastManager

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--proxy-server=socks5://127.0.0.1:1080"
script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
os.chdir(script_dir)

current_os = platform.system()

def setup_environment(): # Linux and Windows
    if current_os == 'Linux':
        linux_env = {
            "QT_OPENGL": "software",
            "QTWEBENGINE_DISABLE_GPU": "1",
            "QT_QUICK_BACKEND": "software",
            "QT_XCB_GL_INTEGRATION": "none"
        }
        for key, value in linux_env.items():
            os.environ[key] = value
    elif current_os == 'Windows':
        windows_env = {}
        for key, value in windows_env.items():
            os.environ[key] = value

def qt_message_handler(mode, context, message):
    if mode == QtMsgType.QtWarningMsg:
        print(f"Qt Warning: {message}")
    elif mode == QtMsgType.QtCriticalMsg:
        print(f"Qt Critical: {message}")
    elif mode == QtMsgType.QtFatalMsg:
        print(f"Qt Fatal: {message}")
        traceback.print_stack()
        sys.exit(1)

qInstallMessageHandler(qt_message_handler)

def excepthook(exc_type, exc_value, exc_tb):
    traceback.print_exception(exc_type, exc_value, exc_tb)
    sys.exit(1)

sys.excepthook = excepthook

def check_admin_rights():
    if current_os == 'Windows':
        import ctypes
        def is_admin():
            try:
                return ctypes.windll.shell32.IsUserAnAdmin()
            except:
                return False
        if not is_admin():
            try:
                ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", sys.executable,
                    ' '.join([f'"{arg}"' for arg in sys.argv]),
                    None, 1
                )
                return False
            except Exception as e:
                print(f"cannot get admin permission: {e}")
                return False
    return True

def main():
    setup_environment()
    if not check_admin_rights():
        sys.exit()
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon('assets/icons/profile.ico'))
    app.setStyle("Fusion")
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    window = MainWindow()
    ToastManager.set_parent(window)
    window.show()
    with loop:
        loop.run_forever()

if __name__ == "__main__":
    main()
