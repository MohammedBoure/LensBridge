# Android Application Module (mobile/android/app)

This directory contains the Android application module configuration, Gradle build scripts, and native Kotlin source files.

## Files and Subdirectories

- **`build.gradle.kts`**: Defines Android SDK versions (compileSdk, minSdk, targetSdk) and manages third-party dependencies such as OkHttp for networking and AndroidX Core KTX.
- **`src/`**: Source root containing `AndroidManifest.xml` (manifest with camera, microphone, and foreground permissions), network security configuration (`res/xml/network_security_config.xml`), Kotlin source files in `main/kotlin/` (`DualCameraManager.kt`, `AudioStreamManager.kt`, `BackgroundStreamService.kt`, `MainActivity.kt`), and launcher resources in `main/res/`.
- **`proguard-rules.pro`**: ProGuard rules for release build optimization.
