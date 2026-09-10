# Vision Cam Mobile Project

A cross-platform Flutter application built to capture and broadcast the phone's camera and microphone audio over local Wi-Fi while running in the background, with full programmatic control from the desktop server.

## Features

- **Back-Camera & Dual-Camera Streaming**: High-throughput rear camera streaming with hardware fault isolation for damaged front cameras.
- **Remote Flash / Torch Control**: Instantaneous flashlight toggling commanded from the server or internal API with zero stream disruption and minimum battery consumption.
- **Microphone Audio Streaming**: Energy-efficient background audio capture streaming 16-bit Mono PCM at 16,000 Hz with negligible CPU load and remote mute/enable controls.
- **Dynamic Quality & FPS Throttling**: Server-controlled hardware JPEG compression (10-100%) and native frame throttling (1-60 FPS) to drastically conserve battery and Wi-Fi transmission energy.
- **Background Execution & 24/7 Persistence**: Runs as an Android Foreground Service (`camera|dataSync|microphone`) holding `WakeLock` and adaptive `WifiLock`. Survives task swiping via `AlarmManager` resurrection and boots automatically upon device restart (`BOOT_COMPLETED`).
- **Zero-Energy Standby & Opportunistic Reconnection**: Sensors (Camera2 and AudioRecord) and high-perf Wi-Fi locks are completely shut down when disconnected, drawing near-zero idle power. Uses `ConnectivityManager.NetworkCallback` and IP caching to reconnect automatically and instantly (<50ms) whenever Wi-Fi associates.
- **Battery Optimization Whitelist**: One-tap whitelist bypasses Android Doze mode and OS battery killers for uninterrupted 24/7 background streaming.
- **Automatic Wi-Fi Discovery**: Adaptive UDP broadcast (8 fast bursts on network changes, 12s sleep intervals in standby) to find the server with minimal battery impact.

## Directory Structure

- **`lib/`**: Flutter UI, business logic, configuration, and background service communication channels.
- **`android/`**: Native Android platform implementation (Camera2 capture, AudioRecord PCM capture, foreground service, wake locks, and OkHttp WebSocket streaming).
- **`pubspec.yaml`**: Flutter package manifest and dependencies (v1.1.0+2).

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
`mobile/build/app/outputs/flutter-apk/app-release.apk` (Version: `1.1.0+2`)
