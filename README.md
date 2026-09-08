# Vision • Mobile Camera Background Stream & Desktop Reverse Proxy System

A complete end-to-end streaming solution that captures the phone's **back (rear) camera** in the background, streams it continuously over local Wi-Fi, and converts the stream on the desktop server into a **reverse proxy stream** for external and internal programs (e.g., OpenCV, AI pipelines, VLC, custom software).

The mobile app runs 24/7 as an Android Foreground Service with `WakeLock`/`WifiLock`, and the desktop server remains active continuously, ready to respond to discovery searches from the phone at any moment.

---

## System Architecture

```
                       +-----------------------------------+
                       |    Phone (Mobile Flutter App)     |
                       | - Back (Rear) Camera Streamer     |
                       | - Fault-Tolerant Camera2 Engine   |
                       | - Background Foreground Service   |
                       | - WakeLock + High-Perf WifiLock   |
                       +-----------------+-----------------+
                                         |
                       UDP Probe (45454) | (Auto-Discovery)
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
                       | - Back-Camera Stream Ingestion    |
                       | - Native PySide6 GUI Monitor      |
                       +-----------------+-----------------+
                                         |
               +-------------------------+-------------------------+
               |                         |                         |
               v                         v                         v
     [ HTTP MJPEG Proxy ]      [ WebSocket Proxy ]      [ Single Snapshot ]
   http://<IP>:8765/stream/video  ws://<IP>:8765/ws/proxy   http://<IP>:8765/snapshot
               |                         |                         |
               +-------------------------+-------------------------+
                                         |
                                         v
                      +--------------------------------------+
                      |      Other Internal Applications     |
                      | - OpenCV (cv2.VideoCapture)          |
                      | - AI / ML Vision Inference Pipelines |
                      | - VLC / Media Players / FFmpeg       |
                      | - Custom Internal Software / Tools   |
                      +--------------------------------------+
```

---

## Key Features

1. **Back-Camera Streaming & Fault Isolation**:
   - Focuses exclusively on the phone's back camera for optimal throughput and clarity.
   - Fault-tolerant hardware engine: if the front camera is broken, the app isolates the error and runs in "Back Camera Only" mode without freezing or crashing.

2. **Reverse / Proxy Stream for Internal Programs**:
   - **HTTP MJPEG Stream** (`http://127.0.0.1:8765/stream/video` or `/video_feed`): Zero-configuration stream compatible with OpenCV `cv2.VideoCapture`, VLC, FFmpeg, and browsers.
   - **Low-Latency WebSocket Proxy** (`ws://127.0.0.1:8765/ws/proxy`): Sub-10ms direct binary JPEG stream.
   - **Snapshot API** (`http://127.0.0.1:8765/snapshot`): High-speed single-frame capture for image analysis scripts.

3. **24/7 Always-On Server & On-Demand Discovery**:
   - Desktop backend runs continuously without stopping. If the phone disconnects or switches networks, the server stays online waiting for the next connection.
   - UDP discovery service binds on port `45454`, replying to phone searches the instant broadcast is started.

4. **Continuous Background Operation on Phone**:
   - Android Foreground Service with persistent notification.
   - Holds `WakeLock` and `WifiLock` so transmission continues even when the screen is turned off or apps are switched.

---

## Directory Structure

- **`server/`**: Desktop program, reverse proxy engine, UDP discovery, and viewer.
  - **`config.py`**: Port settings (`8765` HTTP, `45454` UDP), IP detection, and parameters.
  - **`discovery.py`**: UDP discovery responder on port `45454`.
  - **`stream_hub.py`**: Central back-camera stream proxy broker with queue-based MJPEG pub/sub.
  - **`app.py`**: FastAPI application exposing `/stream/video`, `/ws/proxy`, `/snapshot`, and `/ws/phone`.
  - **`desktop_gui.py`**: PySide6 desktop monitor with live video feed and proxy URLs.
  - **`main.py`**: Main entry point launching backend, discovery, and desktop monitor.
  - **`run_server.bat`**: Double-clickable Windows batch launcher.
  - **`static/`**: Web dashboard assets for browser viewing.
- **`mobile/`**: Flutter mobile application.
  - **`lib/`**: Flutter UI, IP/port settings, and stream controllers.
  - **`android/`**: Native Android layer (`DualCameraManager.kt`, `BackgroundStreamService.kt`).
  - **`pubspec.yaml`**: Flutter package configuration.

---

## Quick Start Guide

### 1. Launch the Desktop Server & Proxy

Double-click `server/run_server.bat` or run from PowerShell:

```powershell
cd server
py main.py
```

The desktop program will display:
- Live back camera feed.
- Ready-to-copy proxy URLs for MJPEG, WebSocket, and Snapshot.
- UDP discovery active on port `45454`.

### 2. Connect from Another Internal Program (OpenCV)

```python
import cv2

# Connect to the local proxy MJPEG stream
cap = cv2.VideoCapture("http://127.0.0.1:8765/stream/video")

while True:
    ret, frame = cap.read()
    if not ret:
        continue
    
    cv2.imshow("Back Camera Live Proxy", frame)
    if cv2.waitKey(1) == 27: # ESC key to exit
        break

cap.release()
cv2.destroyAllWindows()
```

### 3. Running as a 24/7 Windows Background Service

To run the server continuously in the background without keeping any console windows open (starts automatically on Windows boot):

1. **Install Service**: Double-click [`server/install_service.bat`](file:///C:/Users/moham/Desktop/vision/server/install_service.bat)
2. **Check Status**: Double-click [`server/status_service.bat`](file:///C:/Users/moham/Desktop/vision/server/status_service.bat)
3. **Stop Service**: Double-click [`server/stop_service.bat`](file:///C:/Users/moham/Desktop/vision/server/stop_service.bat)
4. **Start Service**: Double-click [`server/start_service.bat`](file:///C:/Users/moham/Desktop/vision/server/start_service.bat)
5. **Uninstall Service**: Double-click [`server/uninstall_service.bat`](file:///C:/Users/moham/Desktop/vision/server/uninstall_service.bat)

### 4. Launch the Phone Application

Install the release APK located at:
`mobile/build/app/outputs/flutter-apk/app-release.apk`

1. Open the app and tap **"START BACKGROUND BROADCAST"**.
2. The phone automatically discovers your PC on port `45454` and connects to `ws://<PC-IP>:8765/ws/phone`.
3. You can also specify the PC IP manually (e.g., `192.168.1.150` or `10.0.2.2` for emulator).
4. Lock the screen or minimize the app; the stream runs continuously in the background.
