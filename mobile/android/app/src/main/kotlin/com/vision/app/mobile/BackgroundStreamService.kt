package com.vision.app.mobile

import android.app.*
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.content.pm.ServiceInfo
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.net.wifi.WifiManager
import android.os.*
import android.util.Log
import androidx.core.app.NotificationCompat
import okhttp3.*
import okio.ByteString.Companion.toByteString
import org.json.JSONObject
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Energy-efficient and resilient Foreground Service that persists camera capture
 * and WebSocket streaming 24/7 in the background.
 *
 * Designed for minimum energy consumption and maximum opportunistic connectivity:
 * - Sensors (Camera & Microphone) are completely powered down when disconnected.
 * - High-performance Wi-Fi lock is only held during active streaming; released during standby.
 * - Adaptive Auto-Discovery: fast burst on network events, low-power sleep when server is offline.
 * - Listens to Android NetworkCallbacks for instant reconnection whenever Wi-Fi associates.
 * - Remembers last known server coordinates for <50ms instant reconnection.
 * - Survives device reboots (BootReceiver) and task swiping (onTaskRemoved + AlarmManager).
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

        const val PREFS_NAME = "VisionCamPrefs"
        const val KEY_LAST_SERVER_IP = "last_server_ip"
        const val KEY_LAST_SERVER_PORT = "last_server_port"
        const val KEY_LAST_AUTO_DISCOVER = "last_auto_discover"
        const val KEY_LAST_CAMERA_MODE = "last_camera_mode"

        // Wire protocol prefix byte codes
        const val CODE_REAR_FRAME: Byte = 0x00
        const val CODE_FRONT_FRAME: Byte = 0x01
        const val CODE_AUDIO_CHUNK: Byte = 0x02

        var isServiceRunning = false
            private set

        var eventCallback: ((String, Map<String, Any>) -> Unit)? = null

        fun isEmulator(): Boolean {
            return (Build.BRAND.startsWith("generic") && Build.DEVICE.startsWith("generic"))
                    || Build.FINGERPRINT.startsWith("generic")
                    || Build.HARDWARE.contains("goldfish")
                    || Build.HARDWARE.contains("ranchu")
                    || Build.MODEL.contains("google_sdk")
                    || Build.MODEL.contains("Emulator")
                    || Build.MODEL.contains("Android SDK built for x86")
        }
    }

    private lateinit var cameraManager: DualCameraManager
    private lateinit var audioManager: AudioStreamManager
    private var wakeLock: PowerManager.WakeLock? = null
    private var wifiLock: WifiManager.WifiLock? = null
    private var multicastLock: WifiManager.MulticastLock? = null

    private var okHttpClient: OkHttpClient? = null
    private var webSocket: WebSocket? = null

    private var targetServerIp: String? = null
    private var targetServerPort: Int = 8765
    private var autoDiscover: Boolean = true
    private var cameraMode: String = "rear"

    private val isStreaming = AtomicBoolean(false)
    private var discoveryThread: Thread? = null

    // Adaptive Discovery synchronization
    private val discoveryLock = java.lang.Object()
    private var discoveryBurstCount = 8

    // Network Connectivity monitoring
    private var connectivityManager: ConnectivityManager? = null
    private var networkCallback: ConnectivityManager.NetworkCallback? = null

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
        audioManager = AudioStreamManager(this)
        createNotificationChannel()
        acquireStandbyLocks()
        initHttpClient()
        registerNetworkObserver()
    }

    private fun initHttpClient() {
        okHttpClient = OkHttpClient.Builder()
            .readTimeout(10, TimeUnit.SECONDS)
            .writeTimeout(10, TimeUnit.SECONDS)
            .pingInterval(3, TimeUnit.SECONDS)
            .retryOnConnectionFailure(true)
            .build()
    }

    private fun acquireStandbyLocks() {
        try {
            val powerManager = getSystemService(Context.POWER_SERVICE) as PowerManager
            wakeLock = powerManager.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "VisionCam::WakeLock").apply {
                acquire(24 * 60 * 60 * 1000L)
            }

            // Android requires MulticastLock to receive UDP discovery broadcasts
            val wifiManager = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
            multicastLock = wifiManager.createMulticastLock("VisionCam::MulticastLock").apply {
                setReferenceCounted(true)
                acquire()
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed acquiring WakeLock or MulticastLock: ${e.message}")
        }
    }

    private fun acquireStreamingWifiLock() {
        try {
            if (wifiLock == null || wifiLock?.isHeld != true) {
                val wifiManager = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
                @Suppress("DEPRECATION")
                wifiLock = wifiManager.createWifiLock(WifiManager.WIFI_MODE_FULL_HIGH_PERF, "VisionCam::StreamingWifiLock").apply {
                    setReferenceCounted(false)
                    acquire()
                }
                Log.d(TAG, "Acquired High-Performance WifiLock for active streaming.")
            }
        } catch (e: Exception) {
            Log.w(TAG, "Failed to acquire High-Perf WifiLock: ${e.message}")
        }
    }

    private fun releaseStreamingWifiLock() {
        try {
            if (wifiLock?.isHeld == true) {
                wifiLock?.release()
                Log.d(TAG, "Released High-Performance WifiLock to save standby battery.")
            }
        } catch (e: Exception) {
            Log.w(TAG, "Error releasing WifiLock: ${e.message}")
        }
    }

    private fun releaseLocks() {
        try {
            releaseStreamingWifiLock()
            if (wakeLock?.isHeld == true) wakeLock?.release()
            if (multicastLock?.isHeld == true) multicastLock?.release()
        } catch (e: Exception) {
            Log.e(TAG, "Error releasing locks: ${e.message}")
        }
    }

    private fun registerNetworkObserver() {
        try {
            connectivityManager = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
            val request = NetworkRequest.Builder()
                .addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
                .addTransportType(NetworkCapabilities.TRANSPORT_WIFI)
                .build()

            networkCallback = object : ConnectivityManager.NetworkCallback() {
                override fun onAvailable(network: Network) {
                    Log.i(TAG, "Wi-Fi network detected! Triggering opportunistic reconnection...")
                    if (isServiceRunning && !isStreaming.get()) {
                        triggerOpportunisticReconnect()
                    }
                }

                override fun onLost(network: Network) {
                    Log.w(TAG, "Wi-Fi network connection lost.")
                }
            }
            connectivityManager?.registerNetworkCallback(request, networkCallback!!)
        } catch (e: Exception) {
            Log.w(TAG, "Could not register NetworkCallback: ${e.message}")
        }
    }

    private fun unregisterNetworkObserver() {
        try {
            networkCallback?.let { connectivityManager?.unregisterNetworkCallback(it) }
        } catch (_: Exception) {}
        networkCallback = null
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> {
                targetServerIp = intent.getStringExtra(EXTRA_SERVER_IP)?.trim()
                targetServerPort = intent.getIntExtra(EXTRA_SERVER_PORT, 8765)
                autoDiscover = intent.getBooleanExtra(EXTRA_AUTO_DISCOVER, true)
                cameraMode = intent.getStringExtra(EXTRA_CAMERA_MODE) ?: "rear"

                // Save parameters for boot and auto-reconnect resilience
                savePreferences(targetServerIp ?: "", targetServerPort, autoDiscover, cameraMode)

                startForegroundNotification()
                isServiceRunning = true

                // Priority 1: User explicitly provided an IP
                if (!targetServerIp.isNullOrEmpty() && targetServerIp != "0.0.0.0") {
                    Log.d(TAG, "Connecting to user specified Server IP: $targetServerIp:$targetServerPort")
                    connectWebSocket(targetServerIp!!, targetServerPort)
                } else if (isEmulator()) {
                    Log.d(TAG, "Connecting directly to emulator host at 10.0.2.2:$targetServerPort")
                    connectWebSocket("10.0.2.2", targetServerPort)
                } else {
                    // Priority 2: Opportunistic fast connect to last known IP in cache
                    val cachedIp = loadSavedServerIp()
                    if (!cachedIp.isNullOrEmpty()) {
                        Log.d(TAG, "Attempting opportunistic instant connect to cached Server IP: $cachedIp:$targetServerPort")
                        connectWebSocket(cachedIp, targetServerPort)
                    }

                    // Priority 3: Start adaptive auto-discovery if needed
                    if (autoDiscover) {
                        startAdaptiveAutoDiscovery()
                    } else if (cachedIp.isNullOrEmpty()) {
                        notifyEvent("ERROR", mapOf("error" to "No Server IP specified"))
                    }
                }
            }
            ACTION_STOP -> {
                stopStream()
                stopSelf()
            }
        }
        return START_STICKY
    }

    private fun triggerOpportunisticReconnect() {
        val cachedIp = if (!targetServerIp.isNullOrEmpty() && targetServerIp != "0.0.0.0") targetServerIp else loadSavedServerIp()
        if (!cachedIp.isNullOrEmpty()) {
            connectWebSocket(cachedIp, targetServerPort)
        }
        wakeDiscoveryBurst()
    }

    private fun wakeDiscoveryBurst() {
        synchronized(discoveryLock) {
            discoveryBurstCount = 8
            discoveryLock.notifyAll()
        }
    }

    private fun savePreferences(ip: String, port: Int, auto: Boolean, mode: String) {
        try {
            val prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            prefs.edit().apply {
                if (ip.isNotEmpty() && ip != "0.0.0.0") {
                    putString(KEY_LAST_SERVER_IP, ip)
                }
                putInt(KEY_LAST_SERVER_PORT, port)
                putBoolean(KEY_LAST_AUTO_DISCOVER, auto)
                putString(KEY_LAST_CAMERA_MODE, mode)
                apply()
            }
        } catch (_: Exception) {}
    }

    private fun loadSavedServerIp(): String? {
        val prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val ip = prefs.getString(KEY_LAST_SERVER_IP, "") ?: ""
        return if (ip.isNotEmpty() && ip != "0.0.0.0") ip else null
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
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
                serviceType = serviceType or ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE
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

    /**
     * Adaptive auto-discovery:
     * - Runs 8 fast discovery pulses (1.5s interval) on startup / network change.
     * - Drops to 12s standby interval when server is offline to conserve maximum battery.
     * - Wakes up instantly on network connectivity changes via wakeDiscoveryBurst().
     */
    private fun startAdaptiveAutoDiscovery() {
        if (discoveryThread?.isAlive == true) {
            wakeDiscoveryBurst()
            return
        }

        notifyEvent("DISCOVERING", mapOf("status" to "Searching Wi-Fi for Desktop Server..."))

        discoveryThread = Thread {
            var socket: DatagramSocket? = null
            try {
                socket = DatagramSocket().apply {
                    broadcast = true
                    soTimeout = 2000
                }

                val probeMsg = "VISION_DISCOVER_PROBE".toByteArray()
                val broadcastAddresses = mutableListOf(
                    InetAddress.getByName("255.255.255.255")
                )

                if (isEmulator()) {
                    broadcastAddresses.add(InetAddress.getByName("10.0.2.2"))
                }

                val buffer = ByteArray(1024)
                val responsePacket = DatagramPacket(buffer, buffer.size)

                while (isServiceRunning && !isStreaming.get()) {
                    try {
                        for (addr in broadcastAddresses) {
                            val probePacket = DatagramPacket(probeMsg, probeMsg.size, addr, 45454)
                            socket.send(probePacket)
                        }

                        socket.receive(responsePacket)
                        val respJson = String(responsePacket.data, 0, responsePacket.length)
                        val json = JSONObject(respJson)

                        if (json.optString("type") == "VISION_SERVER_ANNOUNCE") {
                            var ip = json.optString("ip", responsePacket.address.hostAddress ?: "")
                            val port = json.optInt("port", 8765)

                            if (isEmulator() && (ip == "127.0.0.1" || ip.startsWith("192.168."))) {
                                ip = "10.0.2.2"
                            }

                            Log.i(TAG, "Discovered Vision Server at $ip:$port! Connecting...")
                            savePreferences(ip, port, autoDiscover, cameraMode)
                            connectWebSocket(ip, port)
                            break
                        }
                    } catch (_: Exception) {
                        // Timeout on packet receive is normal during scanning
                    }

                    // Adaptive sleep: burst vs low-power standby
                    val sleepDuration = synchronized(discoveryLock) {
                        if (discoveryBurstCount > 0) {
                            discoveryBurstCount--
                            1500L
                        } else {
                            12000L // Deep standby: sleep 12s so radio and CPU can enter low-power C-states
                        }
                    }

                    try {
                        synchronized(discoveryLock) {
                            discoveryLock.wait(sleepDuration)
                        }
                    } catch (_: InterruptedException) {
                        break
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "Discovery socket error: ${e.message}")
            } finally {
                socket?.close()
            }
        }.apply {
            isDaemon = true
            start()
        }
    }

    private fun connectWebSocket(ip: String, port: Int) {
        if (isStreaming.get()) return

        val model = "${Build.MANUFACTURER} ${Build.MODEL}"
        val url = "ws://$ip:$port/ws/phone?device=${java.net.URLEncoder.encode(model, "UTF-8")}"

        notifyEvent("CONNECTING", mapOf("serverIp" to ip, "port" to port, "status" to "Connecting to $ip:$port..."))
        Log.d(TAG, "Attempting WebSocket connection to: $url")

        val request = Request.Builder().url(url).build()
        webSocket = okHttpClient?.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.i(TAG, "WebSocket connected successfully to $ip:$port!")
                isStreaming.set(true)
                savePreferences(ip, port, autoDiscover, cameraMode)
                acquireStreamingWifiLock()

                notifyEvent("STREAMING", mapOf("serverIp" to ip, "status" to "Connected"))

                // Start hardware camera capture only after socket is open
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

                            sendCameraStatusToServer()

                            notifyEvent("CAMERA_STATUS", mapOf(
                                "rearActive" to isRearActive,
                                "rearMessage" to rearMessage,
                                "frontActive" to isFrontActive,
                                "frontMessage" to frontMessage,
                            ))
                        }
                    }
                )

                // Start microphone streaming with zero-overhead PCM (16kHz Mono)
                audioManager.startStreaming(object : AudioStreamManager.AudioChunkListener {
                    override fun onAudioDataAvailable(pcmBytes: ByteArray) {
                        if (!isStreaming.get() || !audioManager.isAudioEnabled()) return
                        val packet = ByteArray(1 + pcmBytes.size)
                        packet[0] = CODE_AUDIO_CHUNK
                        System.arraycopy(pcmBytes, 0, packet, 1, pcmBytes.size)
                        webSocket.send(packet.toByteString(0, packet.size))
                    }
                })

                // Announce device capabilities, flash status, quality, fps, and audio state to server
                sendDeviceInfoToServer()
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                try {
                    val json = JSONObject(text)
                    if (json.optString("type") == "CONTROL") {
                        when (json.optString("action")) {
                            "set_flash" -> {
                                val enable = json.optBoolean("enabled", false)
                                val success = cameraManager.setTorch(enable)
                                sendDeviceStateToServer()
                                notifyEvent("FLASH_STATUS", mapOf("flashEnabled" to cameraManager.isFlashOn, "success" to success))
                            }
                            "set_quality" -> {
                                val quality = json.optInt("quality", 75)
                                val success = cameraManager.setJpegQuality(quality)
                                sendDeviceStateToServer()
                                notifyEvent("QUALITY_STATUS", mapOf("quality" to cameraManager.currentJpegQuality, "success" to success))
                            }
                            "set_fps" -> {
                                val fps = json.optInt("fps", 30)
                                cameraManager.setTargetFps(fps)
                                sendDeviceStateToServer()
                                notifyEvent("FPS_STATUS", mapOf("fps" to cameraManager.targetFps))
                            }
                            "set_audio" -> {
                                val enable = json.optBoolean("enabled", true)
                                audioManager.setEnabled(enable)
                                sendDeviceStateToServer()
                                notifyEvent("AUDIO_STATUS", mapOf("audioEnabled" to audioManager.isAudioEnabled()))
                            }
                            "sync_state" -> {
                                sendDeviceInfoToServer()
                            }
                        }
                    }
                } catch (e: Exception) {
                    Log.w(TAG, "Error handling server control message: ${e.message}")
                }
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                val errorMsg = t.localizedMessage ?: t.message ?: "Connection failed"
                Log.w(TAG, "WebSocket connection failed to $ip:$port: $errorMsg")
                isStreaming.set(false)

                // Shut down sensors and release high-perf lock to save battery
                cameraManager.stopStreaming()
                audioManager.stopStreaming()
                releaseStreamingWifiLock()

                notifyEvent("DISCONNECTED", mapOf(
                    "error" to errorMsg,
                    "serverIp" to ip,
                    "port" to port,
                    "reason" to "Cannot reach $ip:$port ($errorMsg)"
                ))

                // Opportunistic reconnect retry
                if (isServiceRunning) {
                    try {
                        Thread.sleep(3000)
                    } catch (_: InterruptedException) {}
                    if (isServiceRunning) {
                        if (autoDiscover) {
                            startAdaptiveAutoDiscovery()
                        } else {
                            connectWebSocket(ip, port)
                        }
                    }
                }
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                Log.d(TAG, "WebSocket closed ($code): $reason")
                isStreaming.set(false)
                cameraManager.stopStreaming()
                audioManager.stopStreaming()
                releaseStreamingWifiLock()
                notifyEvent("DISCONNECTED", mapOf("reason" to reason))

                if (isServiceRunning && autoDiscover) {
                    startAdaptiveAutoDiscovery()
                }
            }
        })
    }

    private fun sendDeviceInfoToServer() {
        try {
            val bm = getSystemService(Context.BATTERY_SERVICE) as? BatteryManager
            val batteryLevel = bm?.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY) ?: -1
            val json = JSONObject().apply {
                put("type", "DEVICE_INFO")
                put("device_model", "${Build.MANUFACTURER} ${Build.MODEL}")
                put("battery", if (batteryLevel >= 0) "$batteryLevel%" else "N/A")
                put("flash_supported", cameraManager.isFlashAvailable)
                put("flash_enabled", cameraManager.isFlashOn)
                put("quality", cameraManager.currentJpegQuality)
                put("fps", cameraManager.targetFps)
                put("audio_enabled", audioManager.isAudioEnabled())
            }
            webSocket?.send(json.toString())
        } catch (e: Exception) {
            Log.w(TAG, "Failed to send device info to server: ${e.message}")
        }
    }

    private fun sendDeviceStateToServer() {
        try {
            val json = JSONObject().apply {
                put("type", "STATE_UPDATE")
                put("flash_enabled", cameraManager.isFlashOn)
                put("quality", cameraManager.currentJpegQuality)
                put("fps", cameraManager.targetFps)
                put("audio_enabled", audioManager.isAudioEnabled())
            }
            webSocket?.send(json.toString())
        } catch (e: Exception) {
            Log.w(TAG, "Failed to send device state to server: ${e.message}")
        }
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
        audioManager.stopStreaming()
        releaseStreamingWifiLock()

        try {
            webSocket?.close(1000, "User stopped stream")
        } catch (e: Exception) {
            Log.e(TAG, "Error closing websocket: ${e.message}")
        }
        webSocket = null
        notifyEvent("STOPPED", mapOf("status" to "Broadcast stopped"))
    }

    /**
     * Self-healing resurrection: If the app task is removed from the recent apps screen,
     * schedule an immediate restart via AlarmManager to ensure 24/7 background persistence.
     */
    override fun onTaskRemoved(rootIntent: Intent?) {
        super.onTaskRemoved(rootIntent)
        Log.i(TAG, "Task removed from Recents. Triggering persistent resurrection...")
        if (isServiceRunning) {
            try {
                val restartIntent = Intent(applicationContext, BackgroundStreamService::class.java).apply {
                    action = ACTION_START
                    putExtra(EXTRA_SERVER_IP, targetServerIp ?: "")
                    putExtra(EXTRA_SERVER_PORT, targetServerPort)
                    putExtra(EXTRA_AUTO_DISCOVER, autoDiscover)
                    putExtra(EXTRA_CAMERA_MODE, cameraMode)
                }
                val pendingIntent = PendingIntent.getService(
                    applicationContext,
                    101,
                    restartIntent,
                    PendingIntent.FLAG_ONE_SHOT or PendingIntent.FLAG_IMMUTABLE
                )
                val alarmManager = getSystemService(Context.ALARM_SERVICE) as AlarmManager
                alarmManager.set(
                    AlarmManager.ELAPSED_REALTIME_WAKEUP,
                    SystemClock.elapsedRealtime() + 1000,
                    pendingIntent
                )
            } catch (e: Exception) {
                Log.e(TAG, "Failed scheduling service resurrection: ${e.message}")
            }
        }
    }

    override fun onDestroy() {
        stopStream()
        releaseLocks()
        unregisterNetworkObserver()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null
}
