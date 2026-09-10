# Vision Cam Mobile Project

A cross-platform Flutter application built to capture and broadcast the phone's camera and microphone audio over local Wi-Fi while running in the background, with full programmatic control from the desktop server.

## Features

- **Back-Camera & Dual-Camera Streaming**: High-throughput rear camera streaming with hardware fault isolation for damaged front cameras.
- **Remote Flash / Torch Control**: Instantaneous flashlight toggling commanded from the server or internal API with zero stream disruption and minimum battery consumption.
- **Microphone Audio Streaming**: Energy-efficient background audio capture streaming 16-bit Mono PCM at 16,000 Hz with negligible CPU load and remote mute/enable controls.
- **Dynamic Quality & FPS Throttling**: Server-controlled hardware JPEG compression (10-100%) and native frame throttling (1-60 FPS) to drastically conserve battery and Wi-Fi transmission energy.
- **Background Execution**: Runs as an Android Foreground Service with continuous capture, `WakeLock`, `WifiLock`, and multicast lock so transmission never terminates when the screen turns off.
- **Automatic Wi-Fi Discovery**: Listens for and sends UDP broadcast probes on port `45454` to automatically discover and connect to the local Vision Desktop Server without needing manual IP configuration.

## Directory Structure

- **`lib/`**: Flutter UI, business logic, configuration, and background service communication channels.
- **`android/`**: Native Android platform implementation (Camera2 capture, AudioRecord PCM capture, foreground service, wake locks, and OkHttp WebSocket streaming).
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
