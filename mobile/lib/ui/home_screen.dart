import 'dart:async';
import 'package:flutter/material.dart';
import '../config/app_config.dart';
import '../services/stream_service.dart';
import '../services/wifi_service.dart';
import 'widgets/camera_card.dart';
import 'widgets/status_badge.dart';
import 'widgets/stats_sheet.dart';

/// Main interactive dashboard of the Vision Cam mobile application.
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final StreamService _streamService = StreamService();
  final TextEditingController _manualIpController = TextEditingController();

  WifiInfo _wifiInfo = const WifiInfo(isWifiEnabled: false, ip: '0.0.0.0', ssid: 'Scanning...', rssi: 0);
  Timer? _wifiPollTimer;
  bool _autoDiscover = true;

  @override
  void initState() {
    super.initState();
    _streamService.addListener(_onStreamStateChanged);
    _refreshWifi();
    _wifiPollTimer = Timer.periodic(const Duration(seconds: 4), (_) => _refreshWifi());
  }

  void _onStreamStateChanged() {
    if (mounted) setState(() {});
  }

  Future<void> _refreshWifi() async {
    final info = await WifiService.getWifiDetails();
    if (mounted) {
      setState(() {
        _wifiInfo = info;
      });
    }
  }

  Future<void> _toggleBroadcast() async {
    if (_streamService.isBroadcasting) {
      await _streamService.stopBroadcast();
    } else {
      final ip = _autoDiscover ? null : _manualIpController.text.trim();
      await _streamService.startBroadcast(
        serverIp: ip,
        autoDiscover: _autoDiscover,
      );
    }
  }

  void _openSettings() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => StatefulBuilder(
        builder: (context, setModalState) => StatsSheet(
          isConcurrentSupported: _streamService.isConcurrentSupported,
          activeServerIp: _streamService.activeServerIp,
          manualIpController: _manualIpController,
          autoDiscover: _autoDiscover,
          onAutoDiscoverChanged: (val) {
            setModalState(() => _autoDiscover = val);
            setState(() => _autoDiscover = val);
          },
          onSaveSettings: () {
            Navigator.pop(context);
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Settings updated successfully.')),
            );
          },
        ),
      ),
    );
  }

  @override
  void dispose() {
    _wifiPollTimer?.cancel();
    _streamService.removeListener(_onStreamStateChanged);
    _streamService.dispose();
    _manualIpController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isStreaming = _streamService.isStreaming;
    final isBroadcasting = _streamService.isBroadcasting;

    return Scaffold(
      backgroundColor: AppConfig.bgDark,
      appBar: AppBar(
        backgroundColor: AppConfig.cardDark,
        elevation: 0,
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(
                color: AppConfig.primaryCyan.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Icon(Icons.videocam, color: AppConfig.primaryCyan, size: 20),
            ),
            const SizedBox(width: 10),
            const Text(
              'VISION CAM',
              style: TextStyle(fontWeight: FontWeight.w800, letterSpacing: 1.2, fontSize: 18),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings_outlined, color: Colors.white70),
            onPressed: _openSettings,
          ),
        ],
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Wi-Fi and Discovery Status Badges
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  StatusBadge(
                    label: 'Wi-Fi',
                    value: _wifiInfo.isConnected ? _wifiInfo.ip : 'Offline',
                    dotColor: _wifiInfo.isConnected ? AppConfig.accentGreen : AppConfig.accentRed,
                    icon: _wifiInfo.isConnected ? Icons.wifi : Icons.wifi_off,
                  ),
                  StatusBadge(
                    label: 'Server Link',
                    value: _streamService.statusMessage,
                    dotColor: isStreaming
                        ? AppConfig.accentGreen
                        : (isBroadcasting ? Colors.orange : AppConfig.accentRed),
                  ),
                ],
              ),

              const SizedBox(height: 18),

              // Dual Camera Sensor Telemetry Cards
              Expanded(
                child: ListView(
                  physics: const BouncingScrollPhysics(),
                  children: [
                    CameraCard(
                      title: 'Back Camera',
                      subtitle: 'Primary Environment Sensor',
                      icon: Icons.camera_rear,
                      isStreaming: isStreaming,
                      fps: _streamService.rearFps,
                      themeColor: AppConfig.primaryCyan,
                    ),
                    const SizedBox(height: 14),
                    CameraCard(
                      title: 'Front Camera',
                      subtitle: 'Concurrent User Sensor',
                      icon: Icons.camera_front,
                      isStreaming: isStreaming,
                      fps: _streamService.frontFps,
                      themeColor: const Color(0xFFFF6B6B),
                    ),
                    const SizedBox(height: 16),

                    // Information box explaining background broadcast
                    Container(
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.03),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: Colors.white.withValues(alpha: 0.06)),
                      ),
                      child: const Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Icon(Icons.all_inclusive, size: 20, color: AppConfig.primaryBlue),
                          SizedBox(width: 10),
                          Expanded(
                            child: Text(
                              'Background Mode: Camera and network streaming will stay active when you switch apps or turn off your phone screen.',
                              style: TextStyle(fontSize: 12, color: AppConfig.textDim, height: 1.4),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 16),

              // Big Action Button
              Container(
                height: 56,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(16),
                  boxShadow: [
                    BoxShadow(
                      color: isBroadcasting
                          ? AppConfig.accentRed.withValues(alpha: 0.3)
                          : AppConfig.primaryBlue.withValues(alpha: 0.3),
                      blurRadius: 20,
                      offset: const Offset(0, 4),
                    ),
                  ],
                ),
                child: ElevatedButton(
                  onPressed: _toggleBroadcast,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: isBroadcasting ? AppConfig.accentRed : AppConfig.primaryBlue,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                    elevation: 0,
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(
                        isBroadcasting ? Icons.stop_circle_outlined : Icons.sensors,
                        color: Colors.white,
                        size: 24,
                      ),
                      const SizedBox(width: 10),
                      Text(
                        isBroadcasting ? 'STOP BROADCASTING' : 'START BACKGROUND BROADCAST',
                        style: const TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.bold,
                          letterSpacing: 1.0,
                          fontSize: 14,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
