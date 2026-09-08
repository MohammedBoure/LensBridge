# Mobile Android Native Subsystem

This directory contains the Android native implementation for hardware camera access, Wi-Fi background execution, and Flutter platform channels.

## Key Components

- **`app/src/main/AndroidManifest.xml`**: Declares permissions for camera capture, foreground services (`FOREGROUND_SERVICE_CAMERA`), wake locks, Wi-Fi multicast, and registers `BackgroundStreamService`.
- **`app/build.gradle.kts`**: Configures Android SDK versions and includes OkHttp for background WebSocket networking.
- **`app/src/main/kotlin/com/vision/app/mobile/DualCameraManager.kt`**: Manages concurrent Camera2 capture sessions for both the back (rear) and front cameras using Android concurrent camera APIs (`CameraManager.concurrentCameraIds`) with hardware JPEG encoding.
- **`app/src/main/kotlin/com/vision/app/mobile/BackgroundStreamService.kt`**: Android Foreground Service that maintains continuous video capture and WebSocket transmission in the background, complete with persistent notification, Wi-Fi lock, wake lock, and UDP auto-discovery.
- **`app/src/main/kotlin/com/vision/app/mobile/MainActivity.kt`**: Flutter activity exposing platform MethodChannels (`com.vision.app/stream`) and EventChannels (`com.vision.app/events`) to the Dart application layer.
