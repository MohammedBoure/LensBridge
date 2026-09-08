"""Stream Hub for managing dual camera video streams and client connections.

Receives concurrent rear and front camera frames from the mobile application,
tracks frame rates and diagnostics, and broadcasts live feeds to desktop viewers.
"""

import asyncio
import base64
import collections
import time
from typing import Dict, Optional, Set
from fastapi import WebSocket


class CameraStats:
    """Tracks performance metrics (FPS, bandwidth, frame count) for a single camera stream."""

    def __init__(self, name: str):
        self.name = name
        self.frame_count = 0
        self.total_bytes = 0
        self.current_fps = 0.0
        self.bitrate_kbps = 0.0
        self.last_frame_time = 0.0
        self._timestamps = collections.deque(maxlen=30)
        self._bytes_history = collections.deque(maxlen=30)

    def record_frame(self, frame_size: int):
        """Records a newly arrived frame and updates rolling statistics."""
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
        """Returns statistics snapshot as a dictionary."""
        is_active = (time.time() - self.last_frame_time) < 3.0 if self.last_frame_time > 0 else False
        return {
            "name": self.name,
            "active": is_active,
            "fps": self.current_fps if is_active else 0.0,
            "bitrate_kbps": self.bitrate_kbps if is_active else 0.0,
            "total_frames": self.frame_count,
            "last_seen": round(self.last_frame_time, 2),
        }


class StreamHub:
    """Central broker coordinating mobile phone video streams and desktop viewers."""

    def __init__(self):
        self.phone_socket: Optional[WebSocket] = None
        self.desktop_viewers: Set[WebSocket] = set()

        # Cache latest frame for both cameras (bytes)
        self.latest_frames: Dict[str, bytes] = {
            "rear": b"",
            "front": b"",
        }

        # Stream statistics
        self.stats = {
            "rear": CameraStats("Rear Camera"),
            "front": CameraStats("Front Camera"),
        }
        self.phone_info: Dict[str, str] = {
            "device_model": "Unknown",
            "connected_at": "",
            "ip": "",
        }
        self.camera_status: dict = {
            "rear_active": True,
            "front_active": False,
            "front_message": "Standby",
        }

    async def register_phone(self, websocket: WebSocket, client_ip: str, device_model: str = "Mobile"):
        """Registers the mobile phone as the active streaming source."""
        self.phone_socket = websocket
        self.phone_info = {
            "device_model": device_model,
            "connected_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "ip": client_ip,
        }
        print(f"[StreamHub] Phone connected from {client_ip} ({device_model})")
        await self.broadcast_server_event({
            "type": "PHONE_CONNECTED",
            "phone_info": self.phone_info,
            "camera_status": self.camera_status,
        })

    async def unregister_phone(self):
        """Handles phone disconnection."""
        print("[StreamHub] Phone disconnected.")
        self.phone_socket = None
        self.phone_info = {"device_model": "None", "connected_at": "", "ip": ""}
        await self.broadcast_server_event({"type": "PHONE_DISCONNECTED"})

    async def register_viewer(self, websocket: WebSocket):
        """Registers a desktop viewer client."""
        self.desktop_viewers.add(websocket)
        # Send initial status & cached frames immediately
        await websocket.send_json({
            "type": "INITIAL_STATE",
            "phone_info": self.phone_info,
            "camera_status": self.camera_status,
            "stats": self.get_stats(),
        })
        for cam_id in ["rear", "front"]:
            if self.latest_frames[cam_id]:
                # Send latest cached frame
                prefix = 0x00 if cam_id == "rear" else 0x01
                await websocket.send_bytes(bytes([prefix]) + self.latest_frames[cam_id])

    def unregister_viewer(self, websocket: WebSocket):
        """Removes a desktop viewer client."""
        self.desktop_viewers.discard(websocket)

    async def handle_incoming_frame(self, raw_bytes: bytes):
        """
        Processes a raw binary frame from the mobile application.

        Byte layout:
          - Byte 0: Camera Identifier (0x00 = Rear, 0x01 = Front)
          - Bytes 1..N: JPEG compressed image payload
        """
        if len(raw_bytes) < 2:
            return

        camera_code = raw_bytes[0]
        camera_id = "rear" if camera_code == 0x00 else "front"
        jpeg_payload = raw_bytes[1:]

        # Update stats and frame cache
        self.latest_frames[camera_id] = jpeg_payload
        self.stats[camera_id].record_frame(len(jpeg_payload))

        # Forward directly to all desktop viewers
        if self.desktop_viewers:
            dead_viewers = []
            for viewer in self.desktop_viewers:
                try:
                    await viewer.send_bytes(raw_bytes)
                except Exception:
                    dead_viewers.append(viewer)

            for dead in dead_viewers:
                self.desktop_viewers.discard(dead)

    async def broadcast_server_event(self, event_dict: dict):
        """Broadcasts a JSON control event to all desktop viewers."""
        if not self.desktop_viewers:
            return
        dead_viewers = []
        for viewer in self.desktop_viewers:
            try:
                await viewer.send_json(event_dict)
            except Exception:
                dead_viewers.append(viewer)

        for dead in dead_viewers:
            self.desktop_viewers.discard(dead)

    def get_stats(self) -> dict:
        """Returns comprehensive streaming diagnostics."""
        return {
            "phone_connected": self.phone_socket is not None,
            "phone_info": self.phone_info,
            "rear": self.stats["rear"].to_dict(),
            "front": self.stats["front"].to_dict(),
            "viewer_count": len(self.desktop_viewers),
        }


# Global singleton instance
hub = StreamHub()
