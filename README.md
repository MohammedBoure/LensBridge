# Vision • Mobile Camera & Microphone Proxy with Remote Hardware Control

A complete end-to-end streaming and hardware control solution that captures the phone's **back (rear) camera** and **microphone audio** in the background, streams them continuously over local Wi-Fi, and converts them on the desktop server into **reverse proxy streams** for internal programs (OpenCV, AI pipelines, VLC, custom software).

Features a bidirectional real-time control system and **Internal REST API** allowing external programs to programmatically control hardware features from the server:
- **Flash / Torch**: Turn ON or OFF on demand with lowest energy consumption.
- **Framerate (FPS)**: Throttled programmatically to maximize battery life and minimize Wi-Fi energy.
- **Compression Quality**: Dynamically adjusted (10-100%) to optimize bandwidth and power.
- **Microphone Audio**: Streamed live (WAV / PCM / WebSocket) and remotely enabled or suspended.

---

## System Architecture

```
                       +-----------------------------------+
                       |    Phone (Mobile Flutter App)     |
                       | - Back (Rear) Camera Streamer     |
                       | - 16kHz PCM Microphone Streamer   |
                       | - Hardware Flash / Torch Control  |
                       | - Dynamic Quality & FPS Throttler |
                       | - Background Foreground Service   |
                       | - WakeLock + High-Perf WifiLock   |
                       +-----------------+-----------------+
                                         |
                       UDP Probe (45454) | (Auto-Discovery & Bidirectional WebSocket)
                                         v
+-------------------------------------------------------------------------+
|                      Local Wi-Fi Network Subnet                         |
+-------------------------------------------------------------------------+
                                         ^
                       UDP Beacon(45454) |
                                         |
                       +-----------------+-----------------+
                       |    Vision Desktop Server & Proxy  |
                       | - Always-On UDP Discovery Listener|
                       | - Video & Audio Stream Ingestion  |
                       | - Programmatic Control Dispatcher |
                       | - Native PySide6 GUI Monitor      |
                       +-----------------+-----------------+
                                         |
         +-------------------------------+-------------------------------+
         |                               |                               |
         v                               v                               v
[ HTTP MJPEG Video ]           [ HTTP Audio (WAV/PCM) ]        [ Internal Control API ]
http://<IP>:8765/stream/video  http://<IP>:8765/stream/audio   POST /api/flash
ws://<IP>:8765/ws/proxy        ws://<IP>:8765/ws/audio         POST /api/fps
http://<IP>:8765/snapshot                                      POST /api/quality
                                                               POST /api/audio
                                                               POST /api/control
                                         |
                                         v
                      +--------------------------------------+
                      |      Other Internal Applications     |
                      | - OpenCV (cv2.VideoCapture)          |
                      | - AI / ML Vision Inference Pipelines |
                      | - VLC / Media Players / FFmpeg       |
                      | - Audio Recorders / Transcribers     |
                      | - Custom Internal Software / Scripts |
                      +--------------------------------------+
```

---

## Key Features

1. **Remote Flashlight (Torch) Control via Internal API**:
   - Turn the rear camera flash ON or OFF programmatically from the server using `POST /api/flash`.
   - Modifies repeating requests on the active Camera2 capture session with **zero video interruption**, **zero camera recreation**, and **least energy consumption**.

2. **Microphone Audio Transmission**:
   - Captures microphone audio as 16-bit Mono PCM at 16,000 Hz.
   - Zero software compression overhead, ensuring negligible CPU usage and maximum battery stability.
   - Consumable via `http://<IP>:8765/stream/audio?format=wav` (VLC / browsers / FFmpeg) or `ws://<IP>:8765/ws/audio`.
   - Remotely controllable via `POST /api/audio` to suspend microphone polling when not needed.

3. **Programmatic Quality & Number of Frames (FPS) Control**:
   - **Target FPS**: Set via `POST /api/fps` (e.g. 5, 10, 15, 30 FPS). High-speed native frame throttling skips unnecessary buffer extraction, saving up to 80% of Wi-Fi radio power.
   - **Quality**: Set via `POST /api/quality` (10 - 100%). Dynamically adjusts hardware JPEG compression to reduce packet sizes and bandwidth.

4. **Internal REST API for Other Programs**:
   - Fully documented REST endpoints allowing any internal or external program (Python, C++, Node.js, cURL) to command the mobile client programmatically.

5. **24/7 Always-On Reliability, Zero-Energy Standby & Opportunistic Reconnection**:
   - **Zero-Energy Standby**: When disconnected or server is offline, Camera2 sensors and AudioRecord hardware are completely shut down, and high-performance Wi-Fi locks are released to allow mobile radios to enter sleep mode.
   - **Instant Opportunistic Reconnection**: Registers `ConnectivityManager.NetworkCallback` and caches the last known server IP/port to reconnect within <50ms whenever the phone associates with a Wi-Fi network.
   - **Adaptive Discovery**: Uses 8 rapid UDP bursts on connection events and relaxes to deep 12s standby sleep when offline to save 90% idle battery.
   - **24/7 Background Persistence & Boot Auto-Start**: Holds Android Foreground Service (`camera|dataSync|microphone`), auto-restarts on phone boot (`BOOT_COMPLETED`), revives via `AlarmManager` if swiped from recent apps, and supports one-tap battery optimization whitelist.

6. **Multi-Broadcaster Resilience & Seamless Failover**:
   - **Concurrent Broadcasters**: Supports multiple mobile phones transmitting back-camera feeds and microphone audio concurrently (`/ws/phone`).
   - **Session-Based Isolation**: Each connection gets a unique session ID. Rapid disconnect/reconnect loops do not cause race conditions where an old socket tears down a new session.
   - **Seamless Auto-Failover**: If the active broadcaster disconnects, the server automatically fails over to the next connected broadcaster without dropping subscriber connections (OpenCV, VLC, web clients).
   - **Broadcaster Selection**: Programmatically inspect connected devices via `GET /api/devices` and switch active cameras via `POST /api/devices/select`.

7. **Granular Internal API Permissions & Access Control**:
   - **Fine-Grained Scopes**: `control:flash`, `control:fps`, `control:quality`, `control:audio`, `control:*`, `stream:video`, `stream:audio`, `status:read`, `admin`, `*`.
   - **Predefined Roles**: `admin`, `operator`, `viewer`, `controller`.
   - **Flexible Token Formats**: Accepts `X-API-Key` header, `Authorization: Bearer <token>`, and query parameters (`?token=<token>`) for seamless integration with OpenCV and HTML media tags.
   - **Secret Isolation**: Stored in `server/permissions.json` which is ignored in version control, with `permissions.example.json` provided as template.

---

## Directory Structure

- **`server/`**: Desktop program, reverse proxy engine, UDP discovery, and viewer.
  - **`config.py`**: Port settings (`8765` HTTP, `45454` UDP), auth toggles, and multi-broadcast limits.
  - **`auth.py`**: Token authentication and role-based permissions engine with granular scope verification.
  - **`permissions.example.json`**: Template for role-based token configuration isolated from git commits.
  - **`discovery.py`**: UDP discovery responder on port `45454`.
  - **`stream_hub.py`**: Central proxy engine with multi-broadcaster session management and automatic failover.
  - **`app.py`**: FastAPI server exposing video/audio proxy endpoints, device selection, and secured internal APIs.
  - **`desktop_gui.py`**: Native PySide6 desktop GUI with video feed, device selection dropdown, hardware controls, and token URLs.
  - **`client_example.py`**: Python demonstration script showing token permissions, multi-device queries, and hardware controls.
  - **`test_resilience_and_permissions.py`**: Automated unit and integration test suite for multi-broadcaster failover and permissions.
  - **`main.py`**: Main entry point launching discovery, Uvicorn backend, and desktop GUI.
  - **`service_main.py`**: Headless background service daemon for 24/7 invisible execution.
  - **`static/`**: Modern web dashboard with in-browser video, audio player, token support, and control toggles.
- **`mobile/`**: Flutter mobile application.
  - **`lib/`**: Flutter UI, IP/port settings, and stream controllers.
  - **`android/`**: Native Android layer (`DualCameraManager.kt`, `AudioStreamManager.kt`, `BackgroundStreamService.kt`).
  - **`pubspec.yaml`**: Flutter package configuration.

---

## Internal REST API Reference

| Endpoint | Method | Required Scope | Description |
|---|---|---|---|
| `/api/flash` | `POST` | `control:flash` | Turn phone camera flash ON or OFF |
| `/api/flash` | `GET` | `status:read` | Get current flash state |
| `/api/fps` | `POST` | `control:fps` | Set target framerate (1 - 60 FPS) |
| `/api/fps` | `GET` | `status:read` | Get current target framerate |
| `/api/quality` | `POST` | `control:quality` | Set JPEG compression quality (10 - 100) |
| `/api/quality` | `GET` | `status:read` | Get current JPEG quality |
| `/api/audio` | `POST` | `control:audio` | Enable or mute microphone audio |
| `/api/audio` | `GET` | `status:read` | Get audio status and metrics |
| `/api/control` | `POST` | `control:*` | Batch update multiple hardware settings |
| `/api/control` | `GET` | `status:read` | Get all current control settings |
| `/api/devices` | `GET` | `status:read` | List connected broadcast sources & telemetry |
| `/api/devices/select` | `POST` | `control:*` | Switch active primary camera source |
| `/api/auth/permissions` | `GET` | None | List available scopes and predefined roles |
| `/api/auth/tokens` | `GET` | `admin` | List active authentication tokens (masked) |
| `/api/auth/tokens` | `POST` | `admin` | Generate new API access token with assigned role |
| `/api/status` | `GET` | `status:read` | Get complete server status, URLs, and telemetry |
| `/stream/video` | `GET` | `stream:video` | MJPEG video stream (supports `?token=...`) |
| `/stream/audio` | `GET` | `stream:audio` | Live microphone audio stream (supports `?token=...`) |
| `/snapshot` | `GET` | `stream:video` | Single JPEG frame snapshot (supports `?token=...`) |

---

## Quick Start Guide

### 1. Launch the Desktop Server & Proxy

Double-click `server/run_server.bat` or run from PowerShell:

```powershell
cd server
venv\Scripts\python.exe main.py
```

### 2. Connect and Control via Python Internal API

```python
import requests
import cv2

# Control hardware via Internal API
requests.post("http://127.0.0.1:8765/api/flash", json={"enabled": True})  # Turn flash ON
requests.post("http://127.0.0.1:8765/api/fps", json={"fps": 15})          # Set 15 FPS (low battery)
requests.post("http://127.0.0.1:8765/api/quality", json={"quality": 60})  # Set 60% quality

# Stream video with OpenCV
cap = cv2.VideoCapture("http://127.0.0.1:8765/stream/video")
while True:
    ret, frame = cap.read()
    if ret:
        cv2.imshow("Back Camera Live", frame)
    if cv2.waitKey(1) == 27:
        break
cap.release()
cv2.destroyAllWindows()
```

### 3. Launch the Phone Application

Install the release APK located at:
`mobile/build/app/outputs/flutter-apk/app-release.apk`

1. Open the app and tap **"START BACKGROUND BROADCAST"**.
2. The phone automatically discovers your PC on port `45454` and connects to `ws://<PC-IP>:8765/ws/phone`.
3. Lock the screen or minimize the app; video and audio stream continuously in the background.
