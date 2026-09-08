"""Main Entry Point for the Vision Desktop Server.

Orchestrates:
1. UDP Wi-Fi Auto-Discovery Service (port 45454)
2. FastAPI Back-Camera WebSocket Stream Server & Proxy (port 8765)
3. Hardware-accelerated Desktop GUI window (PySide6) or Web Dashboard
"""

import argparse
import os
import sys
import threading
import time
import webbrowser
import uvicorn
from app import app
from config import DEFAULT_HOST, HTTP_PORT, DISCOVERY_PORT, get_local_ip
from discovery import DiscoveryService


def start_server_backend(host: str = DEFAULT_HOST, port: int = HTTP_PORT):
    """Starts the Uvicorn ASGI server hosting the REST and WebSocket endpoints."""
    config = uvicorn.Config(app=app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    server.run()


def main():
    parser = argparse.ArgumentParser(description="Vision Back-Camera Stream Server & Proxy")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Host binding address")
    parser.add_argument("--port", type=int, default=HTTP_PORT, help="HTTP/WebSocket port")
    parser.add_argument("--no-gui", action="store_true", help="Run without PySide6 native GUI (launches browser)")
    args = parser.parse_args()

    local_ip = get_local_ip()
    print("=" * 60)
    print("    VISION BACK-CAMERA STREAM SERVER & PROXY HUB")
    print("=" * 60)
    print(f"[*] Local Host IP   : {local_ip}")
    print(f"[*] Web Dashboard   : http://{local_ip}:{args.port}")
    print(f"[*] Phone Endpoint  : ws://{local_ip}:{args.port}/ws/phone")
    print(f"[*] Proxy MJPEG     : http://{local_ip}:{args.port}/stream/video")
    print(f"[*] Proxy WebSocket : ws://{local_ip}:{args.port}/ws/proxy")
    print(f"[*] UDP Discovery   : Broadcast & Listen on port {DISCOVERY_PORT}")
    print("=" * 60)

    # 1. Start UDP Discovery Service
    discovery = DiscoveryService(http_port=args.port, discovery_port=DISCOVERY_PORT)
    discovery.start()

    # 2. Start Uvicorn Server in Background Thread
    server_thread = threading.Thread(
        target=start_server_backend,
        args=(args.host, args.port),
        daemon=True,
    )
    server_thread.start()
    time.sleep(1.0)

    # 3. Launch UI
    if not args.no_gui:
        try:
            from desktop_gui import run_gui
            print("[*] Launching PySide6 Desktop GUI Window...")
            run_gui(port=args.port)
        except Exception as e:
            print(f"[!] PySide6 GUI launch skipped: {e}. Opening default browser...")
            webbrowser.open(f"http://localhost:{args.port}")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
    else:
        print("[*] Opening Web Dashboard in default browser...")
        webbrowser.open(f"http://localhost:{args.port}")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    print("[*] Shutting down Vision Desktop Server...")
    discovery.stop()


if __name__ == "__main__":
    main()
