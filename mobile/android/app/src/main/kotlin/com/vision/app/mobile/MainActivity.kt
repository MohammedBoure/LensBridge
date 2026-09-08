package com.vision.app.mobile

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.wifi.WifiManager
import android.os.Build
import android.os.Bundle
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodChannel
import java.net.InetAddress
import java.nio.ByteOrder

/**
 * MainActivity bridging Flutter Dart UI with native Android background services
 * and concurrent camera capture hardware.
 */
class MainActivity : FlutterActivity() {

    private val METHOD_CHANNEL = "com.vision.app/stream"
    private val EVENT_CHANNEL = "com.vision.app/events"
    private val PERMISSION_REQUEST_CODE = 101

    private var eventSink: EventChannel.EventSink? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        // Method Channel
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, METHOD_CHANNEL).setMethodCallHandler { call, result ->
            when (call.method) {
                "startBroadcast" -> {
                    val serverIp = call.argument<String>("serverIp") ?: ""
                    val serverPort = call.argument<Int>("serverPort") ?: 8765
                    val autoDiscover = call.argument<Boolean>("autoDiscover") ?: true
                    val cameraMode = call.argument<String>("cameraMode") ?: "both"

                    startBroadcastService(serverIp, serverPort, autoDiscover, cameraMode)
                    result.success(true)
                }
                "stopBroadcast" -> {
                    stopBroadcastService()
                    result.success(true)
                }
                "isBroadcasting" -> {
                    result.success(BackgroundStreamService.isServiceRunning)
                }
                "checkConcurrentSupport" -> {
                    val cameraManager = DualCameraManager(this)
                    result.success(cameraManager.isConcurrentSupported())
                }
                "getWifiInfo" -> {
                    result.success(getWifiDetails())
                }
                "requestPermissions" -> {
                    requestAppPermissions()
                    result.success(true)
                }
                else -> result.notImplemented()
            }
        }

        // Event Channel for telemetry and status updates
        EventChannel(flutterEngine.dartExecutor.binaryMessenger, EVENT_CHANNEL).setStreamHandler(
            object : EventChannel.StreamHandler {
                override fun onListen(arguments: Any?, events: EventChannel.EventSink?) {
                    eventSink = events
                }

                override fun onCancel(arguments: Any?) {
                    eventSink = null
                }
            }
        )

        // Register callback from background service
        BackgroundStreamService.eventCallback = { state, payload ->
            runOnUiThread {
                eventSink?.success(payload)
            }
        }
    }

    private fun startBroadcastService(serverIp: String, serverPort: Int, autoDiscover: Boolean, cameraMode: String) {
        val intent = Intent(this, BackgroundStreamService::class.java).apply {
            action = BackgroundStreamService.ACTION_START
            putExtra(BackgroundStreamService.EXTRA_SERVER_IP, serverIp)
            putExtra(BackgroundStreamService.EXTRA_SERVER_PORT, serverPort)
            putExtra(BackgroundStreamService.EXTRA_AUTO_DISCOVER, autoDiscover)
            putExtra(BackgroundStreamService.EXTRA_CAMERA_MODE, cameraMode)
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent)
        } else {
            startService(intent)
        }
    }

    private fun stopBroadcastService() {
        val intent = Intent(this, BackgroundStreamService::class.java).apply {
            action = BackgroundStreamService.ACTION_STOP
        }
        startService(intent)
    }

    private fun requestAppPermissions() {
        val permissions = mutableListOf(
            Manifest.permission.CAMERA,
            Manifest.permission.ACCESS_NETWORK_STATE,
            Manifest.permission.ACCESS_WIFI_STATE
        )

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            permissions.add(Manifest.permission.POST_NOTIFICATIONS)
        }

        val needed = permissions.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }

        if (needed.isNotEmpty()) {
            ActivityCompat.requestPermissions(this, needed.toTypedArray(), PERMISSION_REQUEST_CODE)
        }
    }

    private fun getWifiDetails(): Map<String, Any> {
        val wifiManager = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
        val isWifiEnabled = wifiManager.isWifiEnabled
        val ipAddressInt = wifiManager.connectionInfo.ipAddress
        val ipStr = if (ipAddressInt != 0) {
            val bytes = if (ByteOrder.nativeOrder() == ByteOrder.LITTLE_ENDIAN) {
                Integer.reverseBytes(ipAddressInt)
            } else {
                ipAddressInt
            }
            try {
                InetAddress.getByAddress(
                    byteArrayOf(
                        (bytes ushr 24 and 0xff).toByte(),
                        (bytes ushr 16 and 0xff).toByte(),
                        (bytes ushr 8 and 0xff).toByte(),
                        (bytes and 0xff).toByte()
                    )
                ).hostAddress ?: "127.0.0.1"
            } catch (e: Exception) {
                "0.0.0.0"
            }
        } else {
            "Not connected"
        }

        return mapOf(
            "isWifiEnabled" to isWifiEnabled,
            "ip" to ipStr,
            "ssid" to (wifiManager.connectionInfo.ssid ?: "Unknown"),
            "rssi" to wifiManager.connectionInfo.rssi
        )
    }
}
