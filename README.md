# Vision • Concurrent Dual-Camera Background Streaming System

A complete end-to-end multi-platform project enabling continuous simultaneous broadcasting of both the phone's **rear (back)** and **front (selfie)** cameras over local Wi-Fi to a desktop server program.

The mobile application runs continuously in the **background** (even when minimized or when the screen is locked) and discovers the desktop server **automatically** without requiring manual IP address configuration.

---

## System Architecture

```
                       +-----------------------------------+
                       |    Phone (Mobile Flutter App)    |
                       | - Camera 0 (Rear) & Camera 1      |
                       | - Android Foreground Service      |
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
                       |     Vision Desktop Server         |
                       | - UDP Discovery Broadcaster       |
                       | - Dual-Stream WebSocket Hub       |
                       | - PySide6 GUI / Web Dashboard     |
                       +-----------------------------------+
```

---

## Key Features

1. **Simultaneous Dual Camera Capture & Fault Tolerance**:
   - Streams both the front and rear cameras concurrently, or operates in Back Camera Only mode.
   - Designed with isolated error handling: if one camera sensor (such as a broken front camera) fails to open or is non-functional, the app catches the error, isolates it, and keeps streaming the working camera seamlessly without crashing or freezing.
   - Utilizes Android 11+ (`CameraManager.getConcurrentCameraIds()`) with hardware JPEG encoding.

2. **Uninterrupted Background Operation**:
   - Built on an Android Foreground Service (`BackgroundStreamService`) registered with `FOREGROUND_SERVICE_TYPE_CAMERA` and `FOREGROUND_SERVICE_TYPE_DATA_SYNC`.
   - Displays an ongoing persistent notification.
   - Holds a CPU `PARTIAL_WAKE_LOCK` and a `WIFI_MODE_FULL_HIGH_PERF` lock so the camera capture and network transmission stay alive even when the phone screen turns off.

3. **Zero-Configuration Wi-Fi Auto-Discovery**:
   - The desktop server broadcasts announcements on UDP port `45454` and responds to mobile probe beacons.
   - When the phone opens or connects to Wi-Fi, it auto-detects the server's local IP address and establishes the WebSocket stream automatically.
   - Manual IP override is also available for networks with strict Wi-Fi AP client isolation.

4. **Desktop Live Monitor (Native GUI + Web Dashboard)**:
   - **Native Windows GUI**: Fast, hardware-accelerated desktop viewer window built with PySide6.
   - **Modern Web Dashboard**: Responsive dark glassmorphic HTML5 Canvas viewer with Split Screen, Picture-in-Picture (PiP), Single Camera zoom, live FPS telemetry, and instant snapshot captures.

---

## Directory Structure

- **`server/`**: The desktop program (Python, FastAPI, WebSocket Hub, PySide6 Desktop GUI, and Web dashboard).
  - **`config.py`**: Port definitions, local IP detection, and streaming defaults.
  - **`discovery.py`**: UDP auto-discovery beacon and probe responder service.
  - **`stream_hub.py`**: Central WebSocket manager receiving dual camera frames and routing to desktop viewers.
  - **`app.py`**: FastAPI application serving REST endpoints and WebSockets (`/ws/phone` and `/ws/client`).
  - **`desktop_gui.py`**: Native Windows PySide6 dual-camera desktop GUI window.
  - **`main.py`**: Main launcher orchestrating discovery, backend server, and desktop GUI.
  - **`run_server.bat`**: Double-clickable Windows launcher batch script.
  - **`static/`**: Web viewer assets (`index.html`, `style.css`, `app.js`).
- **`mobile/`**: The Flutter mobile application.
  - **`lib/`**: Flutter UI, state controllers, Wi-Fi service, and settings.
  - **`android/`**: Android native layer with `DualCameraManager.kt`, `BackgroundStreamService.kt`, and permissions in `AndroidManifest.xml`.
  - **`pubspec.yaml`**: Flutter configuration and dependencies.

---

## Quick Start Guide

### 1. Launching the Desktop Server Program

From the repository root on Windows:

```powershell
# Method 1: Double-click or run the batch launcher
.\server\run_server.bat

# Method 2: Run directly with Python
cd server
py main.py
```

- The desktop server will start its UDP Auto-Discovery beacon on port `45454`.
- The PySide6 Desktop GUI window will appear displaying side-by-side feeds for the **Rear Camera** and **Front Camera**.
- You can also view the stream in your browser at `http://localhost:8000`.

### 2. Running the Mobile Application

Ensure your phone and PC are connected to the same Wi-Fi network.

```powershell
cd mobile
flutter run
```

Or build the release APK and install it on your phone:

```powershell
cd mobile
flutter build apk --release
```

Install the APK located at:
`mobile/build/app/outputs/flutter-apk/app-release.apk`

1. Open the app on your phone and grant camera and notification permissions.
2. Tap **"START BACKGROUND BROADCAST"**.
3. The app will automatically discover your PC on the Wi-Fi network, establish the stream, and broadcast both cameras simultaneously.
4. You can minimize the app or lock your phone screen; streaming will continue uninterrupted.
