package com.vision.app.mobile

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build
import android.util.Log

/**
 * Ensures the Vision background streaming service automatically starts
 * upon device boot, restart, or application update, providing true 24/7
 * uninterrupted operation without requiring manual user interaction.
 */
class BootReceiver : BroadcastReceiver() {

    companion object {
        private const val TAG = "VisionBootReceiver"
        const val PREFS_NAME = "VisionCamPrefs"
        const val KEY_AUTO_START_ENABLED = "auto_start_on_boot"
    }

    override fun onReceive(context: Context, intent: Intent) {
        val action = intent.action
        Log.d(TAG, "Received system broadcast: $action")

        if (action == Intent.ACTION_BOOT_COMPLETED ||
            action == Intent.ACTION_MY_PACKAGE_REPLACED ||
            action == "android.intent.action.QUICKBOOT_POWERON" ||
            action == "com.htc.intent.action.QUICKBOOT_POWERON"
        ) {
            val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            val isAutoStartEnabled = prefs.getBoolean(KEY_AUTO_START_ENABLED, true)

            if (!isAutoStartEnabled) {
                Log.d(TAG, "Auto-start on boot is disabled in preferences.")
                return
            }

            val serverIp = prefs.getString("last_server_ip", "") ?: ""
            val serverPort = prefs.getInt("last_server_port", 8765)
            val autoDiscover = prefs.getBoolean("last_auto_discover", true)
            val cameraMode = prefs.getString("last_camera_mode", "rear") ?: "rear"

            Log.i(TAG, "Auto-starting Vision BackgroundStreamService on boot (Target: $serverIp:$serverPort, Mode: $cameraMode)")

            val serviceIntent = Intent(context, BackgroundStreamService::class.java).apply {
                this.action = BackgroundStreamService.ACTION_START
                putExtra(BackgroundStreamService.EXTRA_SERVER_IP, serverIp)
                putExtra(BackgroundStreamService.EXTRA_SERVER_PORT, serverPort)
                putExtra(BackgroundStreamService.EXTRA_AUTO_DISCOVER, autoDiscover)
                putExtra(BackgroundStreamService.EXTRA_CAMERA_MODE, cameraMode)
            }

            try {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    context.startForegroundService(serviceIntent)
                } else {
                    context.startService(serviceIntent)
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to start BackgroundStreamService on boot: ${e.message}", e)
            }
        }
    }
}
