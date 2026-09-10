"""Native PySide6 Desktop GUI for Vision Back-Camera Stream & Audio Proxy.

Displays the live back camera video feed, connection status, microphone audio status,
and provides programmatic remote hardware controls (Flashlight, Target Framerate,
JPEG Quality, Audio Streaming) along with internal REST API URLs and code snippets.
"""

import json
import sys
import threading
import time
import urllib.request
import urllib.parse
from PySide6 import QtCore, QtGui, QtWidgets
import websocket
from config import HTTP_PORT, get_local_ip


class ProxyStreamWorker(QtCore.QThread):
    """Background worker connecting to local WebSocket proxy and emitting video frames and events."""

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

        # Hardware states
        self.flash_on = False
        self.audio_on = True
        self.current_fps = 30
        self.current_quality = 75

        self.setWindowTitle("Vision Stream Proxy • Video, Audio & Remote Hardware Control")
        self.resize(1260, 780)
        self.setStyleSheet("background-color: #0d1117; color: #f0f6fc; font-family: 'Segoe UI', sans-serif;")

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        main_layout = QtWidgets.QHBoxLayout(central)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        # =========================================================================
        # LEFT PANE: Video Display & Remote Control Panel
        # =========================================================================
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

        self.audio_badge = QtWidgets.QLabel("🎤 AUDIO ACTIVE")
        self.audio_badge.setStyleSheet(
            "background-color: #161b22; color: #38bdf8; padding: 4px 10px; border-radius: 6px; font-family: monospace; font-weight: bold;"
        )
        header_bar.addWidget(self.audio_badge)

        left_box.addLayout(header_bar)

        # Video Label Screen
        self.video_screen = QtWidgets.QLabel("Waiting for Phone Stream...\n\nStart broadcast on your phone")
        self.video_screen.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.video_screen.setStyleSheet(
            "background-color: #030712; color: #64748b; font-size: 14px; font-weight: bold; border-radius: 12px; border: 1px solid rgba(255,255,255,0.08);"
        )
        self.video_screen.setMinimumSize(640, 420)
        self.video_screen.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        left_box.addWidget(self.video_screen, 1)

        # Remote Hardware Control Bar
        controls_card = QtWidgets.QGroupBox("Server Programmatic Controls (Dispatched over Wi-Fi)")
        controls_card.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid rgba(255,255,255,0.12); border-radius: 10px; padding: 10px; margin-top: 6px; background-color: #111827; }")
        controls_layout = QtWidgets.QHBoxLayout(controls_card)
        controls_layout.setSpacing(12)

        # 1. Flash Toggle Button
        self.btn_flash = QtWidgets.QPushButton("⚡ Flash: OFF")
        self.btn_flash.setStyleSheet(
            "background-color: #374151; color: white; padding: 8px 14px; border-radius: 8px; font-weight: bold; font-size: 12px;"
        )
        self.btn_flash.clicked.connect(self.toggle_flash)
        controls_layout.addWidget(self.btn_flash)

        # 2. Audio Toggle Button
        self.btn_audio = QtWidgets.QPushButton("🎤 Microphone: ON")
        self.btn_audio.setStyleSheet(
            "background-color: #065f46; color: #a7f3d0; padding: 8px 14px; border-radius: 8px; font-weight: bold; font-size: 12px;"
        )
        self.btn_audio.clicked.connect(self.toggle_audio)
        controls_layout.addWidget(self.btn_audio)

        # 3. Target Framerate (FPS)
        fps_layout = QtWidgets.QHBoxLayout()
        fps_lbl = QtWidgets.QLabel("FPS:")
        fps_lbl.setStyleSheet("color: #94a3b8; font-weight: bold;")
        fps_layout.addWidget(fps_lbl)

        self.fps_combo = QtWidgets.QComboBox()
        self.fps_combo.addItems(["5", "10", "15", "20", "24", "30", "60"])
        self.fps_combo.setCurrentText("30")
        self.fps_combo.setStyleSheet("background-color: #1f2937; color: #38bdf8; font-weight: bold; padding: 4px 8px; border-radius: 6px;")
        self.fps_combo.currentTextChanged.connect(self.change_fps)
        fps_layout.addWidget(self.fps_combo)
        controls_layout.addLayout(fps_layout)

        # 4. JPEG Quality Slider
        quality_layout = QtWidgets.QHBoxLayout()
        self.quality_lbl = QtWidgets.QLabel("Quality: 75%")
        self.quality_lbl.setStyleSheet("color: #94a3b8; font-weight: bold;")
        quality_layout.addWidget(self.quality_lbl)

        self.quality_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.quality_slider.setRange(10, 100)
        self.quality_slider.setValue(75)
        self.quality_slider.setFixedWidth(110)
        self.quality_slider.valueChanged.connect(self.change_quality)
        quality_layout.addWidget(self.quality_slider)
        controls_layout.addLayout(quality_layout)

        left_box.addWidget(controls_card)

        # Bottom Actions Bar
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

        # =========================================================================
        # RIGHT PANE: Proxy Stream URLs & Internal API Integration
        # =========================================================================
        right_box = QtWidgets.QVBoxLayout()
        right_box.setSpacing(12)

        # 1. Connection Status Card
        status_group = QtWidgets.QGroupBox("Server & Phone Link")
        status_group.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; margin-top: 6px; padding-top: 12px; }")
        status_layout = QtWidgets.QVBoxLayout(status_group)

        self.phone_status_label = QtWidgets.QLabel("● Phone: Waiting for Wi-Fi stream...")
        self.phone_status_label.setStyleSheet("color: #f59e0b; font-weight: bold;")
        status_layout.addWidget(self.phone_status_label)

        server_info = QtWidgets.QLabel(f"Server Host: {self.local_ip}:{self.port} (24/7 Always-On)")
        server_info.setStyleSheet("color: #8b949e; font-size: 11px; font-family: monospace;")
        status_layout.addWidget(server_info)

        discovery_info = QtWidgets.QLabel("UDP Discovery: Listening on port 45454")
        discovery_info.setStyleSheet("color: #34d399; font-size: 11px; font-family: monospace;")
        status_layout.addWidget(discovery_info)

        right_box.addWidget(status_group)

        # 2. Reverse / Proxy Stream Endpoints Card
        proxy_group = QtWidgets.QGroupBox("Stream Endpoints (Video & Audio)")
        proxy_group.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; margin-top: 6px; padding-top: 12px; }")
        proxy_layout = QtWidgets.QVBoxLayout(proxy_group)
        proxy_layout.setSpacing(8)

        self.mjpeg_url = f"http://127.0.0.1:{self.port}/stream/video"
        proxy_layout.addWidget(self._build_copy_row("MJPEG Video Stream (OpenCV / VLC):", self.mjpeg_url))

        self.audio_url = f"http://127.0.0.1:{self.port}/stream/audio"
        proxy_layout.addWidget(self._build_copy_row("Microphone Audio Stream (WAV / VLC):", self.audio_url))

        self.ws_proxy_url = f"ws://127.0.0.1:{self.port}/ws/proxy"
        proxy_layout.addWidget(self._build_copy_row("WebSocket Video Proxy (Raw Frames):", self.ws_proxy_url))

        self.snapshot_url = f"http://127.0.0.1:{self.port}/snapshot"
        proxy_layout.addWidget(self._build_copy_row("Single Frame Snapshot:", self.snapshot_url))

        right_box.addWidget(proxy_group)

        # 3. Internal REST API & Programmatic Control Card
        api_group = QtWidgets.QGroupBox("Internal API: Programmatic Remote Control")
        api_group.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; margin-top: 6px; padding-top: 12px; }")
        api_layout = QtWidgets.QVBoxLayout(api_group)

        api_snippet = (
            "# Internal API Examples (Python):\n"
            "import requests\n\n"
            "# 1. Turn Flash ON / OFF\n"
            f'requests.post("http://127.0.0.1:{self.port}/api/flash", json={{"enabled": True}})\n\n'
            "# 2. Set Target Framerate (e.g. 15 FPS for low power)\n"
            f'requests.post("http://127.0.0.1:{self.port}/api/fps", json={{"fps": 15}})\n\n'
            "# 3. Set Compression Quality (10 - 100)\n"
            f'requests.post("http://127.0.0.1:{self.port}/api/quality", json={{"quality": 60}})\n\n'
            "# 4. Enable / Disable Microphone Audio\n"
            f'requests.post("http://127.0.0.1:{self.port}/api/audio", json={{"enabled": True}})\n'
        )

        code_text = QtWidgets.QTextEdit()
        code_text.setReadOnly(True)
        code_text.setText(api_snippet)
        code_text.setStyleSheet(
            "background-color: #030712; color: #a5f3fc; font-family: monospace; font-size: 11px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.06);"
        )
        api_layout.addWidget(code_text)

        btn_copy_api = QtWidgets.QPushButton("Copy Internal API Python Code")
        btn_copy_api.setStyleSheet(
            "background-color: #374151; color: white; padding: 6px 12px; border-radius: 6px; font-size: 11px;"
        )
        btn_copy_api.clicked.connect(lambda: QtWidgets.QApplication.clipboard().setText(api_snippet))
        api_layout.addWidget(btn_copy_api)

        right_box.addWidget(api_group, 1)

        main_layout.addLayout(right_box, 4)

        # Status Bar
        self.status_bar = QtWidgets.QStatusBar()
        self.status_bar.setStyleSheet("color: #64748b; font-size: 11px;")
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Vision Proxy running. Internal API ready 24/7.")

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
        layout.setSpacing(3)

        lbl = QtWidgets.QLabel(label_text)
        lbl.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: bold;")
        layout.addWidget(lbl)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(6)

        edit = QtWidgets.QLineEdit(url_text)
        edit.setReadOnly(True)
        edit.setStyleSheet(
            "background-color: #030712; color: #38bdf8; font-family: monospace; font-size: 11px; padding: 4px 8px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.1);"
        )
        row.addWidget(edit, 1)

        btn = QtWidgets.QPushButton("Copy")
        btn.setStyleSheet(
            "background-color: #1e293b; color: white; padding: 4px 8px; border-radius: 6px; font-size: 11px; font-weight: bold;"
        )
        btn.clicked.connect(lambda: QtWidgets.QApplication.clipboard().setText(url_text))
        row.addWidget(btn)

        layout.addLayout(row)
        return container

    def _call_api_async(self, endpoint: str, json_data: dict):
        """Asynchronously triggers an internal API request."""
        def run():
            try:
                url = f"http://127.0.0.1:{self.port}{endpoint}"
                data = json.dumps(json_data).encode("utf-8")
                req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=3) as resp:
                    resp.read()
            except Exception as e:
                print(f"[Desktop GUI] API error ({endpoint}): {e}")

        threading.Thread(target=run, daemon=True).start()

    def toggle_flash(self):
        self.flash_on = not self.flash_on
        self._update_flash_button_ui(self.flash_on)
        self._call_api_async("/api/flash", {"enabled": self.flash_on})

    def toggle_audio(self):
        self.audio_on = not self.audio_on
        self._update_audio_button_ui(self.audio_on)
        self._call_api_async("/api/audio", {"enabled": self.audio_on})

    def change_fps(self, val: str):
        try:
            fps = int(val)
            self.current_fps = fps
            self._call_api_async("/api/fps", {"fps": fps})
        except Exception:
            pass

    def change_quality(self, val: int):
        self.current_quality = val
        self.quality_lbl.setText(f"Quality: {val}%")
        self._call_api_async("/api/quality", {"quality": val})

    def _update_flash_button_ui(self, enabled: bool):
        self.flash_on = enabled
        if enabled:
            self.btn_flash.setText("⚡ Flash: ON")
            self.btn_flash.setStyleSheet("background-color: #d97706; color: white; padding: 8px 14px; border-radius: 8px; font-weight: bold; font-size: 12px;")
        else:
            self.btn_flash.setText("⚡ Flash: OFF")
            self.btn_flash.setStyleSheet("background-color: #374151; color: white; padding: 8px 14px; border-radius: 8px; font-weight: bold; font-size: 12px;")

    def _update_audio_button_ui(self, enabled: bool):
        self.audio_on = enabled
        if enabled:
            self.btn_audio.setText("🎤 Microphone: ON")
            self.btn_audio.setStyleSheet("background-color: #065f46; color: #a7f3d0; padding: 8px 14px; border-radius: 8px; font-weight: bold; font-size: 12px;")
            self.audio_badge.setText("🎤 AUDIO ACTIVE")
            self.audio_badge.setStyleSheet("background-color: #161b22; color: #38bdf8; padding: 4px 10px; border-radius: 6px; font-family: monospace; font-weight: bold;")
        else:
            self.btn_audio.setText("🎤 Microphone: MUTED")
            self.btn_audio.setStyleSheet("background-color: #7f1d1d; color: #fca5a5; padding: 8px 14px; border-radius: 8px; font-weight: bold; font-size: 12px;")
            self.audio_badge.setText("🎤 AUDIO MUTED")
            self.audio_badge.setStyleSheet("background-color: #161b22; color: #ef4444; padding: 4px 10px; border-radius: 6px; font-family: monospace; font-weight: bold;")

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
            self.phone_status_label.setText(f"● Phone Connected ({info.get('ip', 'Wi-Fi')} - {info.get('device_model', 'Mobile')})")
            self.phone_status_label.setStyleSheet("color: #00e676; font-weight: bold;")
        elif event_type == "PHONE_DISCONNECTED":
            self.phone_status_label.setText("● Phone: Disconnected (Waiting for stream...)")
            self.phone_status_label.setStyleSheet("color: #f59e0b; font-weight: bold;")
            self.fps_badge.setText("0.0 FPS")
        elif event_type in ("CONTROL_UPDATED", "PHONE_STATE_SYNC"):
            controls = data.get("controls", {})
            if "flash_enabled" in controls:
                self._update_flash_button_ui(controls["flash_enabled"])
            if "audio_enabled" in controls:
                self._update_audio_button_ui(controls["audio_enabled"])
            if "quality" in controls:
                q = controls["quality"]
                self.quality_slider.blockSignals(True)
                self.quality_slider.setValue(q)
                self.quality_slider.blockSignals(False)
                self.quality_lbl.setText(f"Quality: {q}%")
            if "fps" in controls:
                fps = str(controls["fps"])
                self.fps_combo.blockSignals(True)
                idx = self.fps_combo.findText(fps)
                if idx >= 0:
                    self.fps_combo.setCurrentIndex(idx)
                self.fps_combo.blockSignals(False)

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
