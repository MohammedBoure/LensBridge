# Android Application Module (mobile/android/app)

This directory contains the Android application module configuration, Gradle build scripts, and native Kotlin source files.

## Files and Subdirectories

- **`build.gradle.kts`**: Defines Android SDK versions (compileSdk, minSdk, targetSdk) and manages third-party dependencies such as OkHttp for networking and AndroidX Core KTX.
- **`src/`**: Source root containing `AndroidManifest.xml` (manifest with permissions, cleartext traffic enabled, and services), network security configuration (`res/xml/network_security_config.xml`), Kotlin source files in `main/kotlin/`, and launcher resources in `main/res/`.
- **`proguard-rules.pro`**: ProGuard rules for release build optimization.
