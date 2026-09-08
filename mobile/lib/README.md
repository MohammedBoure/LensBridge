# Vision Mobile Application Core (lib/)

This directory houses the Dart source code for the Vision Cam mobile application.

## Directory Structure and Files

- **`main.dart`**: Application entry point configuring Material 3 dark theming and window overlays.
- **`config/`**: Contains `app_config.dart` defining network ports, UDP discovery parameters, and styling colors.
- **`services/`**: Houses application business logic, including `stream_service.dart` (state & background service controller), `wifi_service.dart` (Wi-Fi detection), and `discovery_service.dart` (UDP discovery client).
- **`ui/`**: Contains `home_screen.dart` (main dashboard) and `widgets/` (reusable UI components).
