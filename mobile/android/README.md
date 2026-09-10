# Mobile Android Native Subsystem

This directory contains the Android native implementation for hardware camera access, microphone audio capture, Wi-Fi background execution, and Flutter platform channels.

## Key Components

- **`app/src/main/AndroidManifest.xml`**: Declares permissions for camera capture, microphone audio recording (`RECORD_AUDIO`), foreground services (`FOREGROUND_SERVICE_CAMERA`, `FOREGROUND_SERVICE_MICROPHONE`, `FOREGROUND_SERVICE_DATA_SYNC`), wake locks, Wi-Fi multicast, and registers `BackgroundStreamService`.
- **`app/build.gradle.kts`**: Configures Android SDK versions and includes OkHttp for background WebSocket networking.
- **`app/src/main/kotlin/com/vision/app/mobile/DualCameraManager.kt`**: Manages Camera2 capture sessions with hardware JPEG encoding, seamless programmatic flash/torch toggling without session reconstruction, dynamic hardware JPEG quality adjustments, and native high-speed frame rate throttling for minimum battery consumption.
- **`app/src/main/kotlin/com/vision/app/mobile/AudioStreamManager.kt`**: Low-power, zero-overhead background microphone audio recorder streaming 16-bit Mono PCM at 16,000 Hz.
- **`app/src/main/kotlin/com/vision/app/mobile/BackgroundStreamService.kt`**: Android Foreground Service maintaining continuous video and audio transmission in the background, handling two-way server control messages (flash, quality, fps, audio), persistent notification, locks, and UDP auto-discovery.
- **`app/src/main/kotlin/com/vision/app/mobile/MainActivity.kt`**: Flutter activity exposing platform MethodChannels (`com.vision.app/stream`) and EventChannels (`com.vision.app/events`) to the Dart application layer.
