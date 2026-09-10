"""Stream Hub for Vision Desktop Server.

Acts as a high-performance proxy broker for:
1. Video: Converts back-camera JPEG stream to HTTP MJPEG, raw WebSocket proxy, and snapshots.
2. Audio: Captures microphone PCM audio (16kHz Mono 16-bit) and provides HTTP audio stream & WebSocket.
3. Hardware Controls: Manages camera flashlight (torch), JPEG quality, target FPS, and audio state
   with two-way real-time WebSocket communication to the mobile phone and REST APIs for internal programs.
"""

import asyncio
import collections
import json
import struct
import time
from typing import Dict, Optional, Set
from fastapi import WebSocket

from config import (
    DEFAULT_FLASH_ENABLED,
    DEFAULT_JPEG_QUALITY,
    DEFAULT_FPS_TARGET,
    DEFAULT_AUDIO_ENABLED,
    AUDIO_SAMPLE_RATE,
    AUDIO_CHANNELS,
    AUDIO_BIT_DEPTH,
)


class StreamStats:
    """Tracks framerate, bitrate, and frame count for the back camera stream."""

    def __init__(self):
        self.frame_count = 0
        self.total_bytes = 0
        self.current_fps = 0.0
        self.bitrate_kbps = 0.0
        self.last_frame_time = 0.0
        self._timestamps = collections.deque(maxlen=30)
        self._bytes_history = collections.deque(maxlen=30)

    def record_frame(self, frame_size: int):
        now = time.time()
        self.frame_count += 1
        self.total_bytes += frame_size
        self.last_frame_time = now

        self._timestamps.append(now)
        self._bytes_history.append(frame_size)

        if len(self._timestamps) > 1:
            duration = self._timestamps[-1] - self._timestamps[0]
            if duration > 0:
                self.current_fps = round((len(self._timestamps) - 1) / duration, 1)
                window_bytes = sum(self._bytes_history)
                self.bitrate_kbps = round((window_bytes * 8) / (duration * 1000), 1)

    def to_dict(self) -> dict:
        is_active = (time.time() - self.last_frame_time) < 3.0 if self.last_frame_time > 0 else False
        return {
            "active": is_active,
            "fps": self.current_fps if is_active else 0.0,
            "bitrate_kbps": self.bitrate_kbps if is_active else 0.0,
            "total_frames": self.frame_count,
            "last_seen": round(self.last_frame_time, 2),
        }


class AudioStats:
    """Tracks microphone audio metrics (packets, bytes, bitrate, activity)."""

    def __init__(self):
        self.packet_count = 0
        self.total_bytes = 0
        self.current_kbps = 0.0
        self.last_audio_time = 0.0
        self._timestamps = collections.deque(maxlen=40)
        self._bytes_history = collections.deque(maxlen=40)

    def record_chunk(self, chunk_size: int):
        now = time.time()
        self.packet_count += 1
        self.total_bytes += chunk_size
        self.last_audio_time = now

        self._timestamps.append(now)
        self._bytes_history.append(chunk_size)

        if len(self._timestamps) > 1:
            duration = self._timestamps[-1] - self._timestamps[0]
            if duration > 0:
                window_bytes = sum(self._bytes_history)
                self.current_kbps = round((window_bytes * 8) / (duration * 1000), 1)

    def to_dict(self) -> dict:
        is_active = (time.time() - self.last_audio_time) < 3.0 if self.last_audio_time > 0 else False
        return {
            "active": is_active,
            "sample_rate": AUDIO_SAMPLE_RATE,
            "channels": AUDIO_CHANNELS,
            "bit_depth": AUDIO_BIT_DEPTH,
            "bitrate_kbps": self.current_kbps if is_active else 0.0,
            "total_packets": self.packet_count,
            "total_bytes": self.total_bytes,
            "last_seen": round(self.last_audio_time, 2),
        }


class StreamHub:
    """Central proxy broker coordinating mobile camera stream, audio, controls, and external programs."""

    def __init__(self):
        self.phone_socket: Optional[WebSocket] = None
        self.proxy_clients: Set[WebSocket] = set()
        self.audio_proxy_clients: Set[WebSocket] = set()
        self.latest_frame: bytes = b""
        self.stats = StreamStats()
        self.audio_stats = AudioStats()

        # Remote Hardware State
        self.flash_enabled: bool = DEFAULT_FLASH_ENABLED
        self.jpeg_quality: int = DEFAULT_JPEG_QUALITY
        self.target_fps: int = DEFAULT_FPS_TARGET
        self.audio_enabled: bool = DEFAULT_AUDIO_ENABLED

        # Active queue subscribers for HTTP streaming
        self._mjpeg_subscribers: Set[asyncio.Queue] = set()
        self._audio_subscribers: Set[asyncio.Queue] = set()

        self.phone_info: Dict[str, str] = {
            "device_model": "None",
            "connected_at": "",
            "ip": "",
            "battery": "N/A",
            "flash_supported": "Unknown",
        }

    async def register_phone(self, websocket: WebSocket, client_ip: str, device_model: str = "Mobile"):
        """Registers the mobile phone as the active streaming source and synchronizes settings."""
        self.phone_socket = websocket
        self.phone_info = {
            "device_model": device_model,
            "connected_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "ip": client_ip,
            "battery": "N/A",
            "flash_supported": "Unknown",
        }
        print(f"[StreamHub] Phone connected from {client_ip} ({device_model})")

        # Sync server control parameters with phone immediately
        await self.send_phone_control("set_flash", enabled=self.flash_enabled)
        await self.send_phone_control("set_quality", quality=self.jpeg_quality)
        await self.send_phone_control("set_fps", fps=self.target_fps)
        await self.send_phone_control("set_audio", enabled=self.audio_enabled)

        await self.broadcast_event({
            "type": "PHONE_CONNECTED",
            "phone_info": self.phone_info,
            "controls": self.get_controls_dict(),
        })

    async def unregister_phone(self):
        """Handles phone disconnection gracefully without stopping proxy listeners."""
        print("[StreamHub] Phone disconnected. Waiting for reconnection...")
        self.phone_socket = None
        self.phone_info = {"device_model": "None", "connected_at": "", "ip": "", "battery": "N/A", "flash_supported": "Unknown"}
        await self.broadcast_event({"type": "PHONE_DISCONNECTED"})

    async def register_proxy(self, websocket: WebSocket):
        """Registers an internal program or viewer to receive live raw video frames."""
        self.proxy_clients.add(websocket)
        if self.latest_frame:
            try:
                await websocket.send_bytes(self.latest_frame)
            except Exception:
                pass

    def unregister_proxy(self, websocket: WebSocket):
        """Removes a video proxy client upon disconnection."""
        self.proxy_clients.discard(websocket)

    async def register_audio_proxy(self, websocket: WebSocket):
        """Registers an internal client or web viewer to receive live binary audio chunks."""
        self.audio_proxy_clients.add(websocket)

    def unregister_audio_proxy(self, websocket: WebSocket):
        """Removes an audio proxy client upon disconnection."""
        self.audio_proxy_clients.discard(websocket)

    # ---------------- Control Methods ---------------- #

    async def send_phone_control(self, action: str, **kwargs) -> bool:
        """Sends a JSON control instruction to the mobile phone over WebSocket."""
        if not self.phone_socket:
            return False
        try:
            payload = {"type": "CONTROL", "action": action, **kwargs}
            await self.phone_socket.send_text(json.dumps(payload))
            return True
        except Exception as e:
            print(f"[StreamHub] Error sending control to phone: {e}")
            return False

    async def set_flash(self, enabled: bool) -> bool:
        """Turns the rear camera flash on or off."""
        self.flash_enabled = bool(enabled)
        sent = await self.send_phone_control("set_flash", enabled=self.flash_enabled)
        await self.broadcast_event({
            "type": "CONTROL_UPDATED",
            "control": "flash",
            "enabled": self.flash_enabled,
            "phone_received": sent,
        })
        return sent

    async def set_quality(self, quality: int) -> bool:
        """Programmatically controls the hardware JPEG compression quality (10 - 100)."""
        clamped = max(10, min(100, int(quality)))
        self.jpeg_quality = clamped
        sent = await self.send_phone_control("set_quality", quality=clamped)
        await self.broadcast_event({
            "type": "CONTROL_UPDATED",
            "control": "quality",
            "quality": clamped,
            "phone_received": sent,
        })
        return sent

    async def set_fps(self, fps: int) -> bool:
        """Programmatically controls the target framerate (1 - 60 FPS)."""
        clamped = max(1, min(60, int(fps)))
        self.target_fps = clamped
        sent = await self.send_phone_control("set_fps", fps=clamped)
        await self.broadcast_event({
            "type": "CONTROL_UPDATED",
            "control": "fps",
            "fps": clamped,
            "phone_received": sent,
        })
        return sent

    async def set_audio(self, enabled: bool) -> bool:
        """Enables or disables microphone audio capture and transmission."""
        self.audio_enabled = bool(enabled)
        sent = await self.send_phone_control("set_audio", enabled=self.audio_enabled)
        await self.broadcast_event({
            "type": "CONTROL_UPDATED",
            "control": "audio",
            "enabled": self.audio_enabled,
            "phone_received": sent,
        })
        return sent

    def get_controls_dict(self) -> dict:
        """Returns the current state of all remote hardware controls."""
        return {
            "flash_enabled": self.flash_enabled,
            "quality": self.jpeg_quality,
            "fps": self.target_fps,
            "audio_enabled": self.audio_enabled,
            "phone_connected": self.phone_socket is not None,
        }

    # ---------------- Stream Ingestion & Dispatch ---------------- #

    async def handle_incoming_frame(self, raw_bytes: bytes):
        """
        Processes a raw binary packet from the mobile phone.

        Byte layout:
          - 0x00: Rear Camera JPEG frame
          - 0x01: Front Camera JPEG frame (filtered out)
          - 0x02: Microphone Audio PCM 16kHz chunk
          - Default: Direct JPEG frame
        """
        if len(raw_bytes) < 4:
            return

        prefix = raw_bytes[0]

        # Audio chunk packet (0x02)
        if prefix == 0x02:
            pcm_payload = raw_bytes[1:]
            await self.handle_incoming_audio(pcm_payload)
            return

        # Front camera frame (0x01): skip to preserve bandwidth and focus on rear camera
        if prefix == 0x01:
            return

        # Rear camera frame (0x00) or non-prefixed JPEG
        if prefix == 0x00:
            jpeg_payload = raw_bytes[1:]
        else:
            jpeg_payload = raw_bytes

        # Update cache and telemetry
        self.latest_frame = jpeg_payload
        self.stats.record_frame(len(jpeg_payload))

        # Forward directly to all HTTP MJPEG stream queues
        for q in list(self._mjpeg_subscribers):
            if q.full():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                q.put_nowait(jpeg_payload)
            except asyncio.QueueFull:
                pass

        # Forward directly to internal proxy WebSocket clients
        if self.proxy_clients:
            dead_clients = []
            for client in self.proxy_clients:
                try:
                    await client.send_bytes(jpeg_payload)
                except Exception:
                    dead_clients.append(client)

            for dead in dead_clients:
                self.proxy_clients.discard(dead)

    async def handle_incoming_audio(self, pcm_chunk: bytes):
        """Processes an incoming PCM audio chunk from the mobile microphone."""
        self.audio_stats.record_chunk(len(pcm_chunk))

        # Forward to HTTP audio subscribers
        for q in list(self._audio_subscribers):
            if q.full():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                q.put_nowait(pcm_chunk)
            except asyncio.QueueFull:
                pass

        # Forward to raw audio WebSocket proxy clients
        if self.audio_proxy_clients:
            dead_clients = []
            for client in self.audio_proxy_clients:
                try:
                    await client.send_bytes(pcm_chunk)
                except Exception:
                    dead_clients.append(client)

            for dead in dead_clients:
                self.audio_proxy_clients.discard(dead)

    async def broadcast_event(self, event_dict: dict):
        """Broadcasts a JSON control/telemetry event to all connected proxy clients."""
        if not self.proxy_clients:
            return
        dead_clients = []
        for client in self.proxy_clients:
            try:
                await client.send_json(event_dict)
            except Exception:
                dead_clients.append(client)

        for dead in dead_clients:
            self.proxy_clients.discard(dead)

    # ---------------- HTTP Stream Generators ---------------- #

    async def generate_mjpeg_stream(self):
        """
        Asynchronous generator for HTTP multipart/x-mixed-replace MJPEG video stream.
        Universal compatibility for OpenCV, VLC, web browsers, and internal programs.
        """
        q = asyncio.Queue(maxsize=3)
        if self.latest_frame:
            q.put_nowait(self.latest_frame)
        self._mjpeg_subscribers.add(q)
        try:
            while True:
                try:
                    frame = await asyncio.wait_for(q.get(), timeout=2.0)
                except asyncio.TimeoutError:
                    if self.latest_frame:
                        frame = self.latest_frame
                    else:
                        continue

                header = (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n"
                )
                yield header + frame + b"\r\n"
        finally:
            self._mjpeg_subscribers.discard(q)

    async def generate_audio_stream(self, format_type: str = "wav"):
        """
        Asynchronous generator for live microphone audio streaming.
        Supports WAV streaming (with standard 44-byte continuous header) or raw PCM.
        Compatible with VLC, FFmpeg, and Python requests/sounddevice.
        """
        q = asyncio.Queue(maxsize=15)
        self._audio_subscribers.add(q)

        try:
            if format_type.lower() == "wav":
                # Create a 44-byte standard RIFF WAV header configured for streaming
                byte_rate = AUDIO_SAMPLE_RATE * AUDIO_CHANNELS * (AUDIO_BIT_DEPTH // 8)
                block_align = AUDIO_CHANNELS * (AUDIO_BIT_DEPTH // 8)
                header = struct.pack(
                    "<4sI4s4sIHHIIHH4sI",
                    b"RIFF",
                    0x7FFFFFF0,  # Arbitrary large stream length
                    b"WAVE",
                    b"fmt ",
                    16,  # Subchunk1Size for PCM
                    1,   # AudioFormat (1 = PCM)
                    AUDIO_CHANNELS,
                    AUDIO_SAMPLE_RATE,
                    byte_rate,
                    block_align,
                    AUDIO_BIT_DEPTH,
                    b"data",
                    0x7FFFFFF0 - 36,
                )
                yield header

            while True:
                try:
                    chunk = await asyncio.wait_for(q.get(), timeout=2.0)
                    yield chunk
                except asyncio.TimeoutError:
                    # Keep connection alive with silent frame if audio is paused
                    silence = b"\x00" * 320
                    yield silence
        finally:
            self._audio_subscribers.discard(q)

    def get_stats(self) -> dict:
        """Returns streaming telemetry, audio metrics, and remote controls state."""
        return {
            "phone_connected": self.phone_socket is not None,
            "phone_info": self.phone_info,
            "stream": self.stats.to_dict(),
            "audio": self.audio_stats.to_dict(),
            "controls": self.get_controls_dict(),
            "proxy_clients_count": len(self.proxy_clients),
            "audio_proxy_clients_count": len(self.audio_proxy_clients),
        }


# Global singleton instance
hub = StreamHub()
