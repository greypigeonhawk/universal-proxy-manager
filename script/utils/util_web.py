import time,asyncio
from aiohttp_socks import ProxyConnector
from aiohttp import ClientSession, ClientTimeout
from PyQt5.QtCore import pyqtSignal,QObject,Qt, QTimer
from PyQt5.QtWidgets import QWidget, QLabel
from PyQt5.QtGui import QFont
from ping3 import ping

from .util_manager import utils

@utils.decorate_all_methods(utils.show_error_messagebox)
class NetworkTester(QObject):

    speedTestProgress = pyqtSignal(float)
    speedTestFinished = pyqtSignal(dict)

    pingTestProgress = pyqtSignal(int, object)
    pingTestFinished = pyqtSignal(dict)

    latencyTestProgress = pyqtSignal(int, object)
    latencyTestFinished = pyqtSignal(dict)

    geolocationTestFinished = pyqtSignal(dict)
    geolocationTestProgress = pyqtSignal(str)

    testError = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._tasks = []

    def cancel_all(self, f=None):
        for task in self._tasks:
            if not task.done():
                task.cancel()
        self._tasks.clear()

    def _track_task(self, coro):
        loop = asyncio.get_running_loop()
        task = loop.create_task(coro)
        self._tasks.append(task)
        return task

    def _build_connector(self, proxy: str):
        if proxy:
            try:
                return ProxyConnector.from_url(proxy)
            except Exception as e:
                self.testError.emit(f"name of proxy error: {e}")
        return None

    async def test_download_speed(self, url: str, proxy: str = "", duration: float = 15.0,f=None):
        samples = []
        downloaded = 0
        start = time.time()
        async def reporter():
            while True:
                await asyncio.sleep(0.3)
                elapsed = time.time() - start
                if elapsed > 0:
                    speed = (downloaded * 8 / 1_000_000) / elapsed
                    samples.append(speed)
                    self.speedTestProgress.emit(round(speed, 2))
        connector = self._build_connector(proxy)
        try:
            timeout = ClientTimeout(total=duration + 5)
            async with ClientSession(connector=connector, timeout=timeout) as session:
                reporter_task = asyncio.create_task(reporter())
                async with session.get(url) as response:
                    async for chunk in response.content.iter_chunked(1024 * 64):
                        downloaded += len(chunk)
                        if time.time() - start >= duration:
                            break
                reporter_task.cancel()
            if samples:
                self.speedTestFinished.emit({
                    'avg': round(sum(samples) / len(samples), 2),'max': round(max(samples), 2),'min': round(min(samples), 2),
                    'samples': samples})
            else:
                self.testError.emit("test fails,no data returned")
        except asyncio.CancelledError:
            self.testError.emit("speed test failed")
        except Exception as e:
            self.testError.emit(f"error: {e}")

    async def test_ping(self, target: str, count: int = 20, interval: float = 0.3, f=None):
        samples = []
        for i in range(1, count + 1):
            try:
                delay = ping(target, timeout=2)
                if delay is not None:
                    delay_ms = round(delay * 1000, 2)
                    samples.append(delay_ms)
                    self.pingTestProgress.emit(i, delay_ms)
                else:
                    self.pingTestProgress.emit(i, None)
            except Exception:
                self.pingTestProgress.emit(i, None)
            await asyncio.sleep(interval)
        loss = 1 - len(samples) / count
        if samples:
            self.pingTestFinished.emit({'avg': round(sum(samples) / len(samples), 2),'max': round(max(samples), 2),
                'min': round(min(samples), 2),'loss': loss,'samples': samples})
        else:
            self.testError.emit("all Ping tests time out")

    async def test_http_latency(self, url: str, proxy: str = "", count: int = 10, interval: float = 0.3,f=None):
        samples = []
        async def run_once(i):
            try:
                connector = self._build_connector(proxy)
                timeout = ClientTimeout(total=3.5)
                async with ClientSession(connector=connector, timeout=timeout) as session:
                    start = time.time()
                    async with session.get(url) as resp:
                        await resp.read()
                    delay = round((time.time() - start) * 1000, 2)
                    samples.append(delay)
                    self.latencyTestProgress.emit(i, delay)
            except Exception:
                self.latencyTestProgress.emit(i, None)
        for i in range(1, count + 1):
            await run_once(i)
            await asyncio.sleep(interval)
        if samples:
            self.latencyTestFinished.emit({'avg': round(sum(samples) / len(samples), 2),'max': round(max(samples), 2),
                'min': round(min(samples), 2),'samples': samples})
        else:
            self.testError.emit("all latency tests time out")

    async def test_geolocation(self, proxy: str = "", f=None):
        self.geolocationTestProgress.emit("▶ Starting to get public IP address...")
        ip_address = None
        ip_providers = ["http://icanhazip.com","http://ipinfo.io/ip","http://ifconfig.me/ip"]
        for provider in ip_providers:
            try:
                self.geolocationTestProgress.emit(f"Trying IP provider: {provider}")
                connector = self._build_connector(proxy)
                async with ClientSession(connector=connector, timeout=ClientTimeout(total=10)) as session:
                    async with session.get(provider) as response:
                        if response.status == 200:
                            ip_text = await response.text()
                            ip_address = ip_text.strip()
                            if ip_address:
                                break
            except Exception as e:
                self.geolocationTestProgress.emit(f"❗ Failed to get IP from {provider}: {str(e)}")
                continue
        if not ip_address:
            self.testError.emit("❌ Failed to retrieve public IP address.")
            return
        self.geolocationTestProgress.emit(f"✅ IP address obtained: {ip_address}")
        self.geolocationTestProgress.emit("▶ Getting geolocation info...")
        geo_providers = [f"http://ipinfo.io/{ip_address}/json",f"http://ip-api.com/json/{ip_address}"]
        location_data = None
        for provider in geo_providers:
            try:
                self.geolocationTestProgress.emit(f"Trying geo provider: {provider}")
                connector = self._build_connector(proxy)
                async with ClientSession(connector=connector, timeout=ClientTimeout(total=10)) as session:
                    async with session.get(provider) as response:
                        if response.status == 200:
                            location_data = await response.json()
                            if location_data:
                                break
            except Exception as e:
                self.geolocationTestProgress.emit(f"❗ Failed to get geo info from {provider}: {str(e)}")
                continue
        if not location_data:
            self.testError.emit("❌ Failed to retrieve geolocation info.")
            return
        result = self._normalize_geolocation_data(ip_address, location_data, proxy)
        self.geolocationTestFinished.emit(result)

    def _normalize_geolocation_data(self, ip, raw_data, proxy):
        result = {"ip": ip,"country": "","region": "","city": "","isp": "","latitude": None,"longitude": None,
            "proxy_used": proxy,"raw_data": raw_data}
        if "org" in raw_data:
            result["isp"] = raw_data.get("org", "")
            result["country"] = raw_data.get("country", "")
            result["region"] = raw_data.get("region", "")
            result["city"] = raw_data.get("city", "")
            loc = raw_data.get("loc", "").split(",")
            if len(loc) == 2:
                result["latitude"] = loc[0]
                result["longitude"] = loc[1]
        elif "isp" in raw_data:
            result["isp"] = raw_data.get("isp", "")
            result["country"] = raw_data.get("country", "")
            result["region"] = raw_data.get("regionName", "")
            result["city"] = raw_data.get("city", "")
            result["latitude"] = raw_data.get("lat")
            result["longitude"] = raw_data.get("lon")
        return result

class Toast(QWidget):
    
    HEIGHT_SPACING = 10

    def __init__(self, message, duration=2000, parent=None):
        if parent is None or not parent.isVisible():
            self._invalid = True
            return
        else:
            self._invalid = False

        super().__init__(parent)
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.label = QLabel(message, self)
        self.label.setStyleSheet("""
            QLabel {
                color: white;
                background-color: rgba(0, 0, 0, 180);
                border-radius: 10px;
                padding: 10px 20px;
            }
        """)
        self.label.setFont(QFont("微软雅黑", 10))
        self.label.adjustSize()

        self.resize(self.label.size())

        self.duration = duration
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.close_toast)

    def show(self):
        if getattr(self, '_invalid', False):
            return 
        ToastManager.add_toast(self)
        self.timer.start(self.duration)
        super().show()

    def close_toast(self):
        self.close()
        ToastManager.remove_toast(self)

class ToastManager:
    toasts = []
    parent_window = None

    @classmethod
    def set_parent(cls, window):
        cls.parent_window = window

    @classmethod
    def add_toast(cls, toast):
        if not cls.parent_window or not cls.parent_window.isVisible():
            return
        cls.toasts.append(toast)
        cls.update_toasts_position()

    @classmethod
    def remove_toast(cls, toast):
        if toast in cls.toasts:
            cls.toasts.remove(toast)
            cls.update_toasts_position()

    @classmethod
    def update_toasts_position(cls):
        if not cls.parent_window or not cls.parent_window.isVisible():
            return
        parent_geom = cls.parent_window.geometry()
        if not parent_geom.isValid():
            return
        margin_bottom = 50
        margin_right = 20
        y = parent_geom.y() + parent_geom.height() - margin_bottom
        for toast in reversed(cls.toasts):
            x = parent_geom.x() + parent_geom.width() - toast.width() - margin_right
            toast.move(x, y - toast.height())
            y -= (toast.height() + Toast.HEIGHT_SPACING)


