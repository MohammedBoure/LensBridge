import 'dart:async';
import 'dart:convert';
import 'dart:io';
import '../config/app_config.dart';

/// Representation of a discovered Desktop Vision Server on the local network.
class DiscoveredServer {
  final String serverName;
  final String ip;
  final int port;
  final String streamEndpoint;

  const DiscoveredServer({
    required this.serverName,
    required this.ip,
    required this.port,
    required this.streamEndpoint,
  });

  factory DiscoveredServer.fromJson(Map<String, dynamic> json) {
    return DiscoveredServer(
      serverName: json['server_name'] as String? ?? 'Desktop Server',
      ip: json['ip'] as String? ?? '',
      port: json['port'] as int? ?? 8765,
      streamEndpoint: json['stream_endpoint'] as String? ?? '',
    );
  }
}

/// UDP discovery client that searches for desktop server announcements over Wi-Fi.
class DiscoveryService {
  RawDatagramSocket? _socket;
  final _serverFoundController = StreamController<DiscoveredServer>.broadcast();

  Stream<DiscoveredServer> get onServerFound => _serverFoundController.stream;

  Future<void> startDiscovery() async {
    try {
      _socket = await RawDatagramSocket.bind(InternetAddress.anyIPv4, 0);
      _socket?.broadcastEnabled = true;

      _socket?.listen((event) {
        if (event == RawSocketEvent.read) {
          final datagram = _socket?.receive();
          if (datagram != null) {
            try {
              final text = utf8.decode(datagram.data);
              final json = jsonDecode(text) as Map<String, dynamic>;
              if (json['type'] == 'VISION_SERVER_ANNOUNCE') {
                final server = DiscoveredServer.fromJson(json);
                _serverFoundController.add(server);
              }
            } catch (_) {}
          }
        }
      });

      // Broadcast probe packet
      final probeBytes = utf8.encode(AppConfig.discoveryProbeMessage);
      _socket?.send(probeBytes, InternetAddress(AppConfig.broadcastAddress), AppConfig.discoveryPort);
    } catch (e) {
      // Socket exception or network transition
    }
  }

  void stopDiscovery() {
    _socket?.close();
    _socket = null;
  }

  void dispose() {
    stopDiscovery();
    _serverFoundController.close();
  }
}
