import 'package:flutter/material.dart';

/// Central application configuration parameters for Vision Cam.
class AppConfig {
  static const String appName = 'Vision Cam';
  static const int defaultHttpPort = 8765;
  static const int discoveryPort = 45454;
  static const String discoveryProbeMessage = 'VISION_DISCOVER_PROBE';
  static const String broadcastAddress = '255.255.255.255';

  // Video Streaming Defaults
  static const int defaultWidth = 640;
  static const int defaultHeight = 480;
  static const int defaultFps = 30;

  // Theme Colors
  static const Color primaryCyan = Color(0xFF00F2FE);
  static const Color primaryBlue = Color(0xFF4FACFE);
  static const Color bgDark = Color(0xFF0D1117);
  static const Color cardDark = Color(0xFF161B22);
  static const Color accentGreen = Color(0xFF00E676);
  static const Color accentRed = Color(0xFFFF3B30);
  static const Color textDim = Color(0xFF8B949E);
}
