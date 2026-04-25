import socket
import subprocess
import tempfile
import time
from pathlib import Path


PRIVOXY_PATH = r"D:\programs\security\internet\Privoxy\privoxy.exe"
SOCKS_HOST = "127.0.0.1"
SOCKS_PORT = 1080
HTTP_HOST = "127.0.0.1"
HTTP_PORT = 8080


def is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def is_port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def build_privoxy_config() -> str:
    return (
        f"listen-address  {HTTP_HOST}:{HTTP_PORT}\n"
        f"forward-socks5t / {SOCKS_HOST}:{SOCKS_PORT} .\n"
    )


def main():
    privoxy_exe = Path(PRIVOXY_PATH)

    if not privoxy_exe.exists():
        print(f"[ERROR] privoxy.exe 不存在: {PRIVOXY_PATH}")
        return

    if not is_port_open(SOCKS_HOST, SOCKS_PORT):
        print(f"[ERROR] SOCKS5 未启动: {SOCKS_HOST}:{SOCKS_PORT}")
        return

    if is_port_in_use(HTTP_HOST, HTTP_PORT):
        print(f"[ERROR] HTTP 端口已被占用: {HTTP_HOST}:{HTTP_PORT}")
        return

    config_text = build_privoxy_config()

    temp_dir = Path(tempfile.gettempdir()) / "proxy_bridge_test"
    temp_dir.mkdir(parents=True, exist_ok=True)
    config_path = temp_dir / "privoxy_test_config.txt"
    config_path.write_text(config_text, encoding="utf-8")

    print("[INFO] 配置文件已生成:")
    print(config_path)
    print("----------")
    print(config_text)
    print("----------")
    
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0

    process = subprocess.Popen(
        [str(privoxy_exe), str(config_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        startupinfo=startupinfo,
        creationflags=subprocess.CREATE_NO_WINDOW,
        shell=False
    )

    try:
        for i in range(10):
            time.sleep(0.5)
            if is_port_open(HTTP_HOST, HTTP_PORT):
                print(f"[OK] HTTP 代理已启动: http://{HTTP_HOST}:{HTTP_PORT}")
                print("[INFO] 现在你可以手动测试：")
                print(
                    f'PowerShell: Invoke-WebRequest -Uri "https://www.google.com" -Proxy "http://{HTTP_HOST}:{HTTP_PORT}"'
                )
                break
        else:
            print("[ERROR] HTTP 代理启动失败，端口未监听")
            if process.stdout:
                output = process.stdout.read()
                if output:
                    print("[Privoxy 输出]")
                    print(output)
            return

        input("\n按回车键结束并关闭 Privoxy...\n")

    finally:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
        print("[INFO] Privoxy 已关闭")


if __name__ == "__main__":
    main()