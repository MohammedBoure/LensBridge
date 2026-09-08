"""UDP Auto-Discovery Service for Vision Desktop Server.

Broadcasts beacon announcements across the local Wi-Fi network and replies
instantly to mobile client discovery probes so the phone can connect automatically.
"""

import json
import socket
import threading
import time
from typing import Optional
from config import DISCOVERY_PORT, HTTP_PORT, get_local_ip

BEACON_INTERVAL_SECONDS = 2.0
PROBE_MESSAGE = "VISION_DISCOVER_PROBE"


class DiscoveryService:
    """Manages UDP beacon broadcasting and probe responses for seamless Wi-Fi auto-discovery."""

    def __init__(self, http_port: int = HTTP_PORT, discovery_port: int = DISCOVERY_PORT):
        self.http_port = http_port
        self.discovery_port = discovery_port
        self._running = False
        self._broadcast_thread: Optional[threading.Thread] = None
        self._listener_thread: Optional[threading.Thread] = None

    def start(self):
        """Starts the discovery broadcaster and responder threads."""
        if self._running:
            return
        self._running = True

        self._broadcast_thread = threading.Thread(target=self._broadcast_loop, daemon=True)
        self._listener_thread = threading.Thread(target=self._listener_loop, daemon=True)

        self._broadcast_thread.start()
        self._listener_thread.start()
        print(f"[Discovery] UDP auto-discovery service started on port {self.discovery_port}")

    def stop(self):
        """Stops the discovery service gracefully."""
        self._running = False

    def _create_payload(self) -> bytes:
        """Constructs the JSON announcement payload with local network coordinates."""
        local_ip = get_local_ip()
        payload = {
            "type": "VISION_SERVER_ANNOUNCE",
            "server_name": socket.gethostname(),
            "ip": local_ip,
            "port": self.http_port,
            "stream_endpoint": f"ws://{local_ip}:{self.http_port}/ws/phone",
            "timestamp": time.time(),
        }
        return json.dumps(payload).encode("utf-8")

    def _broadcast_loop(self):
        """Periodically broadcasts beacon packets to the local subnet."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(1.0)

        while self._running:
            try:
                data = self._create_payload()
                sock.sendto(data, ("255.255.255.255", self.discovery_port))
            except Exception as e:
                # Network might temporarily be down or transitioning
                pass
            time.sleep(BEACON_INTERVAL_SECONDS)

        sock.close()

    def _listener_loop(self):
        """Listens for direct discovery requests from mobile devices on Wi-Fi."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", self.discovery_port))
            sock.settimeout(1.0)

            while self._running:
                try:
                    data, addr = sock.recvfrom(1024)
                    message = data.decode("utf-8", errors="ignore").strip()
                    if message == PROBE_MESSAGE or "VISION_DISCOVER" in message:
                        response_data = self._create_payload()
                        sock.sendto(response_data, addr)
                except socket.timeout:
                    continue
                except Exception:
                    time.sleep(0.5)
        except Exception as e:
            print(f"[Discovery] Listener warning: {e}")
        finally:
            sock.close()


if __name__ == "__main__":
    service = DiscoveryService()
    service.start()
    print("Broadcasting... Press Ctrl+C to exit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        service.stop()
