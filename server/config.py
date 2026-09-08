"""Server configuration settings for the Vision Desktop Server."""

import socket

# Network configuration
DEFAULT_HOST = "0.0.0.0"
HTTP_PORT = 8765
DISCOVERY_PORT = 45454
BROADCAST_IP = "255.255.255.255"

# Video streaming settings
JPEG_QUALITY = 75
DEFAULT_FPS_TARGET = 30
MAX_BUFFER_FRAMES = 5

def get_local_ip() -> str:
    """Detects the active local LAN/Wi-Fi IP address of the host machine."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Does not actually establish connection; selects the appropriate route
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"
