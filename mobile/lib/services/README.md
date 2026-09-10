# Services Module

This directory contains application business logic, background execution control, network discovery, and telemetry listeners.

## Files

- **`wifi_service.dart`**: Retrieves active Wi-Fi state, local IP address, and connection parameters via platform channels.
- **`discovery_service.dart`**: Provides UDP network discovery socket listeners for identifying desktop server announcements across local subnets.
- **`stream_service.dart`**: Central ChangeNotifier orchestrating background service lifecycle (`startBroadcast`, `stopBroadcast`), managing streaming state transitions, telemetry, and remote hardware state (flash, quality, target FPS, audio status) synchronized with the server.
