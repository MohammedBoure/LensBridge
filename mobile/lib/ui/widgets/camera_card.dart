import 'package:flutter/material.dart';
import '../../config/app_config.dart';

/// Card widget visualizing a camera feed's state, FPS, and sensor parameters.
class CameraCard extends StatelessWidget {
  final String title;
  final String subtitle;
  final IconData icon;
  final bool isStreaming;
  final double fps;
  final Color themeColor;

  const CameraCard({
    super.key,
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.isStreaming,
    required this.fps,
    required this.themeColor,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppConfig.cardDark,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: isStreaming ? themeColor.withValues(alpha: 0.5) : Colors.white.withValues(alpha: 0.06),
          width: isStreaming ? 1.5 : 1.0,
        ),
        boxShadow: isStreaming
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
                      color: themeColor.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Icon(icon, color: themeColor, size: 20),
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
                  color: isStreaming ? AppConfig.accentGreen.withValues(alpha: 0.15) : Colors.white.withValues(alpha: 0.05),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  isStreaming ? 'LIVE' : 'STANDBY',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                    color: isStreaming ? AppConfig.accentGreen : AppConfig.textDim,
                    letterSpacing: 0.5,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _buildMetricItem('Framerate', '${fps.toStringAsFixed(1)} FPS', isStreaming ? AppConfig.accentGreen : AppConfig.textDim),
              _buildMetricItem('Resolution', '640 x 480', Colors.white70),
              _buildMetricItem('Codec', 'Hardware JPEG', Colors.white70),
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
