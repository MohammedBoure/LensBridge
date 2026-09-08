"""Stream Hub for Vision Desktop Server.

Focuses exclusively on the back (rear) camera stream and acts as a high-performance
video proxy/bridge forwarding live frames to internal programs via HTTP MJPEG,
WebSocket, and REST snapshot endpoints.
"""

import asyncio
import collections
import time
from typing import Dict, Optional, Set
from fastapi import WebSocket


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


class StreamHub:
    """Central proxy broker coordinating mobile camera stream and external internal programs."""

    def __init__(self):
        self.phone_socket: Optional[WebSocket] = None
        self.proxy_clients: Set[WebSocket] = set()
        self.latest_frame: bytes = b""
        self.stats = StreamStats()

        # Active queue subscribers for HTTP MJPEG streaming
        self._mjpeg_subscribers: Set[asyncio.Queue] = set()

        self.phone_info: Dict[str, str] = {
            "device_model": "None",
            "connected_at": "",
            "ip": "",
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
        await self.broadcast_event({
            "type": "PHONE_CONNECTED",
            "phone_info": self.phone_info,
        })

    async def unregister_phone(self):
        """Handles phone disconnection gracefully without stopping the proxy server."""
        print("[StreamHub] Phone disconnected. Waiting for reconnection...")
        self.phone_socket = None
        self.phone_info = {"device_model": "None", "connected_at": "", "ip": ""}
        await self.broadcast_event({"type": "PHONE_DISCONNECTED"})

    async def register_proxy(self, websocket: WebSocket):
        """Registers an internal program or viewer to receive live raw frames."""
        self.proxy_clients.add(websocket)
        # Send latest frame immediately if available
        if self.latest_frame:
            try:
                await websocket.send_bytes(self.latest_frame)
            except Exception:
                pass

    def unregister_proxy(self, websocket: WebSocket):
        """Removes a proxy client upon disconnection."""
        self.proxy_clients.discard(websocket)

    async def handle_incoming_frame(self, raw_bytes: bytes):
        """
        Processes a raw binary frame from the mobile application.

        Byte layout:
          - If prefixed: Byte 0 is camera code (0x00=Rear, 0x01=Front).
            We process Rear camera (0x00) frames or non-prefixed JPEG bytes.
        """
        if len(raw_bytes) < 4:
            return

        # Check if first byte is a camera prefix
        if raw_bytes[0] == 0x01:
            # Skip front camera frames; backend focuses exclusively on rear camera
            return

        if raw_bytes[0] == 0x00:
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

    async def broadcast_event(self, event_dict: dict):
        """Broadcasts a JSON control event to all proxy clients."""
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

    def get_stats(self) -> dict:
        """Returns streaming telemetry and connection state."""
        return {
            "phone_connected": self.phone_socket is not None,
            "phone_info": self.phone_info,
            "stream": self.stats.to_dict(),
            "proxy_clients_count": len(self.proxy_clients),
        }


# Global singleton instance
hub = StreamHub()
