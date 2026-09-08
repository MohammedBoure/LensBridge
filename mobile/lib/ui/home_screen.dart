import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import '../config/app_config.dart';
import '../services/stream_service.dart';
import '../services/wifi_service.dart';
import 'widgets/camera_card.dart';
import 'widgets/status_badge.dart';
import 'widgets/stats_sheet.dart';

/// Main interactive dashboard of the Vision Cam mobile application.
/// Allows setting custom Server IP directly on screen, with fault tolerance for broken front cameras.
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final StreamService _streamService = StreamService();
  final TextEditingController _serverIpController = TextEditingController(text: '192.168.1.150');
  final TextEditingController _serverPortController = TextEditingController(text: '8000');

  WifiInfo _wifiInfo = const WifiInfo(isWifiEnabled: false, ip: '0.0.0.0', ssid: 'Scanning...', rssi: 0);
  Timer? _wifiPollTimer;
  bool _autoDiscover = false; // Default to manual/prefilled IP for rock-solid connection
  String _selectedCameraMode = 'rear'; // Default to 'rear' since user's front camera is broken!
  String? _pingResult;
  bool _isPinging = false;

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

  Future<void> _testConnection() async {
    final ip = _serverIpController.text.trim();
    final port = int.tryParse(_serverPortController.text.trim()) ?? 8000;
    if (ip.isEmpty) {
      setState(() => _pingResult = 'Please enter an IP address');
      return;
    }

    setState(() {
      _isPinging = true;
      _pingResult = 'Testing connection to $ip:$port...';
    });

    try {
      final client = HttpClient()..connectionTimeout = const Duration(seconds: 3);
      final req = await client.getUrl(Uri.parse('http://$ip:$port/api/status'));
      final res = await req.close();
      if (res.statusCode == 200) {
        final body = await res.transform(utf8.decoder).join();
        final json = jsonDecode(body);
        setState(() {
          _isPinging = false;
          _pingResult = '✓ Server Online (${json['status']})';
        });
      } else {
        setState(() {
          _isPinging = false;
          _pingResult = '✗ Server returned HTTP ${res.statusCode}';
        });
      }
    } catch (e) {
      setState(() {
        _isPinging = false;
        _pingResult = '✗ Cannot connect: $e';
      });
    }
  }

  Future<void> _toggleBroadcast() async {
    if (_streamService.isBroadcasting) {
      await _streamService.stopBroadcast();
    } else {
      final ip = _autoDiscover ? null : _serverIpController.text.trim();
      final port = int.tryParse(_serverPortController.text.trim()) ?? 8000;
      await _streamService.startBroadcast(
        serverIp: ip,
        serverPort: port,
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
          activeServerIp: _streamService.activeServerIp.isNotEmpty
              ? _streamService.activeServerIp
              : _serverIpController.text,
          manualIpController: _serverIpController,
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
    _serverIpController.dispose();
    _serverPortController.dispose();
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
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Top Status Badges
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  StatusBadge(
                    label: 'Wi-Fi',
                    value: _wifiInfo.isConnected ? _wifiInfo.ip : 'Connected',
                    dotColor: _wifiInfo.isConnected ? AppConfig.accentGreen : AppConfig.primaryCyan,
                    icon: Icons.wifi,
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

              const SizedBox(height: 12),

              // Server IP Configuration Card (Allows setting Server IP yourself!)
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: AppConfig.cardDark,
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(color: AppConfig.primaryCyan.withValues(alpha: 0.25)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Row(
                          children: [
                            Icon(Icons.dns, size: 16, color: AppConfig.primaryCyan),
                            SizedBox(width: 6),
                            Text(
                              'Server IP Address',
                              style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 13),
                            ),
                          ],
                        ),
                        Row(
                          children: [
                            Text(
                              _autoDiscover ? 'Auto-Detect' : 'Manual IP',
                              style: const TextStyle(color: AppConfig.textDim, fontSize: 11),
                            ),
                            Switch(
                              value: !_autoDiscover,
                              activeThumbColor: AppConfig.primaryCyan,
                              materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                              onChanged: isBroadcasting
                                  ? null
                                  : (val) {
                                      setState(() => _autoDiscover = !val);
                                    },
                            ),
                          ],
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),

                    if (!_autoDiscover) ...[
                      Row(
                        children: [
                          Expanded(
                            flex: 3,
                            child: TextField(
                              controller: _serverIpController,
                              enabled: !isBroadcasting,
                              style: const TextStyle(color: Colors.white, fontFamily: 'monospace', fontSize: 14),
                              decoration: InputDecoration(
                                isDense: true,
                                hintText: 'e.g. 192.168.1.150',
                                hintStyle: const TextStyle(color: Colors.white24),
                                filled: true,
                                fillColor: Colors.white.withValues(alpha: 0.05),
                                contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                                border: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(8),
                                  borderSide: BorderSide(color: Colors.white.withValues(alpha: 0.1)),
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            flex: 1,
                            child: TextField(
                              controller: _serverPortController,
                              enabled: !isBroadcasting,
                              keyboardType: TextInputType.number,
                              style: const TextStyle(color: Colors.white, fontFamily: 'monospace', fontSize: 14),
                              decoration: InputDecoration(
                                isDense: true,
                                hintText: '8000',
                                hintStyle: const TextStyle(color: Colors.white24),
                                filled: true,
                                fillColor: Colors.white.withValues(alpha: 0.05),
                                contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
                                border: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(8),
                                  borderSide: BorderSide(color: Colors.white.withValues(alpha: 0.1)),
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(width: 8),
                          IconButton.filledTonal(
                            onPressed: _isPinging ? null : _testConnection,
                            icon: _isPinging
                                ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2))
                                : const Icon(Icons.network_ping, size: 18),
                            tooltip: 'Test Connection',
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      // Quick Preset Chips
                      Row(
                        children: [
                          const Text('Presets: ', style: TextStyle(fontSize: 10, color: AppConfig.textDim)),
                          const SizedBox(width: 4),
                          _buildPresetChip('192.168.1.150 (PC Wi-Fi)', '192.168.1.150'),
                          const SizedBox(width: 6),
                          _buildPresetChip('10.0.2.2 (Emulator)', '10.0.2.2'),
                        ],
                      ),
                    ] else ...[
                      const Text(
                        'Scanning Wi-Fi network via UDP broadcast (Port 45454) for Desktop Server...',
                        style: TextStyle(fontSize: 11, color: AppConfig.textDim),
                      ),
                    ],

                    if (_pingResult != null) ...[
                      const SizedBox(height: 6),
                      Text(
                        _pingResult!,
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                          color: _pingResult!.startsWith('✓') ? AppConfig.accentGreen : AppConfig.accentRed,
                        ),
                      ),
                    ],
                  ],
                ),
              ),

              const SizedBox(height: 12),

              // Camera Mode Selector Tabs
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

              const SizedBox(height: 12),

              // Camera Sensor Cards
              Expanded(
                child: ListView(
                  physics: const BouncingScrollPhysics(),
                  children: [
                    CameraCard(
                      title: 'Back Camera',
                      subtitle: 'Primary Sensor',
                      icon: Icons.camera_rear,
                      isStreaming: isStreaming && isRearSelected,
                      isAvailable: isRearSelected,
                      fps: _streamService.rearFps,
                      themeColor: AppConfig.primaryCyan,
                      statusNote: isRearSelected ? 'Broadcasting live to PC.' : 'Disabled.',
                    ),
                    const SizedBox(height: 10),
                    CameraCard(
                      title: 'Front Camera',
                      subtitle: 'Fault-Protected Sensor',
                      icon: Icons.camera_front,
                      isStreaming: isStreaming && isFrontSelected,
                      isAvailable: isFrontFunctional,
                      fps: _streamService.frontFps,
                      themeColor: const Color(0xFFFF6B6B),
                      statusNote: !isFrontSelected
                          ? 'Bypassed (Back Camera Only mode active for damaged sensor).'
                          : (isStreaming && !_streamService.isFrontActive
                              ? 'Front camera not responding. Safely continuing on Back Camera.'
                              : 'Front camera active.'),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 12),

              // Big Broadcast Action Button
              Container(
                height: 54,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(16),
                  boxShadow: [
                    BoxShadow(
                      color: isBroadcasting
                          ? AppConfig.accentRed.withValues(alpha: 0.35)
                          : AppConfig.primaryBlue.withValues(alpha: 0.35),
                      blurRadius: 18,
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
                        size: 22,
                      ),
                      const SizedBox(width: 8),
                      Text(
                        isBroadcasting ? 'STOP BROADCASTING' : 'START BACKGROUND BROADCAST',
                        style: const TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.bold,
                          letterSpacing: 0.8,
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

  Widget _buildPresetChip(String label, String ip) {
    return GestureDetector(
      onTap: () {
        setState(() {
          _serverIpController.text = ip;
          _pingResult = null;
        });
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(6),
        ),
        child: Text(
          label,
          style: const TextStyle(color: AppConfig.primaryCyan, fontSize: 10, fontFamily: 'monospace'),
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
