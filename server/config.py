"""Server configuration settings for the Vision Desktop Server."""

import socket

# Network configuration
DEFAULT_HOST = "0.0.0.0"
HTTP_PORT = 8765
DISCOVERY_PORT = 45454
BROADCAST_IP = "255.255.255.255"

# Video streaming & remote hardware controls
DEFAULT_FLASH_ENABLED = False
DEFAULT_JPEG_QUALITY = 75
DEFAULT_FPS_TARGET = 30
MAX_BUFFER_FRAMES = 5

# Audio streaming settings (Microphone 16kHz 16-bit Mono PCM)
DEFAULT_AUDIO_ENABLED = True
AUDIO_SAMPLE_RATE = 16000
AUDIO_CHANNELS = 1
AUDIO_BIT_DEPTH = 16
AUDIO_CHUNK_SIZE = 2048

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
