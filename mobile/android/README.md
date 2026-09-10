# Mobile Android Native Subsystem

This directory contains the Android native implementation for hardware camera access, microphone audio capture, Wi-Fi background execution, and Flutter platform channels.

## Key Components

- **`app/src/main/AndroidManifest.xml`**: Declares permissions for camera capture, microphone audio recording (`RECORD_AUDIO`), foreground services (`FOREGROUND_SERVICE_CAMERA`, `FOREGROUND_SERVICE_MICROPHONE`, `FOREGROUND_SERVICE_DATA_SYNC`), wake locks, Wi-Fi multicast, and registers `BackgroundStreamService`.
- **`app/build.gradle.kts`**: Configures Android SDK versions and includes OkHttp for background WebSocket networking.
- **`app/src/main/kotlin/com/vision/app/mobile/DualCameraManager.kt`**: Manages Camera2 capture sessions with hardware JPEG encoding, seamless programmatic flash/torch toggling without session reconstruction, dynamic hardware JPEG quality adjustments, and native high-speed frame rate throttling for minimum battery consumption.
- **`app/src/main/kotlin/com/vision/app/mobile/AudioStreamManager.kt`**: Low-power, zero-overhead background microphone audio recorder streaming 16-bit Mono PCM at 16,000 Hz.
- **`app/src/main/kotlin/com/vision/app/mobile/BootReceiver.kt`**: BroadcastReceiver listening for `BOOT_COMPLETED`, `MY_PACKAGE_REPLACED`, and quickboot intents to automatically launch the background broadcast service on device startup.
- **`app/src/main/kotlin/com/vision/app/mobile/BackgroundStreamService.kt`**: Android Foreground Service providing 24/7 background video and audio transmission with zero-power standby (sensors shut off when disconnected), adaptive auto-discovery (fast bursts relaxing to deep sleep), instant opportunistic auto-reconnect via `ConnectivityManager.NetworkCallback`, `SharedPreferences` IP caching, and self-healing resurrection via `onTaskRemoved` and `AlarmManager`.
- **`app/src/main/kotlin/com/vision/app/mobile/MainActivity.kt`**: Flutter activity exposing platform MethodChannels (`com.vision.app/stream`) and EventChannels (`com.vision.app/events`) to the Dart application layer, including battery optimization bypass and auto-start toggles.
