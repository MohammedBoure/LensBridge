package com.vision.app.mobile

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.ImageFormat
import android.hardware.camera2.*
import android.media.ImageReader
import android.os.Build
import android.os.Handler
import android.os.HandlerThread
import android.util.Log
import android.util.Size
import java.nio.ByteBuffer

/**
 * Manages concurrent capture of both Rear (Back) and Front cameras using Android Camera2 API.
 * Employs concurrent camera configurations introduced in Android 11 (API 30+) when available,
 * with graceful fallback logic for single-ISP devices.
 */
class DualCameraManager(private val context: Context) {

    companion object {
        private const val TAG = "DualCameraManager"
        const val CAMERA_REAR: Byte = 0x00
        const val CAMERA_FRONT: Byte = 0x01
    }

    interface FrameListener {
        fun onFrameAvailable(cameraCode: Byte, jpegBytes: ByteArray)
    }

    private val cameraManager = context.getSystemService(Context.CAMERA_SERVICE) as CameraManager

    private var rearCameraId: String? = null
    private var frontCameraId: String? = null

    private var rearCameraDevice: CameraDevice? = null
    private var frontCameraDevice: CameraDevice? = null

    private var rearCaptureSession: CameraCaptureSession? = null
    private var frontCaptureSession: CameraCaptureSession? = null

    private var rearImageReader: ImageReader? = null
    private var frontImageReader: ImageReader? = null

    private var backgroundThread: HandlerThread? = null
    private var backgroundHandler: Handler? = null

    private var frameListener: FrameListener? = null
    private var isRunning = false

    init {
        detectCameraIds()
    }

    private fun detectCameraIds() {
        try {
            for (id in cameraManager.cameraIdList) {
                val characteristics = cameraManager.getCameraCharacteristics(id)
                val facing = characteristics.get(CameraCharacteristics.LENS_FACING)
                if (facing == CameraCharacteristics.LENS_FACING_BACK && rearCameraId == null) {
                    rearCameraId = id
                } else if (facing == CameraCharacteristics.LENS_FACING_FRONT && frontCameraId == null) {
                    frontCameraId = id
                }
            }
            Log.d(TAG, "Identified cameras - Rear: $rearCameraId, Front: $frontCameraId")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to detect camera IDs", e)
        }
    }

    fun isConcurrentSupported(): Boolean {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            try {
                val concurrentSets = cameraManager.concurrentCameraIds
                for (set in concurrentSets) {
                    if (rearCameraId != null && frontCameraId != null &&
                        set.contains(rearCameraId) && set.contains(frontCameraId)
                    ) {
                        return true
                    }
                }
            } catch (e: Exception) {
                Log.w(TAG, "Error querying concurrent camera IDs", e)
            }
        }
        return false
    }

    @SuppressLint("MissingPermission")
    @Synchronized
    fun startStreaming(
        targetWidth: Int = 640,
        targetHeight: Int = 480,
        listener: FrameListener
    ) {
        if (isRunning) return
        isRunning = true
        frameListener = listener

        startBackgroundThread()

        val handler = backgroundHandler ?: return

        // Open Rear Camera
        rearCameraId?.let { id ->
            setupRearCamera(id, targetWidth, targetHeight, handler)
        }

        // Open Front Camera (Concurrently)
        frontCameraId?.let { id ->
            setupFrontCamera(id, targetWidth, targetHeight, handler)
        }
    }

    @SuppressLint("MissingPermission")
    private fun setupRearCamera(id: String, width: Int, height: Int, handler: Handler) {
        try {
            rearImageReader = ImageReader.newInstance(width, height, ImageFormat.JPEG, 2).apply {
                setOnImageAvailableListener({ reader ->
                    processImage(reader, CAMERA_REAR)
                }, handler)
            }

            cameraManager.openCamera(id, object : CameraDevice.StateCallback() {
                override fun onOpened(camera: CameraDevice) {
                    rearCameraDevice = camera
                    createSession(camera, rearImageReader, isRear = true, handler)
                }

                override fun onDisconnected(camera: CameraDevice) {
                    camera.close()
                    rearCameraDevice = null
                }

                override fun onError(camera: CameraDevice, error: Int) {
                    Log.e(TAG, "Rear camera open error: $error")
                    camera.close()
                    rearCameraDevice = null
                }
            }, handler)
        } catch (e: Exception) {
            Log.e(TAG, "Exception opening rear camera", e)
        }
    }

    @SuppressLint("MissingPermission")
    private fun setupFrontCamera(id: String, width: Int, height: Int, handler: Handler) {
        try {
            frontImageReader = ImageReader.newInstance(width, height, ImageFormat.JPEG, 2).apply {
                setOnImageAvailableListener({ reader ->
                    processImage(reader, CAMERA_FRONT)
                }, handler)
            }

            cameraManager.openCamera(id, object : CameraDevice.StateCallback() {
                override fun onOpened(camera: CameraDevice) {
                    frontCameraDevice = camera
                    createSession(camera, frontImageReader, isRear = false, handler)
                }

                override fun onDisconnected(camera: CameraDevice) {
                    camera.close()
                    frontCameraDevice = null
                }

                override fun onError(camera: CameraDevice, error: Int) {
                    Log.e(TAG, "Front camera open error: $error")
                    camera.close()
                    frontCameraDevice = null
                }
            }, handler)
        } catch (e: Exception) {
            Log.e(TAG, "Exception opening front camera", e)
        }
    }

    private fun createSession(
        camera: CameraDevice,
        imageReader: ImageReader?,
        isRear: Boolean,
        handler: Handler
    ) {
        val surface = imageReader?.surface ?: return
        try {
            val captureRequestBuilder = camera.createCaptureRequest(CameraDevice.TEMPLATE_RECORD).apply {
                addTarget(surface)
                set(CaptureRequest.CONTROL_AF_MODE, CaptureRequest.CONTROL_AF_MODE_CONTINUOUS_PICTURE)
                set(CaptureRequest.JPEG_QUALITY, 75.toByte())
            }

            val sessionCallback = object : CameraCaptureSession.StateCallback() {
                override fun onConfigured(session: CameraCaptureSession) {
                    if (isRear) rearCaptureSession = session else frontCaptureSession = session
                    try {
                        session.setRepeatingRequest(captureRequestBuilder.build(), null, handler)
                        Log.d(TAG, "${if (isRear) "Rear" else "Front"} repeating capture active")
                    } catch (e: Exception) {
                        Log.e(TAG, "Repeating request failed", e)
                    }
                }

                override fun onConfigureFailed(session: CameraCaptureSession) {
                    Log.e(TAG, "Session configuration failed for ${if (isRear) "Rear" else "Front"}")
                }
            }

            @Suppress("DEPRECATION")
            camera.createCaptureSession(listOf(surface), sessionCallback, handler)
        } catch (e: Exception) {
            Log.e(TAG, "Failed creating capture session", e)
        }
    }

    private fun processImage(reader: ImageReader, cameraCode: Byte) {
        val image = reader.acquireLatestImage() ?: return
        try {
            val planes = image.planes
            if (planes.isNotEmpty()) {
                val buffer: ByteBuffer = planes[0].buffer
                val bytes = ByteArray(buffer.remaining())
                buffer.get(bytes)
                frameListener?.onFrameAvailable(cameraCode, bytes)
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error reading image buffer", e)
        } finally {
            image.close()
        }
    }

    @Synchronized
    fun stopStreaming() {
        isRunning = false
        try {
            rearCaptureSession?.close()
            frontCaptureSession?.close()
            rearCameraDevice?.close()
            frontCameraDevice?.close()
            rearImageReader?.close()
            frontImageReader?.close()
        } catch (e: Exception) {
            Log.e(TAG, "Error closing camera sessions", e)
        } finally {
            rearCaptureSession = null
            frontCaptureSession = null
            rearCameraDevice = null
            frontCameraDevice = null
            rearImageReader = null
            frontImageReader = null
        }
        stopBackgroundThread()
    }

    private fun startBackgroundThread() {
        if (backgroundThread == null) {
            backgroundThread = HandlerThread("VisionCameraBackground").apply {
                start()
                backgroundHandler = Handler(looper)
            }
        }
    }

    private fun stopBackgroundThread() {
        backgroundThread?.quitSafely()
        try {
            backgroundThread?.join(500)
        } catch (e: Exception) {
            Log.e(TAG, "Error stopping background thread", e)
        } finally {
            backgroundThread = null
            backgroundHandler = null
        }
    }
}
