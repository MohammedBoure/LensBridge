package com.vision.app.mobile

import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Process
import android.util.Log
import androidx.core.content.ContextCompat
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Energy-efficient and fault-tolerant audio capture manager.
 * Captures microphone audio as 16-bit Mono PCM at 16,000 Hz.
 * Uses zero software compression overhead, ensuring negligible CPU usage,
 * minimal battery consumption, and rock-solid stability during long 24/7 background sessions.
 */
class AudioStreamManager(private val context: Context) {

    companion object {
        private const val TAG = "AudioStreamManager"
        const val SAMPLE_RATE = 16000
        const val CHANNEL_CONFIG = AudioFormat.CHANNEL_IN_MONO
        const val AUDIO_FORMAT = AudioFormat.ENCODING_PCM_16BIT
    }

    interface AudioChunkListener {
        fun onAudioDataAvailable(pcmBytes: ByteArray)
    }

    private val isRecording = AtomicBoolean(false)
    private var isEnabled = true
    private var recordingThread: Thread? = null
    private var audioRecord: AudioRecord? = null
    private var chunkListener: AudioChunkListener? = null

    val isCapturing: Boolean
        get() = isRecording.get() && isEnabled

    fun setEnabled(enabled: Boolean) {
        isEnabled = enabled
        if (!enabled && isRecording.get()) {
            pauseRecording()
        } else if (enabled && !isRecording.get() && chunkListener != null) {
            resumeRecording()
        }
    }

    fun isAudioEnabled(): Boolean = isEnabled

    @SuppressLint("MissingPermission")
    @Synchronized
    fun startStreaming(listener: AudioChunkListener) {
        chunkListener = listener
        if (!isEnabled) {
            Log.d(TAG, "Audio is currently muted/disabled by settings.")
            return
        }

        if (isRecording.get()) return

        if (ContextCompat.checkSelfPermission(context, android.Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED
        ) {
            Log.w(TAG, "RECORD_AUDIO permission not granted. Audio capture disabled.")
            return
        }

        try {
            val minBufferSize = AudioRecord.getMinBufferSize(SAMPLE_RATE, CHANNEL_CONFIG, AUDIO_FORMAT)
            if (minBufferSize == AudioRecord.ERROR || minBufferSize == AudioRecord.ERROR_BAD_VALUE) {
                Log.e(TAG, "Invalid audio recording parameters")
                return
            }

            // Buffer roughly 64ms - 100ms of audio (1024 or 2048 samples = 2048 or 4096 bytes)
            val bufferSize = maxOf(minBufferSize, 2048)
            audioRecord = AudioRecord(
                MediaRecorder.AudioSource.MIC,
                SAMPLE_RATE,
                CHANNEL_CONFIG,
                AUDIO_FORMAT,
                bufferSize * 2
            )

            if (audioRecord?.state != AudioRecord.STATE_INITIALIZED) {
                Log.e(TAG, "AudioRecord failed to initialize")
                audioRecord?.release()
                audioRecord = null
                return
            }

            audioRecord?.startRecording()
            isRecording.set(true)

            recordingThread = Thread({
                Process.setThreadPriority(Process.THREAD_PRIORITY_AUDIO)
                val readBuffer = ByteArray(2048) // 1024 samples (64ms of audio at 16kHz)

                while (isRecording.get()) {
                    val record = audioRecord ?: break
                    val bytesRead = record.read(readBuffer, 0, readBuffer.size)
                    if (bytesRead > 0 && isEnabled) {
                        val packet = ByteArray(bytesRead)
                        System.arraycopy(readBuffer, 0, packet, 0, bytesRead)
                        chunkListener?.onAudioDataAvailable(packet)
                    } else if (bytesRead < 0) {
                        Log.w(TAG, "AudioRecord read error code: $bytesRead")
                        try {
                            Thread.sleep(100)
                        } catch (_: InterruptedException) {
                            break
                        }
                    }
                }
            }, "VisionAudioRecorderThread").apply {
                isDaemon = true
                start()
            }

            Log.d(TAG, "Audio recording started successfully at ${SAMPLE_RATE}Hz Mono")
        } catch (e: Exception) {
            Log.e(TAG, "Failed starting AudioRecord: ${e.message}", e)
            stopStreaming()
        }
    }

    private fun pauseRecording() {
        try {
            audioRecord?.stop()
        } catch (e: Exception) {
            Log.w(TAG, "Error pausing audio record: ${e.message}")
        }
    }

    private fun resumeRecording() {
        try {
            audioRecord?.startRecording()
        } catch (e: Exception) {
            Log.w(TAG, "Error resuming audio record: ${e.message}")
        }
    }

    @Synchronized
    fun stopStreaming() {
        isRecording.set(false)
        recordingThread?.interrupt()
        recordingThread = null

        try {
            audioRecord?.stop()
        } catch (_: Exception) {}
        try {
            audioRecord?.release()
        } catch (_: Exception) {}
        audioRecord = null
        chunkListener = null
        Log.d(TAG, "Audio streaming stopped.")
    }
}
