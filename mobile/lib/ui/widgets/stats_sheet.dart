import 'package:flutter/material.dart';
import '../../config/app_config.dart';

/// Modal bottom sheet for network settings, hardware capabilities, and manual IP configuration.
class StatsSheet extends StatelessWidget {
  final bool isConcurrentSupported;
  final String activeServerIp;
  final TextEditingController manualIpController;
  final bool autoDiscover;
  final ValueChanged<bool> onAutoDiscoverChanged;
  final VoidCallback onSaveSettings;

  const StatsSheet({
    super.key,
    required this.isConcurrentSupported,
    required this.activeServerIp,
    required this.manualIpController,
    required this.autoDiscover,
    required this.onAutoDiscoverChanged,
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
              'Broadcast & Network Settings',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.white),
            ),
            const SizedBox(height: 16),

            // Hardware Capability Pill
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: isConcurrentSupported ? AppConfig.accentGreen.withValues(alpha: 0.1) : Colors.orange.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                  color: isConcurrentSupported ? AppConfig.accentGreen.withValues(alpha: 0.3) : Colors.orange.withValues(alpha: 0.3),
                ),
              ),
              child: Row(
                children: [
                  Icon(
                    isConcurrentSupported ? Icons.check_circle_outline : Icons.info_outline,
                    color: isConcurrentSupported ? AppConfig.accentGreen : Colors.orange,
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          isConcurrentSupported
                              ? 'Hardware Dual-ISP Active'
                              : 'Standard Multi-Camera Mode',
                          style: const TextStyle(fontWeight: FontWeight.w600, color: Colors.white, fontSize: 13),
                        ),
                        Text(
                          isConcurrentSupported
                              ? 'Hardware supports concurrent front + rear sensors.'
                              : 'Software multi-camera capture pipeline enabled.',
                          style: const TextStyle(fontSize: 11, color: AppConfig.textDim),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 20),

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

            // Background Service Notice
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.03),
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Row(
                children: [
                  Icon(Icons.lock_clock, size: 20, color: AppConfig.primaryCyan),
                  SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      'Background execution uses Android Foreground Service to keep camera & Wi-Fi stream active even if screen is locked.',
                      style: TextStyle(fontSize: 11, color: AppConfig.textDim),
                    ),
                  ),
                ],
              ),
            ),

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
}
