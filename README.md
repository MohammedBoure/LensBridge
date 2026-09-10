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

5. **24/7 Always-On Reliability & Background Service**:
   - Android Foreground Service with `camera|dataSync|microphone` types.
   - Holds `WakeLock` and `WifiLock` so transmission continues when the phone screen is turned off.

---

## Directory Structure

- **`server/`**: Desktop program, reverse proxy engine, UDP discovery, and viewer.
  - **`config.py`**: Port settings (`8765` HTTP, `45454` UDP), default audio/video parameters.
  - **`discovery.py`**: UDP discovery responder on port `45454`.
  - **`stream_hub.py`**: Central video & audio proxy broker with bidirectional control dispatch.
  - **`app.py`**: FastAPI server exposing video/audio proxy endpoints and internal hardware control APIs.
  - **`desktop_gui.py`**: Native PySide6 desktop GUI with video feed, hardware control buttons, and copyable URLs.
  - **`client_example.py`**: Complete Python demonstration script for the Internal API and streams.
  - **`main.py`**: Main entry point launching discovery, Uvicorn backend, and desktop GUI.
  - **`service_main.py`**: Headless background service daemon for 24/7 invisible execution.
  - **`static/`**: Modern web dashboard with in-browser video, audio player, and control toggles.
- **`mobile/`**: Flutter mobile application.
  - **`lib/`**: Flutter UI, IP/port settings, and stream controllers.
  - **`android/`**: Native Android layer (`DualCameraManager.kt`, `AudioStreamManager.kt`, `BackgroundStreamService.kt`).
  - **`pubspec.yaml`**: Flutter package configuration.

---

## Internal REST API Reference

| Endpoint | Method | Payload / Params | Description |
|---|---|---|---|
| `/api/flash` | `POST` | `{"enabled": true}` or `?enabled=true` | Turn phone camera flash ON or OFF |
| `/api/flash` | `GET` | None | Get current flash state |
| `/api/fps` | `POST` | `{"fps": 15}` or `?fps=15` | Set target framerate (1 - 60 FPS) |
| `/api/fps` | `GET` | None | Get current target framerate |
| `/api/quality` | `POST` | `{"quality": 60}` or `?quality=60` | Set JPEG compression quality (10 - 100) |
| `/api/quality` | `GET` | None | Get current JPEG quality |
| `/api/audio` | `POST` | `{"enabled": true}` or `?enabled=true` | Enable or mute microphone audio |
| `/api/audio` | `GET` | None | Get audio status and metrics |
| `/api/control` | `POST` | `{"flash": true, "fps": 15, "quality": 70, "audio": true}` | Batch update multiple hardware settings |
| `/api/control` | `GET` | None | Get all current control settings |
| `/api/status` | `GET` | None | Get complete server status, URLs, and telemetry |
| `/stream/video` | `GET` | None | MJPEG video stream (OpenCV, VLC, FFmpeg) |
| `/stream/audio` | `GET` | `?format=wav` or `?format=pcm` | Live microphone audio stream |
| `/snapshot` | `GET` | None | Single JPEG frame snapshot |

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
