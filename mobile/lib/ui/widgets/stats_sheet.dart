import 'package:flutter/material.dart';
import '../../config/app_config.dart';

/// Modal bottom sheet for network settings, camera selection, and fault-tolerant configuration.
class StatsSheet extends StatelessWidget {
  final bool isConcurrentSupported;
  final String activeServerIp;
  final TextEditingController manualIpController;
  final bool autoDiscover;
  final String cameraMode;
  final ValueChanged<bool> onAutoDiscoverChanged;
  final ValueChanged<String> onCameraModeChanged;
  final VoidCallback onSaveSettings;

  const StatsSheet({
    super.key,
    required this.isConcurrentSupported,
    required this.activeServerIp,
    required this.manualIpController,
    required this.autoDiscover,
    required this.cameraMode,
    required this.onAutoDiscoverChanged,
    required this.onCameraModeChanged,
    required this.onSaveSettings,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: EdgeInsets.only(
        left: 20,
        right: 20,
        top: 24,
        bottom: MediaQuery.of(context).viewInsets.bottom + 24,
      ),
      decoration: const BoxDecoration(
        color: AppConfig.cardDark,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: Colors.white24,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: 18),
            const Text(
              'Broadcast & Camera Settings',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.white),
            ),
            const SizedBox(height: 16),

            // Camera Sensor Selection
            const Text(
              'Active Camera Mode',
              style: TextStyle(color: AppConfig.textDim, fontSize: 13, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 8),
            Container(
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.04),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
              ),
              child: Column(
                children: [
                  _buildCameraOption(
                    title: 'Back Camera Only',
                    subtitle: 'Recommended if your front camera is damaged or not working',
                    value: 'rear',
                    noteColor: AppConfig.accentGreen,
                  ),
                  const Divider(height: 1, color: Colors.white12),
                  _buildCameraOption(
                    title: 'Both Cameras (Dual Broadcast)',
                    subtitle: 'Broadcasts both front & rear concurrently (with auto-fallback)',
                    value: 'both',
                    noteColor: AppConfig.textDim,
                  ),
                  const Divider(height: 1, color: Colors.white12),
                  _buildCameraOption(
                    title: 'Front Camera Only',
                    subtitle: 'Broadcasts only the front selfie sensor',
                    value: 'front',
                    noteColor: AppConfig.textDim,
                  ),
                ],
              ),
            ),

            const SizedBox(height: 16),

            // Hardware Capability Pill
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: isConcurrentSupported ? AppConfig.accentGreen.withValues(alpha: 0.1) : Colors.blue.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                  color: isConcurrentSupported ? AppConfig.accentGreen.withValues(alpha: 0.3) : Colors.blue.withValues(alpha: 0.3),
                ),
              ),
              child: Row(
                children: [
                  Icon(
                    isConcurrentSupported ? Icons.check_circle_outline : Icons.info_outline,
                    color: isConcurrentSupported ? AppConfig.accentGreen : AppConfig.primaryBlue,
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          isConcurrentSupported ? 'Hardware Dual-ISP Active' : 'Fault-Tolerant Camera Guard Active',
                          style: const TextStyle(fontWeight: FontWeight.w600, color: Colors.white, fontSize: 13),
                        ),
                        Text(
                          isConcurrentSupported
                              ? 'Device hardware supports concurrent front & back sensors.'
                              : 'If a camera fails or is broken, the app runs safely on the working sensor.',
                          style: const TextStyle(fontSize: 11, color: AppConfig.textDim),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 16),

            // Auto-Discovery Switch
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Wi-Fi Auto-Discovery (UDP 45454)', style: TextStyle(color: Colors.white, fontSize: 14)),
              subtitle: const Text('Automatically connects to server when on same Wi-Fi', style: TextStyle(color: AppConfig.textDim, fontSize: 12)),
              value: autoDiscover,
              activeThumbColor: AppConfig.primaryCyan,
              onChanged: onAutoDiscoverChanged,
            ),

            if (!autoDiscover) ...[
              const SizedBox(height: 12),
              const Text('Manual Server IP / Hostname', style: TextStyle(color: AppConfig.textDim, fontSize: 12)),
              const SizedBox(height: 6),
              TextField(
                controller: manualIpController,
                style: const TextStyle(color: Colors.white, fontFamily: 'monospace'),
                decoration: InputDecoration(
                  hintText: 'e.g. 192.168.1.50',
                  hintStyle: const TextStyle(color: Colors.white24),
                  filled: true,
                  fillColor: Colors.white.withValues(alpha: 0.05),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(10),
                    borderSide: BorderSide(color: Colors.white.withValues(alpha: 0.1)),
                  ),
                ),
              ),
            ],

            const SizedBox(height: 20),

            SizedBox(
              width: double.infinity,
              height: 46,
              child: ElevatedButton(
                onPressed: onSaveSettings,
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppConfig.primaryBlue,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                child: const Text('Apply Settings', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCameraOption({
    required String title,
    required String subtitle,
    required String value,
    required Color noteColor,
  }) {
    final isSelected = cameraMode == value;
    return InkWell(
      onTap: () => onCameraModeChanged(value),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        child: Row(
          children: [
            Container(
              width: 20,
              height: 20,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                border: Border.all(
                  color: isSelected ? AppConfig.primaryCyan : Colors.white38,
                  width: 2,
                ),
              ),
              child: isSelected
                  ? Center(
                      child: Container(
                        width: 10,
                        height: 10,
                        decoration: const BoxDecoration(
                          shape: BoxShape.circle,
                          color: AppConfig.primaryCyan,
                        ),
                      ),
                    )
                  : null,
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 14,
                      fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(subtitle, style: TextStyle(color: noteColor, fontSize: 11)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
