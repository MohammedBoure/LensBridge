"""Native PySide6 Desktop GUI for Vision Back-Camera Stream Proxy.

Displays the live back camera video feed, connection status, and provides
copyable proxy stream URLs (MJPEG, WebSocket, REST Snapshot) for piping
the stream into internal applications (OpenCV, AI/ML models, VLC, etc.).
"""

import json
import sys
import time
from PySide6 import QtCore, QtGui, QtWidgets
import websocket
from config import HTTP_PORT, get_local_ip


class ProxyStreamWorker(QtCore.QThread):
    """Background worker connecting to local WebSocket proxy and emitting video frames."""

    frame_signal = QtCore.Signal(QtGui.QPixmap)
    status_signal = QtCore.Signal(str, bool)
    event_signal = QtCore.Signal(dict)

    def __init__(self, port: int = HTTP_PORT):
        super().__init__()
        self.port = port
        self.running = True
        self.ws = None

    def run(self):
        url = f"ws://127.0.0.1:{self.port}/ws/proxy"
        while self.running:
            try:
                self.status_signal.emit("Connecting to local proxy core...", False)
                self.ws = websocket.WebSocketApp(
                    url,
                    on_open=self.on_open,
                    on_message=self.on_message,
                    on_error=self.on_error,
                    on_close=self.on_close,
                )
                self.ws.run_forever(ping_interval=10, ping_timeout=5)
            except Exception as e:
                self.status_signal.emit(f"Connection error: {e}", False)
            time.sleep(2)

    def stop(self):
        self.running = False
        if self.ws:
            self.ws.close()

    def on_open(self, ws):
        self.status_signal.emit("Proxy Active (Listening for Mobile Stream)", True)

    def on_message(self, ws, message):
        if isinstance(message, bytes) and len(message) > 4:
            image = QtGui.QImage()
            if image.loadFromData(message, "JPEG"):
                pixmap = QtGui.QPixmap.fromImage(image)
                self.frame_signal.emit(pixmap)
        elif isinstance(message, str):
            try:
                data = json.loads(message)
                self.event_signal.emit(data)
            except Exception:
                pass

    def on_error(self, ws, error):
        self.status_signal.emit(f"Proxy notice: {error}", False)

    def on_close(self, ws, close_code, close_msg):
        self.status_signal.emit("Proxy disconnected. Reconnecting...", False)


class MainWindow(QtWidgets.QMainWindow):
    """Main window of the Vision Desktop Server & Stream Proxy."""

    def __init__(self, port: int = HTTP_PORT):
        super().__init__()
        self.port = port
        self.local_ip = get_local_ip()

        self.last_pixmap = None
        self.frame_count = 0
        self.last_fps_time = time.time()

        self.setWindowTitle("Vision Stream Proxy • Back-Camera Live Bridge")
        self.resize(1180, 720)
        self.setStyleSheet("background-color: #0d1117; color: #f0f6fc; font-family: 'Segoe UI', sans-serif;")

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        main_layout = QtWidgets.QHBoxLayout(central)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        # LEFT PANE: Video Display
        left_box = QtWidgets.QVBoxLayout()
        left_box.setSpacing(10)

        header_bar = QtWidgets.QHBoxLayout()
        title_label = QtWidgets.QLabel("BACK CAMERA LIVE FEED")
        title_label.setStyleSheet("font-size: 16px; font-weight: 800; color: #00f2fe; letter-spacing: 1px;")
        header_bar.addWidget(title_label)

        header_bar.addStretch()

        self.fps_badge = QtWidgets.QLabel("0.0 FPS")
        self.fps_badge.setStyleSheet(
            "background-color: #161b22; color: #00e676; padding: 4px 10px; border-radius: 6px; font-family: monospace; font-weight: bold;"
        )
        header_bar.addWidget(self.fps_badge)

        self.res_badge = QtWidgets.QLabel("-- x --")
        self.res_badge.setStyleSheet(
            "background-color: #161b22; color: #8b949e; padding: 4px 10px; border-radius: 6px; font-family: monospace;"
        )
        header_bar.addWidget(self.res_badge)

        left_box.addLayout(header_bar)

        # Video Label Screen
        self.video_screen = QtWidgets.QLabel("Waiting for Phone Stream...\n\nStart broadcast on your phone")
        self.video_screen.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.video_screen.setStyleSheet(
            "background-color: #030712; color: #64748b; font-size: 14px; font-weight: bold; border-radius: 12px; border: 1px solid rgba(255,255,255,0.08);"
        )
        self.video_screen.setMinimumSize(640, 480)
        self.video_screen.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        left_box.addWidget(self.video_screen, 1)

        # Bottom actions
        action_bar = QtWidgets.QHBoxLayout()
        btn_snapshot = QtWidgets.QPushButton("Save Snapshot")
        btn_snapshot.setStyleSheet(
            "background-color: #1f2937; color: white; padding: 8px 16px; border-radius: 8px; font-weight: bold;"
        )
        btn_snapshot.clicked.connect(self.save_snapshot)
        action_bar.addWidget(btn_snapshot)

        btn_web = QtWidgets.QPushButton("Open Web Dashboard")
        btn_web.setStyleSheet(
            "background-color: #2563eb; color: white; padding: 8px 16px; border-radius: 8px; font-weight: bold;"
        )
        btn_web.clicked.connect(self.open_web)
        action_bar.addWidget(btn_web)

        action_bar.addStretch()
        left_box.addLayout(action_bar)

        main_layout.addLayout(left_box, 6)

        # RIGHT PANE: Proxy Stream URLs & Internal App Integration
        right_box = QtWidgets.QVBoxLayout()
        right_box.setSpacing(14)

        # 1. Connection Status Card
        status_group = QtWidgets.QGroupBox("Server & Phone Link")
        status_group.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; margin-top: 8px; padding-top: 14px; }")
        status_layout = QtWidgets.QVBoxLayout(status_group)

        self.phone_status_label = QtWidgets.QLabel("● Phone: Waiting for Wi-Fi stream...")
        self.phone_status_label.setStyleSheet("color: #f59e0b; font-weight: bold;")
        status_layout.addWidget(self.phone_status_label)

        server_info = QtWidgets.QLabel(f"Server IP: {self.local_ip}:{self.port} (24/7 Always-On)")
        server_info.setStyleSheet("color: #8b949e; font-size: 11px; font-family: monospace;")
        status_layout.addWidget(server_info)

        discovery_info = QtWidgets.QLabel("UDP Discovery: Listening on port 45454")
        discovery_info.setStyleSheet("color: #34d399; font-size: 11px; font-family: monospace;")
        status_layout.addWidget(discovery_info)

        right_box.addWidget(status_group)

        # 2. Reverse / Proxy Stream Endpoints Card
        proxy_group = QtWidgets.QGroupBox("Reverse / Proxy Stream Endpoints")
        proxy_group.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; margin-top: 8px; padding-top: 14px; }")
        proxy_layout = QtWidgets.QVBoxLayout(proxy_group)
        proxy_layout.setSpacing(10)

        # MJPEG URL
        self.mjpeg_url = f"http://127.0.0.1:{self.port}/stream/video"
        proxy_layout.addWidget(self._build_copy_row("MJPEG Stream (OpenCV / VLC / Web):", self.mjpeg_url))

        # WebSocket Proxy URL
        self.ws_proxy_url = f"ws://127.0.0.1:{self.port}/ws/proxy"
        proxy_layout.addWidget(self._build_copy_row("WebSocket Proxy (Raw Frames):", self.ws_proxy_url))

        # Snapshot URL
        self.snapshot_url = f"http://127.0.0.1:{self.port}/snapshot"
        proxy_layout.addWidget(self._build_copy_row("Single Frame Snapshot:", self.snapshot_url))

        right_box.addWidget(proxy_group)

        # 3. Code Example for Internal Programs
        code_group = QtWidgets.QGroupBox("Connect from Another Internal Program")
        code_group.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; margin-top: 8px; padding-top: 14px; }")
        code_layout = QtWidgets.QVBoxLayout(code_group)

        snippet = (
            "# Python OpenCV Example:\n"
            "import cv2\n"
            f'cap = cv2.VideoCapture("{self.mjpeg_url}")\n'
            "while True:\n"
            "    ret, frame = cap.read()\n"
            "    if ret:\n"
            '        cv2.imshow("Phone Camera Stream", frame)\n'
            "    if cv2.waitKey(1) == 27: break\n"
            "cap.release()\n"
            "cv2.destroyAllWindows()"
        )

        code_text = QtWidgets.QTextEdit()
        code_text.setReadOnly(True)
        code_text.setText(snippet)
        code_text.setStyleSheet(
            "background-color: #030712; color: #a5f3fc; font-family: monospace; font-size: 11px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.06);"
        )
        code_layout.addWidget(code_text)

        btn_copy_code = QtWidgets.QPushButton("Copy Python Code Snippet")
        btn_copy_code.setStyleSheet(
            "background-color: #374151; color: white; padding: 6px 12px; border-radius: 6px; font-size: 11px;"
        )
        btn_copy_code.clicked.connect(lambda: QtWidgets.QApplication.clipboard().setText(snippet))
        code_layout.addWidget(btn_copy_code)

        right_box.addWidget(code_group, 1)

        main_layout.addLayout(right_box, 4)

        # Status Bar
        self.status_bar = QtWidgets.QStatusBar()
        self.status_bar.setStyleSheet("color: #64748b; font-size: 11px;")
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Vision Proxy running. Server ready 24/7.")

        # Start Stream Worker
        self.worker = ProxyStreamWorker(port=self.port)
        self.worker.frame_signal.connect(self.update_frame)
        self.worker.status_signal.connect(self.update_status)
        self.worker.event_signal.connect(self.handle_event)
        self.worker.start()

    def _build_copy_row(self, label_text: str, url_text: str) -> QtWidgets.QWidget:
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        lbl = QtWidgets.QLabel(label_text)
        lbl.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: bold;")
        layout.addWidget(lbl)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(6)

        edit = QtWidgets.QLineEdit(url_text)
        edit.setReadOnly(True)
        edit.setStyleSheet(
            "background-color: #030712; color: #38bdf8; font-family: monospace; font-size: 11px; padding: 5px 8px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.1);"
        )
        row.addWidget(edit, 1)

        btn = QtWidgets.QPushButton("Copy")
        btn.setStyleSheet(
            "background-color: #1e293b; color: white; padding: 5px 10px; border-radius: 6px; font-size: 11px; font-weight: bold;"
        )
        btn.clicked.connect(lambda: QtWidgets.QApplication.clipboard().setText(url_text))
        row.addWidget(btn)

        layout.addLayout(row)
        return container

    def update_frame(self, pixmap: QtGui.QPixmap):
        self.last_pixmap = pixmap
        scaled = pixmap.scaled(
            self.video_screen.size(),
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
        self.video_screen.setPixmap(scaled)

        self.frame_count += 1
        now = time.time()
        elapsed = now - self.last_fps_time
        if elapsed >= 1.0:
            fps = round(self.frame_count / elapsed, 1)
            self.fps_badge.setText(f"{fps} FPS")
            self.res_badge.setText(f"{pixmap.width()} x {pixmap.height()}")
            self.frame_count = 0
            self.last_fps_time = now

    def update_status(self, msg: str, is_active: bool):
        self.status_bar.showMessage(msg)

    def handle_event(self, data: dict):
        event_type = data.get("type")
        if event_type == "PHONE_CONNECTED":
            info = data.get("phone_info", {})
            self.phone_status_label.setText(f"● Phone Connected ({info.get('ip', 'Unknown')} - {info.get('device_model', 'Mobile')})")
            self.phone_status_label.setStyleSheet("color: #00e676; font-weight: bold;")
        elif event_type == "PHONE_DISCONNECTED":
            self.phone_status_label.setText("● Phone: Disconnected (Waiting for stream...)")
            self.phone_status_label.setStyleSheet("color: #f59e0b; font-weight: bold;")
            self.fps_badge.setText("0.0 FPS")

    def save_snapshot(self):
        if self.last_pixmap:
            filename, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Save Snapshot", f"snapshot_{int(time.time())}.jpg", "Images (*.jpg *.png)"
            )
            if filename:
                self.last_pixmap.save(filename, "JPG")

    def open_web(self):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(f"http://localhost:{self.port}"))

    def closeEvent(self, event):
        self.worker.stop()
        event.accept()


def run_gui(port: int = HTTP_PORT):
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
    window = MainWindow(port=port)
    window.show()
    app.exec()


if __name__ == "__main__":
    run_gui()
