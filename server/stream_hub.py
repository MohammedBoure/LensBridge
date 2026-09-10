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
import secrets
import struct
import time
from typing import Dict, Optional, Set, List
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


class BroadcastSource:
    """Represents an active or standby broadcasting device (e.g. mobile phone)."""

    def __init__(self, session_id: str, websocket: WebSocket, client_ip: str, device_model: str):
        self.session_id = session_id
        self.websocket = websocket
        self.client_ip = client_ip
        self.device_model = device_model
        self.connected_at = time.time()
        self.last_active = time.time()
        self.frames_received = 0
        self.audio_chunks_received = 0
        self.is_active = False
        self.device_info: dict = {
            "device_model": device_model,
            "ip": client_ip,
            "battery": "N/A",
            "flash_supported": "Unknown",
        }

    def to_dict(self) -> dict:
        now = time.time()
        return {
            "session_id": self.session_id,
            "device_model": self.device_model,
            "ip": self.client_ip,
            "connected_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.connected_at)),
            "uptime_seconds": round(now - self.connected_at, 1),
            "last_active_seconds_ago": round(now - self.last_active, 2),
            "frames_received": self.frames_received,
            "audio_chunks_received": self.audio_chunks_received,
            "is_active": self.is_active,
            "battery": self.device_info.get("battery", "N/A"),
            "flash_supported": self.device_info.get("flash_supported", "Unknown"),
        }


# Minimal valid 1x1 JPEG bytes used as placeholder/standby frame
STANDBY_JPEG = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\x08\x06\x06"
    b"\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
    b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01"
    b"\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00"
    b"?\x00\xbf\x00\xff\xd9"
)


class StreamHub:
    """
    Central Coordinator for Video Frames, Microphone Audio, and Remote Hardware Controls.
    Supports multiple concurrent phone broadcaster connections, seamless automatic failover,
    non-blocking client disconnect handling, and granular proxy access.
    """

    def __init__(self):
        # Connected broadcaster devices
        self.sources: Dict[str, BroadcastSource] = {}
        self.active_source_id: Optional[str] = None
        self._hub_lock = asyncio.Lock()

        # Telemetry & counters
        self.total_connections_count: int = 0
        self.total_disconnections_count: int = 0

        # Proxy client sets
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

    @property
    def phone_socket(self) -> Optional[WebSocket]:
        """Returns the WebSocket connection of the active primary broadcast source."""
        if self.active_source_id and self.active_source_id in self.sources:
            return self.sources[self.active_source_id].websocket
        return None

    async def register_phone(self, websocket: WebSocket, client_ip: str, device_model: str = "Mobile") -> str:
        """
        Registers a broadcasting phone session.
        Gracefully supersedes any prior stale connection from the same device/IP
        and smoothly sets the new connection as the active source.
        """
        async with self._hub_lock:
            now_ms = int(time.time() * 1000)
            session_id = f"src_{now_ms}_{secrets.token_hex(4)}"

            # Clean up previous stale connections from the exact same client IP
            superseded = [
                s_id for s_id, src in self.sources.items()
                if src.client_ip == client_ip and s_id != session_id
            ]
            was_active_superseded = (self.active_source_id in superseded)
            for s_id in superseded:
                old_source = self.sources.pop(s_id, None)
                if old_source:
                    try:
                        await old_source.websocket.close(code=1000, reason="Replaced by new connection session")
                    except Exception:
                        pass

            source = BroadcastSource(session_id, websocket, client_ip, device_model)

            # Keep active source uninterrupted if another phone connects concurrently;
            # activate immediately if no active source exists or if reconnecting same device.
            should_activate = (
                self.active_source_id is None
                or self.active_source_id not in self.sources
                or was_active_superseded
            )

            if should_activate:
                for s in self.sources.values():
                    s.is_active = False
                source.is_active = True
                self.active_source_id = session_id
                self.phone_info = {
                    "device_model": device_model,
                    "connected_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "ip": client_ip,
                    "battery": "N/A",
                    "flash_supported": "Unknown",
                }
            else:
                source.is_active = False

            self.sources[session_id] = source
            self.total_connections_count += 1
            print(f"[StreamHub] Broadcaster connected: {device_model} @ {client_ip} (Session: {session_id}, Active: {'YES' if should_activate else 'NO'}, Total: {len(self.sources)})")

        # Synchronize current server hardware parameters to the newly connected phone
        await self.send_phone_control("set_flash", target_session_id=session_id, enabled=self.flash_enabled)
        await self.send_phone_control("set_quality", target_session_id=session_id, quality=self.jpeg_quality)
        await self.send_phone_control("set_fps", target_session_id=session_id, fps=self.target_fps)
        await self.send_phone_control("set_audio", target_session_id=session_id, enabled=self.audio_enabled)

        await self.broadcast_event({
            "type": "PHONE_CONNECTED",
            "session_id": session_id,
            "phone_info": self.phone_info,
            "connected_sources": [s.to_dict() for s in self.sources.values()],
            "controls": self.get_controls_dict(),
        })

        return session_id

    async def unregister_phone(self, session_id: str):
        """
        Gracefully unregisters a specific broadcasting session upon disconnection.
        If multiple broadcasters are connected, seamlessly fails over to the next available source
        without interrupting external proxy subscribers.
        """
        async with self._hub_lock:
            if session_id not in self.sources:
                # Already cleaned up or superseded
                return

            disconnected_source = self.sources.pop(session_id, None)
            self.total_disconnections_count += 1
            desc = f"{disconnected_source.device_model} @ {disconnected_source.client_ip}" if disconnected_source else session_id
            print(f"[StreamHub] Broadcaster disconnected: {desc} (Remaining: {len(self.sources)})")

            # Check if disconnected source was the active primary
            if self.active_source_id == session_id:
                if self.sources:
                    # Seamless failover to next connected broadcaster!
                    new_active_id = next(iter(self.sources.keys()))
                    self.active_source_id = new_active_id
                    new_source = self.sources[new_active_id]
                    new_source.is_active = True

                    self.phone_info = new_source.device_info.copy()
                    self.phone_info["connected_at"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(new_source.connected_at))

                    print(f"[StreamHub] Active broadcast seamlessly failed over to: {new_source.device_model} ({new_active_id})")
                    await self.broadcast_event({
                        "type": "ACTIVE_SOURCE_SWITCHED",
                        "active_session_id": new_active_id,
                        "phone_info": self.phone_info,
                        "connected_sources": [s.to_dict() for s in self.sources.values()],
                    })
                    return
                else:
                    self.active_source_id = None
                    self.phone_info = {
                        "device_model": "None",
                        "connected_at": "",
                        "ip": "",
                        "battery": "N/A",
                        "flash_supported": "Unknown",
                    }
                    await self.broadcast_event({
                        "type": "PHONE_DISCONNECTED",
                        "connected_sources": [],
                    })

    async def set_active_source(self, session_id: str) -> bool:
        """Manually switches the active broadcast source when multiple cameras are connected."""
        async with self._hub_lock:
            if session_id not in self.sources:
                return False

            for s_id, s in self.sources.items():
                s.is_active = (s_id == session_id)

            self.active_source_id = session_id
            active_source = self.sources[session_id]
            self.phone_info = active_source.device_info.copy()
            self.phone_info["connected_at"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(active_source.connected_at))

            await self.broadcast_event({
                "type": "ACTIVE_SOURCE_SWITCHED",
                "active_session_id": session_id,
                "phone_info": self.phone_info,
                "connected_sources": [s.to_dict() for s in self.sources.values()],
            })
            return True

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

    async def send_phone_control(self, action: str, target_session_id: Optional[str] = None, **kwargs) -> bool:
        """Sends a JSON control instruction to the active mobile phone or a specific target session."""
        payload = json.dumps({"type": "CONTROL", "action": action, **kwargs})

        # If a specific target session was provided, deliver to it
        if target_session_id and target_session_id in self.sources:
            try:
                await self.sources[target_session_id].websocket.send_text(payload)
                return True
            except Exception as e:
                print(f"[StreamHub] Error sending control to {target_session_id}: {e}")
                return False

        # Otherwise deliver to active source, or broadcast to all connected sources
        if not self.sources:
            return False

        delivered_any = False
        targets = [self.sources[self.active_source_id]] if (self.active_source_id and self.active_source_id in self.sources) else list(self.sources.values())

        for src in targets:
            try:
                await src.websocket.send_text(payload)
                delivered_any = True
            except Exception as e:
                print(f"[StreamHub] Error sending control to source {src.session_id}: {e}")

        return delivered_any

    async def set_flash(self, enabled: bool, target_session_id: Optional[str] = None) -> bool:
        """Turns the rear camera flash on or off."""
        self.flash_enabled = bool(enabled)
        sent = await self.send_phone_control("set_flash", target_session_id=target_session_id, enabled=self.flash_enabled)
        await self.broadcast_event({
            "type": "CONTROL_UPDATED",
            "control": "flash",
            "enabled": self.flash_enabled,
            "phone_received": sent,
        })
        return sent

    async def set_quality(self, quality: int, target_session_id: Optional[str] = None) -> bool:
        """Programmatically controls the hardware JPEG compression quality (10 - 100)."""
        clamped = max(10, min(100, int(quality)))
        self.jpeg_quality = clamped
        sent = await self.send_phone_control("set_quality", target_session_id=target_session_id, quality=clamped)
        await self.broadcast_event({
            "type": "CONTROL_UPDATED",
            "control": "quality",
            "quality": clamped,
            "phone_received": sent,
        })
        return sent

    async def set_fps(self, fps: int, target_session_id: Optional[str] = None) -> bool:
        """Programmatically controls the target framerate (1 - 60 FPS)."""
        clamped = max(1, min(60, int(fps)))
        self.target_fps = clamped
        sent = await self.send_phone_control("set_fps", target_session_id=target_session_id, fps=clamped)
        await self.broadcast_event({
            "type": "CONTROL_UPDATED",
            "control": "fps",
            "fps": clamped,
            "phone_received": sent,
        })
        return sent

    async def set_audio(self, enabled: bool, target_session_id: Optional[str] = None) -> bool:
        """Enables or disables microphone audio capture and transmission."""
        self.audio_enabled = bool(enabled)
        sent = await self.send_phone_control("set_audio", target_session_id=target_session_id, enabled=self.audio_enabled)
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
            "phone_connected": bool(self.sources),
            "active_source_id": self.active_source_id,
            "connected_sources_count": len(self.sources),
        }

    # ---------------- Stream Ingestion & Dispatch ---------------- #

    async def handle_incoming_frame(self, raw_bytes: bytes, session_id: Optional[str] = None):
        """
        Processes a raw binary packet from a specific mobile session.
        Only dispatches to external consumers if the session is the active primary broadcaster.

        Byte layout:
          - 0x00: Rear Camera JPEG frame
          - 0x01: Front Camera JPEG frame (filtered out)
          - 0x02: Microphone Audio PCM 16kHz chunk
          - Default: Direct JPEG frame
        """
        if len(raw_bytes) < 4:
            return

        # Track per-source activity telemetry
        source = self.sources.get(session_id) if session_id else None
        if source:
            source.last_active = time.time()

        prefix = raw_bytes[0]

        # Audio chunk packet (0x02)
        if prefix == 0x02:
            if source:
                source.audio_chunks_received += 1
            # Forward audio if it's the active source or the only source
            if not self.active_source_id or session_id == self.active_source_id:
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

        if source:
            source.frames_received += 1

        # Only forward frames from the active primary broadcast session
        if self.active_source_id and session_id != self.active_source_id:
            return

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

    def get_standby_frame(self) -> bytes:
        """Returns placeholder JPEG frame when no mobile broadcaster is actively streaming."""
        return STANDBY_JPEG

    # ---------------- HTTP Stream Generators ---------------- #

    async def generate_mjpeg_stream(self):
        """
        Asynchronous generator for HTTP multipart/x-mixed-replace MJPEG video stream.
        Maintains seamless connection through phone disconnections and rapid reconnects.
        """
        q = asyncio.Queue(maxsize=3)
        if self.latest_frame:
            q.put_nowait(self.latest_frame)
        self._mjpeg_subscribers.add(q)
        try:
            while True:
                try:
                    frame = await asyncio.wait_for(q.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    if self.latest_frame:
                        frame = self.latest_frame
                        await asyncio.sleep(0.15)
                    else:
                        await asyncio.sleep(0.2)
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
        Gracefully preserves audio stream pipe through broadcaster reconnection cycles.
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
                    chunk = await asyncio.wait_for(q.get(), timeout=1.0)
                    yield chunk
                except asyncio.TimeoutError:
                    # Keep connection alive with short silence packet if audio stream is idle/reconnecting
                    await asyncio.sleep(0.15)
                    silence = b"\x00" * 320
                    yield silence
        finally:
            self._audio_subscribers.discard(q)

    def get_stats(self) -> dict:
        """Returns streaming telemetry, multi-device broadcaster state, and controls."""
        return {
            "phone_connected": bool(self.sources),
            "active_source_id": self.active_source_id,
            "connected_devices_count": len(self.sources),
            "connected_devices": [s.to_dict() for s in self.sources.values()],
            "total_connections": self.total_connections_count,
            "total_disconnections": self.total_disconnections_count,
            "phone_info": self.phone_info,
            "stream": self.stats.to_dict(),
            "audio": self.audio_stats.to_dict(),
            "controls": self.get_controls_dict(),
            "proxy_clients_count": len(self.proxy_clients),
            "audio_proxy_clients_count": len(self.audio_proxy_clients),
        }


# Global singleton instance
hub = StreamHub()

