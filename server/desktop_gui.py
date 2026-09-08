"""Native PySide6 Desktop GUI for Vision Server.

Provides a hardware-accelerated desktop viewer window displaying simultaneous
rear and front camera feeds directly on Windows without requiring a browser.
"""

import sys
import threading
import time
import urllib.request
from PySide6 import QtCore, QtGui, QtWidgets
import websocket
from config import HTTP_PORT, get_local_ip


class StreamWorker(QtCore.QThread):
    """Background worker connecting to local WebSocket stream and emitting decoded frames."""

    rear_frame_signal = QtCore.Signal(QtGui.QPixmap)
    front_frame_signal = QtCore.Signal(QtGui.QPixmap)
    status_signal = QtCore.Signal(str, bool)
    cam_status_signal = QtCore.Signal(dict)

    def __init__(self, port: int = HTTP_PORT):
        super().__init__()
        self.port = port
        self.running = True
        self.ws = None

    def run(self):
        url = f"ws://127.0.0.1:{self.port}/ws/client"
        while self.running:
            try:
                self.status_signal.emit("Connecting to server core...", False)
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
        self.status_signal.emit("Connected to Local Stream Server", True)

    def on_message(self, ws, message):
        if isinstance(message, bytes) and len(message) > 1:
            cam_code = message[0]
            jpeg_data = message[1:]

            image = QtGui.QImage()
            if image.loadFromData(jpeg_data, "JPEG"):
                pixmap = QtGui.QPixmap.fromImage(image)
                if cam_code == 0:
                    self.rear_frame_signal.emit(pixmap)
                else:
                    self.front_frame_signal.emit(pixmap)
        elif isinstance(message, str):
            try:
                import json
                data = json.loads(message)
                if data.get("type") == "CAMERA_STATUS" or "camera_status" in data:
                    self.cam_status_signal.emit(data.get("camera_status") or data)
            except Exception:
                pass

    def on_error(self, ws, error):
        self.status_signal.emit(f"Stream warning: {error}", False)

    def on_close(self, ws, close_status_code, close_msg):
        self.status_signal.emit("Disconnected. Retrying...", False)


class CameraBox(QtWidgets.QGroupBox):
    """Visual widget displaying one camera feed along with its title, FPS, and snapshot button."""

    def __init__(self, title: str, tag_color: str):
        super().__init__(title)
        self.tag_color = tag_color
        self.last_pixmap = None
        self.frame_count = 0
        self.last_fps_time = time.time()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 8)

        # Video frame display label
        self.video_label = QtWidgets.QLabel("Waiting for stream...")
        self.video_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet(
            "background-color: #0b0f19; color: #64748b; font-size: 13px; font-weight: bold; border-radius: 8px;"
        )
        self.video_label.setMinimumSize(360, 270)
        self.video_label.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        layout.addWidget(self.video_label)

        # Telemetry and actions bar
        bottom_bar = QtWidgets.QHBoxLayout()
        self.fps_label = QtWidgets.QLabel("0.0 FPS")
        self.fps_label.setStyleSheet("color: #00e676; font-family: monospace; font-weight: bold;")
        bottom_bar.addWidget(self.fps_label)

        bottom_bar.addStretch()

        self.btn_snapshot = QtWidgets.QPushButton("Save Snapshot")
        self.btn_snapshot.setStyleSheet(
            "background-color: #1e293b; color: white; padding: 4px 10px; border-radius: 4px;"
        )
        self.btn_snapshot.clicked.connect(self.save_snapshot)
        bottom_bar.addWidget(self.btn_snapshot)

        layout.addLayout(bottom_bar)

    def update_frame(self, pixmap: QtGui.QPixmap):
        self.last_pixmap = pixmap
        # Scale pixmap maintaining aspect ratio
        scaled = pixmap.scaled(
            self.video_label.size(),
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
        self.video_label.setPixmap(scaled)

        # Update FPS
        self.frame_count += 1
        now = time.time()
        elapsed = now - self.last_fps_time
        if elapsed >= 1.0:
            fps = round(self.frame_count / elapsed, 1)
            self.fps_label.setText(f"{fps} FPS")
            self.frame_count = 0
            self.last_fps_time = now

    def save_snapshot(self):
        if self.last_pixmap:
            filename, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Save Snapshot", f"snapshot_{int(time.time())}.jpg", "Images (*.jpg *.png)"
            )
            if filename:
                self.last_pixmap.save(filename, "JPG")


class MainWindow(QtWidgets.QMainWindow):
    """Main window of the Vision Desktop Server GUI."""

    def __init__(self, port: int = HTTP_PORT):
        super().__init__()
        self.port = port
        self.local_ip = get_local_ip()

        self.setWindowTitle("Vision Desktop Live Server • Dual Camera Stream")
        self.resize(1100, 680)
        self.setStyleSheet("background-color: #0f172a; color: #f8fafc;")

        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QtWidgets.QVBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Header bar
        header_bar = QtWidgets.QHBoxLayout()

        title_label = QtWidgets.QLabel("VISION DESKTOP SERVER")
        title_label.setStyleSheet("font-size: 18px; font-weight: 800; color: #38bdf8; letter-spacing: 1px;")
        header_bar.addWidget(title_label)

        header_bar.addSpacing(20)

        self.ip_badge = QtWidgets.QLabel(f"Local IP: {self.local_ip}:{self.port}")
        self.ip_badge.setStyleSheet(
            "background-color: #1e293b; padding: 6px 12px; border-radius: 6px; font-family: monospace;"
        )
        header_bar.addWidget(self.ip_badge)

        self.discovery_badge = QtWidgets.QLabel("UDP Discovery: Active (Port 45454)")
        self.discovery_badge.setStyleSheet(
            "background-color: #064e3b; color: #34d399; padding: 6px 12px; border-radius: 6px; font-family: monospace;"
        )
        header_bar.addWidget(self.discovery_badge)

        header_bar.addStretch()

        self.btn_web = QtWidgets.QPushButton("Open Web Dashboard")
        self.btn_web.setStyleSheet(
            "background-color: #2563eb; color: white; padding: 6px 14px; border-radius: 6px; font-weight: bold;"
        )
        self.btn_web.clicked.connect(self.open_web_browser)
        header_bar.addWidget(self.btn_web)

        main_layout.addLayout(header_bar)

        # Video feeds grid (Rear + Front)
        streams_layout = QtWidgets.QHBoxLayout()
        streams_layout.setSpacing(14)

        self.rear_box = CameraBox("Rear Camera (Back)", "#00f2fe")
        self.front_box = CameraBox("Front Camera (Selfie)", "#ff6b6b")

        streams_layout.addWidget(self.rear_box, 1)
        streams_layout.addWidget(self.front_box, 1)

        main_layout.addLayout(streams_layout, 1)

        # Status footer
        self.status_bar = QtWidgets.QStatusBar()
        self.status_bar.setStyleSheet("color: #94a3b8; font-size: 12px;")
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready. Waiting for mobile Wi-Fi connection...")

        # Start stream worker thread
        self.worker = StreamWorker(port=self.port)
        self.worker.rear_frame_signal.connect(self.rear_box.update_frame)
        self.worker.front_frame_signal.connect(self.front_box.update_frame)
        self.worker.status_signal.connect(self.update_status)
        self.worker.cam_status_signal.connect(self.update_camera_status)
        self.worker.start()

    def update_status(self, msg: str, connected: bool):
        self.status_bar.showMessage(msg)

    def update_camera_status(self, data: dict):
        if data.get("front_active") is False:
            msg = data.get("front_message") or "Hardware Offline / Broken"
            self.front_box.video_label.setText(
                f"FRONT CAMERA OFFLINE / BYPASSED\n\n({msg})\n\nStreaming Rear Camera Safely"
            )
            self.front_box.fps_label.setText("Bypassed")

    def open_web_browser(self):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(f"http://localhost:{self.port}"))

    def closeEvent(self, event):
        self.worker.stop()
        event.accept()


def run_gui(port: int = HTTP_PORT):
    """Launches the PySide6 Desktop GUI application."""
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
    window = MainWindow(port=port)
    window.show()
    app.exec()


if __name__ == "__main__":
    run_gui()
