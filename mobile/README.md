# Vision Cam Mobile Project

A cross-platform Flutter application built to capture and broadcast both the rear (back) and front cameras concurrently over local Wi-Fi while running in the background.

## Features

- **Concurrent Dual Camera & Single-Camera Modes**: Simultaneously streams frames from the rear camera and front selfie camera, or operates in Back Camera Only mode if the front camera is broken or unavailable.
- **Hardware Fault-Tolerance**: If one camera (e.g., front camera) is damaged, disconnected, or fails to open, the application isolates the error and seamlessly continues streaming the functional camera without crashing or freezing.
- **Background Execution**: Runs as an Android Foreground Service with continuous capture, `WakeLock`, and `WifiLock` so transmission never terminates when the screen turns off or apps are switched.
- **Automatic Wi-Fi Discovery**: Listens for and sends UDP broadcast probes on port `45454` to automatically discover and connect to the local Vision Desktop Server without needing manual IP configuration.
- **Telemetry and Controls**: Real-time FPS metrics, Wi-Fi status badges, camera mode switchers (Back Only vs. Dual), and manual IP override settings.

## Directory Structure

- **`lib/`**: Flutter UI, business logic, configuration, and background service communication channels.
- **`android/`**: Native Android platform implementation (Camera2 concurrent capture, foreground service, wake locks, and OkHttp WebSocket streaming).
- **`pubspec.yaml`**: Flutter package manifest and dependencies.

## Building and Running

To run the mobile app on a connected phone or emulator:

```bash
cd mobile
flutter pub get
flutter run
```

To build a standalone APK for your phone:

```bash
flutter build apk --release
```
The compiled release APK is located at:
`mobile/build/app/outputs/flutter-apk/app-release.apk`
