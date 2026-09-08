import 'dart:async';
import 'package:flutter/material.dart';
import '../config/app_config.dart';
import '../services/stream_service.dart';
import '../services/wifi_service.dart';
import 'widgets/camera_card.dart';
import 'widgets/status_badge.dart';
import 'widgets/stats_sheet.dart';

/// Main interactive dashboard of the Vision Cam mobile application.
/// Configured with fault tolerance for broken front cameras.
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
  String _selectedCameraMode = 'rear'; // Default to 'rear' since user's front camera is broken!

  @override
  void initState() {
    super.initState();
    _streamService.addListener(_onStreamStateChanged);
    _streamService.setCameraMode(_selectedCameraMode);
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
        cameraMode: _selectedCameraMode,
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
          cameraMode: _selectedCameraMode,
          onAutoDiscoverChanged: (val) {
            setModalState(() => _autoDiscover = val);
            setState(() => _autoDiscover = val);
          },
          onCameraModeChanged: (val) {
            setModalState(() => _selectedCameraMode = val);
            setState(() {
              _selectedCameraMode = val;
              _streamService.setCameraMode(val);
            });
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

    final isRearSelected = _selectedCameraMode == 'both' || _selectedCameraMode == 'rear';
    final isFrontSelected = _selectedCameraMode == 'both' || _selectedCameraMode == 'front';

    final bool isFrontFunctional = isFrontSelected && (!isStreaming || _streamService.isFrontActive);

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
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Wi-Fi and Server Badges
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

              const SizedBox(height: 14),

              // Quick Mode Switcher Pill Tabs
              Container(
                padding: const EdgeInsets.all(4),
                decoration: BoxDecoration(
                  color: AppConfig.cardDark,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
                ),
                child: Row(
                  children: [
                    Expanded(
                      child: _buildModeTab(
                        label: 'Back Only',
                        mode: 'rear',
                        isRecommended: true,
                      ),
                    ),
                    Expanded(
                      child: _buildModeTab(
                        label: 'Dual Cams',
                        mode: 'both',
                        isRecommended: false,
                      ),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 14),

              // Camera Sensor Cards
              Expanded(
                child: ListView(
                  physics: const BouncingScrollPhysics(),
                  children: [
                    CameraCard(
                      title: 'Back Camera',
                      subtitle: 'Primary Environment Sensor',
                      icon: Icons.camera_rear,
                      isStreaming: isStreaming && isRearSelected,
                      isAvailable: isRearSelected,
                      fps: _streamService.rearFps,
                      themeColor: AppConfig.primaryCyan,
                      statusNote: isRearSelected ? 'Broadcasting smoothly at high framerate.' : 'Disabled in mode settings.',
                    ),
                    const SizedBox(height: 12),
                    CameraCard(
                      title: 'Front Camera',
                      subtitle: 'User Sensor (Fault-Protected)',
                      icon: Icons.camera_front,
                      isStreaming: isStreaming && isFrontSelected,
                      isAvailable: isFrontFunctional,
                      fps: _streamService.frontFps,
                      themeColor: const Color(0xFFFF6B6B),
                      statusNote: !isFrontSelected
                          ? 'Bypassed (Back Camera Mode active for non-working front sensor).'
                          : (isStreaming && !_streamService.isFrontActive
                              ? 'Front camera not responding. App safely continuing with Back Camera.'
                              : 'Front camera active with hardware fault-guard.'),
                    ),
                    const SizedBox(height: 14),

                    // Information box
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.03),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: Colors.white.withValues(alpha: 0.06)),
                      ),
                      child: const Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Icon(Icons.shield_outlined, size: 20, color: AppConfig.accentGreen),
                          SizedBox(width: 10),
                          Expanded(
                            child: Text(
                              'Fault Protection Active: Even if one camera hardware fails or is broken, the broadcast runs continuously on the working sensor without interruption.',
                              style: TextStyle(fontSize: 11, color: AppConfig.textDim, height: 1.4),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 14),

              // Big Broadcast Button
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

  Widget _buildModeTab({required String label, required String mode, required bool isRecommended}) {
    final isSelected = _selectedCameraMode == mode;
    return GestureDetector(
      onTap: () {
        if (!_streamService.isBroadcasting) {
          setState(() {
            _selectedCameraMode = mode;
            _streamService.setCameraMode(mode);
          });
        }
      },
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(vertical: 8),
        decoration: BoxDecoration(
          color: isSelected ? AppConfig.primaryBlue : Colors.transparent,
          borderRadius: BorderRadius.circular(8),
        ),
        child: Center(
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                label,
                style: TextStyle(
                  color: isSelected ? Colors.white : AppConfig.textDim,
                  fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                  fontSize: 12,
                ),
              ),
              if (isRecommended) ...[
                const SizedBox(width: 4),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
                  decoration: BoxDecoration(
                    color: AppConfig.accentGreen.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: const Text('SAFE', style: TextStyle(color: AppConfig.accentGreen, fontSize: 9, fontWeight: FontWeight.bold)),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
