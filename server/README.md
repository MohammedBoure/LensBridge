# Vision Desktop Server & Stream Proxy

This directory contains the desktop backend program, UDP auto-discovery responder, and reverse stream proxy engine designed to convert the mobile phone's **back (rear) camera stream** and **microphone audio** into standard formats for internal programs, with complete programmatic remote control over hardware (flash, quality, FPS, audio).

## Key Capabilities

- **Back-Camera Video Proxy**:
  - **HTTP MJPEG Stream**: `http://<IP>:8765/stream/video` (aliased at `/video_feed`). Universally compatible with OpenCV (`cv2.VideoCapture`), VLC, FFmpeg, and web browsers.
  - **Raw Binary WebSocket Proxy**: `ws://<IP>:8765/ws/proxy`. Zero-latency (<10ms) direct JPEG binary frame pipeline.
  - **REST Frame Snapshot**: `http://<IP>:8765/snapshot` (and `/snapshot.jpg`). Returns the latest frame as a JPEG response.
- **Microphone Audio Proxy**:
  - **Live Audio Stream (WAV)**: `http://<IP>:8765/stream/audio?format=wav`. Standard streamable RIFF audio consumable by VLC, FFmpeg, browsers, and media software.
  - **Raw Audio Stream (PCM)**: `http://<IP>:8765/stream/audio?format=pcm`. 16kHz 16-bit Mono PCM bytes.
  - **WebSocket Audio Proxy**: `ws://<IP>:8765/ws/audio`. Real-time audio chunks for browser players or custom listeners.
- **Internal REST API (Remote Hardware Controls)**:
  - **Flash / Torch Control**: `POST /api/flash` with `{"enabled": true/false}` (or query param `?enabled=true`). Turns rear camera flashlight on/off without interrupting video.
  - **Framerate / Number of Frames Control**: `POST /api/fps` with `{"fps": 15}` (1 - 60 FPS). Hardware frame throttling to maximize phone battery life and save Wi-Fi energy.
  - **JPEG Compression Quality Control**: `POST /api/quality` with `{"quality": 60}` (10 - 100). Dynamically adjusts image compression and bandwidth consumption.
  - **Microphone Audio Control**: `POST /api/audio` with `{"enabled": true/false}`. Suspends microphone sampling on demand to save energy.
  - **Unified Control / Settings**: `POST /api/control` (or `/api/settings`) to update multiple parameters in a single call.
- **24/7 Always-On Reliability**: Continuous execution without crashing; phone disconnections do not terminate listeners.
- **On-Demand Auto-Discovery**: Binds to UDP port `45454` with `SO_REUSEADDR` to respond instantaneously to discovery searches.

## Files and Directory Structure

- **`config.py`**: Central configuration defining ports (`8765` HTTP, `45454` UDP), default audio parameters, and hardware settings.
- **`discovery.py`**: UDP discovery responder and beacon broadcaster on port `45454`. Listens for `VISION_DISCOVER_PROBE` and announces server coordinates.
- **`stream_hub.py`**: Central proxy engine managing video and audio ingestion, queue-based pub/sub dispatch, dropped-frame protection, client telemetry, and two-way control dispatch.
- **`app.py`**: FastAPI server exposing video and audio endpoints (`/stream/video`, `/stream/audio`, `/ws/proxy`, `/ws/audio`, `/snapshot`), ingestion endpoint (`/ws/phone`), and internal control APIs (`/api/flash`, `/api/quality`, `/api/fps`, `/api/audio`, `/api/control`, `/api/status`).
- **`desktop_gui.py`**: Native Windows PySide6 desktop GUI with live video feed, remote control buttons (flash, quality slider, FPS combo, audio toggle), copyable proxy URLs, and code snippets.
- **`client_example.py`**: Python reference script demonstrating internal API programmatic control and video/audio consumption.
- **`main.py`**: Orchestrator launching UDP discovery, Uvicorn backend, and desktop GUI in unison.
- **`service_main.py`**: Headless background service daemon for 24/7 invisible execution with rotating file logging (`service.log`).
- **`service_manager.ps1`**: PowerShell service automation script (`install`, `uninstall`, `start`, `stop`, `restart`, `status`).
- **`run_hidden.vbs`**: Windows Script Host runner launching the server in 100% invisible mode.
- **`install_service.bat`**: 1-click Windows service installer.
- **`uninstall_service.bat`**: 1-click Windows service uninstaller.
- **`start_service.bat`**: 1-click background service starter.
- **`stop_service.bat`**: 1-click background service stopper.
- **`status_service.bat`**: 1-click background service telemetry & endpoint inspector.
- **`requirements.txt`**: Python dependencies (`fastapi`, `uvicorn`, `PySide6`, `websocket-client`, `Pillow`).
- **`run_server.bat`**: Double-clickable Windows batch launcher for interactive desktop GUI mode.
- **`static/`**: Web dashboard assets (`index.html`, `style.css`, `app.js`) with in-browser audio playback and control toggles.

## Internal Program Integration Example

```python
import requests
import cv2

# 1. Programmatically control hardware via Internal API
requests.post("http://127.0.0.1:8765/api/flash", json={"enabled": True})
requests.post("http://127.0.0.1:8765/api/fps", json={"fps": 15})       # Save battery
requests.post("http://127.0.0.1:8765/api/quality", json={"quality": 60}) # Reduce bandwidth

# 2. Connect to Vision proxy MJPEG stream
cap = cv2.VideoCapture("http://127.0.0.1:8765/stream/video")

while True:
    ret, frame = cap.read()
    if not ret:
        continue
    
    cv2.imshow("Phone Back Camera Stream", frame)
    if cv2.waitKey(1) == 27: # ESC
        break

cap.release()
cv2.destroyAllWindows()
```
