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
- **Multi-Broadcaster Resilience & Automatic Failover**:
  - **Multiple Concurrent Sources**: Concurrently connects multiple phone cameras (`/ws/phone`), with each connection identified by an isolated session ID.
  - **Race-Condition Immunity**: Rapid reconnect loops never drop active streaming; an old disconnecting socket's teardown cannot kill a newly reconnected session.
  - **Seamless Failover**: If the active camera disconnects, the server automatically fails over to the next available source without dropping external subscribers (OpenCV, VLC, web clients).
  - **Device Management**: `GET /api/devices` lists connected sources with frame rates, telemetry, and uptimes; `POST /api/devices/select` switches the primary broadcast device.
- **Granular Internal API Permissions & Access Control**:
  - **Fine-Grained Scopes**: `control:flash`, `control:fps`, `control:quality`, `control:audio`, `control:*`, `stream:video`, `stream:audio`, `status:read`, `admin`, `*`.
  - **Predefined Roles**: `admin` (super-user), `operator` (stream + control), `viewer` (read-only streams), `controller` (hardware adjustments).
  - **Flexible Authentication**: Supports `X-API-Key` header, `Authorization: Bearer <token>`, and query parameters (`?token=<token>` or `?api_key=<token>`) for seamless integration with OpenCV and HTML media tags.
  - **Loopback Bypass**: Localhost calls (127.0.0.1) can optionally bypass auth for desktop ease, or enforce strict tokens via `auth_manager.allow_local_loopback_bypass = False`.
- **Internal REST API (Remote Hardware Controls)**:
  - **Flash / Torch Control**: `POST /api/flash` with `{"enabled": true/false}` (or query param `?enabled=true`). Turns rear camera flashlight on/off without interrupting video.
  - **Framerate / Number of Frames Control**: `POST /api/fps` with `{"fps": 15}` (1 - 60 FPS). Hardware frame throttling to maximize phone battery life and save Wi-Fi energy.
  - **JPEG Compression Quality Control**: `POST /api/quality` with `{"quality": 60}` (10 - 100). Dynamically adjusts image compression and bandwidth consumption.
  - **Microphone Audio Control**: `POST /api/audio` with `{"enabled": true/false}`. Suspends microphone sampling on demand to save energy.
  - **Unified Control / Settings**: `POST /api/control` (or `/api/settings`) to update multiple parameters in a single call.
- **24/7 Always-On Reliability**: Continuous execution without crashing; phone disconnections do not terminate listeners.
- **On-Demand Auto-Discovery**: Binds to UDP port `45454` with `SO_REUSEADDR` to respond instantaneously to discovery searches.

## Files and Directory Structure

- **`config.py`**: Central configuration defining ports (`8765` HTTP, `45454` UDP), auth toggles, and multi-broadcast limits.
- **`auth.py`**: Token authentication and role-based permissions engine with granular scope verification (`PermissionScope`, `ROLE_DEFINITIONS`, `PermissionsManager`).
- **`permissions.example.json`**: Template for role-based token configuration isolated from git commits.
- **`discovery.py`**: UDP discovery responder and beacon broadcaster on port `45454`. Listens for `VISION_DISCOVER_PROBE` and announces server coordinates.
- **`stream_hub.py`**: Central proxy engine managing multi-broadcaster session lifecycle, queue-based pub/sub dispatch, seamless auto-failover, telemetry, and two-way control dispatch.
- **`app.py`**: FastAPI server exposing video/audio endpoints, ingestion endpoint (`/ws/phone`), multi-device management (`/api/devices`), auth management (`/api/auth/*`), and internal control APIs.
- **`desktop_gui.py`**: Native Windows PySide6 desktop GUI with live video feed, device selection dropdown, remote control buttons, copyable token URLs, and code snippets.
- **`client_example.py`**: Python reference script demonstrating token authentication, permission scope enforcement, multi-device querying, and hardware control.
- **`test_resilience_and_permissions.py`**: Automated test suite verifying multi-broadcaster failover, race-condition handling, token validation (401, 403, 200), and endpoint streaming.
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
- **`static/`**: Web dashboard assets (`index.html`, `style.css`, `app.js`) with in-browser audio playback, token support, and control toggles.

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
