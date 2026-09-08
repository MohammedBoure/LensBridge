import 'package:flutter/material.dart';
import '../../config/app_config.dart';

/// Card widget visualizing a camera feed's state, FPS, and sensor parameters.
/// Seamlessly displays fault-tolerance when a sensor (such as the front camera) is broken or disabled.
class CameraCard extends StatelessWidget {
  final String title;
  final String subtitle;
  final IconData icon;
  final bool isStreaming;
  final bool isAvailable;
  final double fps;
  final Color themeColor;
  final String? statusNote;

  const CameraCard({
    super.key,
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.isStreaming,
    this.isAvailable = true,
    required this.fps,
    required this.themeColor,
    this.statusNote,
  });

  @override
  Widget build(BuildContext context) {
    final bool isLive = isStreaming && isAvailable && fps > 0.0;
    final bool isBrokenOrDisabled = !isAvailable;

    Color badgeColor = AppConfig.textDim;
    String badgeText = 'STANDBY';

    if (isBrokenOrDisabled) {
      badgeColor = Colors.orange;
      badgeText = 'DISABLED / OFFLINE';
    } else if (isLive) {
      badgeColor = AppConfig.accentGreen;
      badgeText = 'LIVE';
    } else if (isStreaming) {
      badgeColor = AppConfig.primaryBlue;
      badgeText = 'CONNECTING';
    }

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppConfig.cardDark,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: isLive
              ? themeColor.withValues(alpha: 0.5)
              : (isBrokenOrDisabled ? Colors.orange.withValues(alpha: 0.3) : Colors.white.withValues(alpha: 0.06)),
          width: isLive ? 1.5 : 1.0,
        ),
        boxShadow: isLive
            ? [
                BoxShadow(
                  color: themeColor.withValues(alpha: 0.15),
                  blurRadius: 16,
                  offset: const Offset(0, 4),
                )
              ]
            : null,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: isBrokenOrDisabled
                          ? Colors.orange.withValues(alpha: 0.12)
                          : themeColor.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Icon(
                      icon,
                      color: isBrokenOrDisabled ? Colors.orange : themeColor,
                      size: 20,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        style: const TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w700,
                          color: Colors.white,
                        ),
                      ),
                      Text(
                        subtitle,
                        style: const TextStyle(
                          fontSize: 11,
                          color: AppConfig.textDim,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: badgeColor.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  badgeText,
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                    color: badgeColor,
                    letterSpacing: 0.5,
                  ),
                ),
              ),
            ],
          ),
          if (statusNote != null && statusNote!.isNotEmpty) ...[
            const SizedBox(height: 10),
            Text(
              statusNote!,
              style: TextStyle(
                fontSize: 11,
                color: isBrokenOrDisabled ? Colors.orange.shade300 : AppConfig.textDim,
              ),
            ),
          ],
          const SizedBox(height: 14),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _buildMetricItem(
                'Framerate',
                isBrokenOrDisabled ? 'N/A' : '${fps.toStringAsFixed(1)} FPS',
                isLive ? AppConfig.accentGreen : AppConfig.textDim,
              ),
              _buildMetricItem('Resolution', isBrokenOrDisabled ? 'Disabled' : '640 x 480', Colors.white70),
              _buildMetricItem('Fault Guard', 'Protected', AppConfig.accentGreen),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildMetricItem(String label, String value, Color valueColor) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(fontSize: 10, color: AppConfig.textDim),
        ),
        const SizedBox(height: 2),
        Text(
          value,
          style: TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.w600,
            color: valueColor,
            fontFamily: 'monospace',
          ),
        ),
      ],
    );
  }
}
