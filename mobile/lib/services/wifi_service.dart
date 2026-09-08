import 'package:flutter/services.dart';

/// Models the device's local Wi-Fi connection parameters.
class WifiInfo {
  final bool isWifiEnabled;
  final String ip;
  final String ssid;
  final int rssi;

  const WifiInfo({
    required this.isWifiEnabled,
    required this.ip,
    required this.ssid,
    required this.rssi,
  });

  factory WifiInfo.fromMap(Map<dynamic, dynamic> map) {
    return WifiInfo(
      isWifiEnabled: map['isWifiEnabled'] as bool? ?? false,
      ip: map['ip'] as String? ?? '0.0.0.0',
      ssid: map['ssid'] as String? ?? 'Disconnected',
      rssi: map['rssi'] as int? ?? 0,
    );
  }

  bool get isConnected => isWifiEnabled && ip != '0.0.0.0' && ip != 'Not connected';
}

/// Service querying Android Wi-Fi state and local IP coordinates.
class WifiService {
  static const MethodChannel _channel = MethodChannel('com.vision.app/stream');

  static Future<WifiInfo> getWifiDetails() async {
    try {
      final res = await _channel.invokeMethod<Map<dynamic, dynamic>>('getWifiInfo');
      if (res != null) {
        return WifiInfo.fromMap(res);
      }
    } catch (e) {
      // Platform error
    }
    return const WifiInfo(isWifiEnabled: false, ip: '0.0.0.0', ssid: 'Unknown', rssi: 0);
  }
}
