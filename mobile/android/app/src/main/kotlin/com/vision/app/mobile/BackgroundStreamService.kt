package com.vision.app.mobile

import android.app.*
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.net.wifi.WifiManager
import android.os.*
import android.util.Log
import androidx.core.app.NotificationCompat
import okhttp3.*
import okio.ByteString
import okio.ByteString.Companion.toByteString
import org.json.JSONObject
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Foreground Service that persists camera capture and WebSocket streaming
 * in the background even when the device is locked or the app is minimized.
 * Supports fault-tolerant single or dual-camera streaming.
 */
class BackgroundStreamService : Service() {

    companion object {
        private const val TAG = "BackgroundStreamService"
        const val CHANNEL_ID = "vision_stream_service_channel"
        const val NOTIFICATION_ID = 8821

        const val ACTION_START = "com.vision.app.START_STREAM"
        const val ACTION_STOP = "com.vision.app.STOP_STREAM"

        const val EXTRA_SERVER_IP = "extra_server_ip"
        const val EXTRA_SERVER_PORT = "extra_server_port"
        const val EXTRA_AUTO_DISCOVER = "extra_auto_discover"
        const val EXTRA_CAMERA_MODE = "extra_camera_mode"

        var isServiceRunning = false
            private set

        var eventCallback: ((String, Map<String, Any>) -> Unit)? = null
    }

    private lateinit var cameraManager: DualCameraManager
    private var wakeLock: PowerManager.WakeLock? = null
    private var wifiLock: WifiManager.WifiLock? = null

    private var okHttpClient: OkHttpClient? = null
    private var webSocket: WebSocket? = null

    private var targetServerIp: String? = null
    private var targetServerPort: Int = 8000
    private var autoDiscover: Boolean = true
    private var cameraMode: String = "both"

    private val isStreaming = AtomicBoolean(false)
    private var discoveryThread: Thread? = null

    // Camera availability tracking
    private var isRearActive = false
    private var isFrontActive = false
    private var rearMessage = "Standby"
    private var frontMessage = "Standby"

    // Frame tracking for telemetry
    private var rearFramesCount = 0
    private var frontFramesCount = 0
    private var lastStatsUpdate = System.currentTimeMillis()

    override fun onCreate() {
        super.onCreate()
        cameraManager = DualCameraManager(this)
        createNotificationChannel()
        acquireLocks()
        initHttpClient()
    }

    private fun initHttpClient() {
        okHttpClient = OkHttpClient.Builder()
            .readTimeout(10, TimeUnit.SECONDS)
            .writeTimeout(10, TimeUnit.SECONDS)
            .pingInterval(5, TimeUnit.SECONDS)
            .build()
    }

    private fun acquireLocks() {
        try {
            val powerManager = getSystemService(Context.POWER_SERVICE) as PowerManager
            wakeLock = powerManager.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "VisionCam::WakeLock").apply {
                acquire(12 * 60 * 60 * 1000L) // 12 hours max safety
            }

            val wifiManager = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
            wifiLock = wifiManager.createWifiLock(WifiManager.WIFI_MODE_FULL_HIGH_PERF, "VisionCam::WifiLock").apply {
                acquire()
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed acquiring WakeLock or WifiLock", e)
        }
    }

    private fun releaseLocks() {
        try {
            if (wakeLock?.isHeld == true) wakeLock?.release()
            if (wifiLock?.isHeld == true) wifiLock?.release()
        } catch (e: Exception) {
            Log.e(TAG, "Error releasing locks", e)
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> {
                targetServerIp = intent.getStringExtra(EXTRA_SERVER_IP)
                targetServerPort = intent.getIntExtra(EXTRA_SERVER_PORT, 8000)
                autoDiscover = intent.getBooleanExtra(EXTRA_AUTO_DISCOVER, true)
                cameraMode = intent.getStringExtra(EXTRA_CAMERA_MODE) ?: "both"

                startForegroundNotification()
                isServiceRunning = true

                if (autoDiscover && (targetServerIp == null || targetServerIp!!.isEmpty())) {
                    startAutoDiscovery()
                } else {
                    targetServerIp?.let { connectWebSocket(it, targetServerPort) }
                }
            }
            ACTION_STOP -> {
                stopStream()
                stopSelf()
            }
        }
        return START_STICKY
    }

    private fun startForegroundNotification() {
        val modeDesc = when (cameraMode) {
            "rear" -> "Broadcasting rear camera in background"
            "front" -> "Broadcasting front camera in background"
            else -> "Broadcasting cameras in background"
        }

        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Vision Cam Active")
            .setContentText(modeDesc)
            .setSmallIcon(android.R.drawable.ic_menu_camera)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .build()

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            var serviceType = ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                serviceType = serviceType or ServiceInfo.FOREGROUND_SERVICE_TYPE_CAMERA
            }
            startForeground(NOTIFICATION_ID, notification, serviceType)
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Vision Live Stream Service",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Keeps Vision camera broadcasting in the background"
            }
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
    }

    private fun startAutoDiscovery() {
        notifyEvent("DISCOVERING", mapOf("status" to "Scanning Wi-Fi for Desktop Server..."))

        discoveryThread = Thread {
            var socket: DatagramSocket? = null
            try {
                socket = DatagramSocket().apply {
                    broadcast = true
                    soTimeout = 2000
                }

                val probeMsg = "VISION_DISCOVER_PROBE".toByteArray()
                val probePacket = DatagramPacket(
                    probeMsg,
                    probeMsg.size,
                    InetAddress.getByName("255.255.255.255"),
                    45454
                )

                val buffer = ByteArray(1024)
                val responsePacket = DatagramPacket(buffer, buffer.size)

                while (isServiceRunning && !isStreaming.get()) {
                    try {
                        socket.send(probePacket)
                        socket.receive(responsePacket)

                        val respJson = String(responsePacket.data, 0, responsePacket.length)
                        val json = JSONObject(respJson)
                        if (json.optString("type") == "VISION_SERVER_ANNOUNCE") {
                            val ip = json.optString("ip", responsePacket.address.hostAddress)
                            val port = json.optInt("port", 8000)
                            Log.d(TAG, "Discovered Vision Server at $ip:$port")
                            connectWebSocket(ip, port)
                            break
                        }
                    } catch (e: Exception) {
                        Thread.sleep(1500)
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "Discovery error", e)
            } finally {
                socket?.close()
            }
        }.apply { start() }
    }

    private fun connectWebSocket(ip: String, port: Int) {
        val model = "${Build.MANUFACTURER} ${Build.MODEL}"
        val url = "ws://$ip:$port/ws/phone?device=${java.net.URLEncoder.encode(model, "UTF-8")}"

        notifyEvent("CONNECTING", mapOf("serverIp" to ip, "port" to port))

        val request = Request.Builder().url(url).build()
        webSocket = okHttpClient?.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.d(TAG, "WebSocket connected to $ip:$port")
                isStreaming.set(true)
                notifyEvent("STREAMING", mapOf("serverIp" to ip, "status" to "Connected"))

                // Start hardware camera capture with fault-tolerant error listener
                cameraManager.startStreaming(
                    cameraMode = cameraMode,
                    targetWidth = 640,
                    targetHeight = 480,
                    listener = object : DualCameraManager.FrameListener {
                        override fun onFrameAvailable(cameraCode: Byte, jpegBytes: ByteArray) {
                            if (!isStreaming.get()) return

                            // Packet structure: [CameraCode (1 byte)] + [JPEG Bytes]
                            val packet = ByteArray(1 + jpegBytes.size)
                            packet[0] = cameraCode
                            System.arraycopy(jpegBytes, 0, packet, 1, jpegBytes.size)

                            webSocket.send(packet.toByteString(0, packet.size))

                            // Update FPS metrics
                            if (cameraCode == DualCameraManager.CAMERA_REAR) rearFramesCount++ else frontFramesCount++
                            trackTelemetry()
                        }
                    },
                    statusListener = object : DualCameraManager.StateListener {
                        override fun onCameraStateChanged(cameraCode: Byte, isAvailable: Boolean, message: String) {
                            if (cameraCode == DualCameraManager.CAMERA_REAR) {
                                isRearActive = isAvailable
                                rearMessage = message
                            } else {
                                isFrontActive = isAvailable
                                frontMessage = message
                            }

                            // Send state update to server
                            sendCameraStatusToServer()

                            // Notify Flutter UI
                            notifyEvent("CAMERA_STATUS", mapOf(
                                "rearActive" to isRearActive,
                                "rearMessage" to rearMessage,
                                "frontActive" to isFrontActive,
                                "frontMessage" to frontMessage,
                            ))
                        }
                    }
                )
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.e(TAG, "WebSocket failure: ${t.message}")
                isStreaming.set(false)
                cameraManager.stopStreaming()
                notifyEvent("DISCONNECTED", mapOf("error" to (t.message ?: "Connection error")))

                // Auto-reconnect if running
                if (isServiceRunning) {
                    Thread.sleep(3000)
                    if (isServiceRunning) connectWebSocket(ip, port)
                }
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                Log.d(TAG, "WebSocket closed: $reason")
                isStreaming.set(false)
                cameraManager.stopStreaming()
                notifyEvent("DISCONNECTED", mapOf("reason" to reason))
            }
        })
    }

    private fun sendCameraStatusToServer() {
        try {
            val json = JSONObject().apply {
                put("type", "CAMERA_STATUS")
                put("rear_active", isRearActive)
                put("rear_message", rearMessage)
                put("front_active", isFrontActive)
                put("front_message", frontMessage)
            }
            webSocket?.send(json.toString())
        } catch (e: Exception) {
            Log.w(TAG, "Failed to send camera status to server: ${e.message}")
        }
    }

    private fun trackTelemetry() {
        val now = System.currentTimeMillis()
        val elapsed = now - lastStatsUpdate
        if (elapsed >= 1000) {
            val rearFps = (rearFramesCount * 1000f) / elapsed
            val frontFps = (frontFramesCount * 1000f) / elapsed

            notifyEvent("TELEMETRY", mapOf(
                "rearFps" to rearFps,
                "frontFps" to frontFps,
            ))

            rearFramesCount = 0
            frontFramesCount = 0
            lastStatsUpdate = now
        }
    }

    private fun notifyEvent(state: String, data: Map<String, Any>) {
        val payload = HashMap(data)
        payload["state"] = state
        eventCallback?.invoke(state, payload)
    }

    private fun stopStream() {
        isServiceRunning = false
        isStreaming.set(false)
        discoveryThread?.interrupt()
        discoveryThread = null

        cameraManager.stopStreaming()
        try {
            webSocket?.close(1000, "User stopped stream")
        } catch (e: Exception) {
            Log.e(TAG, "Error closing websocket", e)
        }
        webSocket = null
        notifyEvent("STOPPED", mapOf("status" to "Broadcast stopped"))
    }

    override fun onDestroy() {
        stopStream()
        releaseLocks()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null
}
