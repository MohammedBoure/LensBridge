"""Headless Background Service Runner for Vision Stream Bridge.

Designed to run 24/7 as an invisible Windows background service.
Manages:
- File-based rotating logging to service.log
- UDP Auto-Discovery beacon and responder (port 45454)
- FastAPI / Uvicorn reverse proxy server (port 8765)
- Clean shutdown handling
"""

import logging
from logging.handlers import RotatingFileHandler
import os
import signal
import sys
import threading
import time
import uvicorn

from app import app
from config import DEFAULT_HOST, HTTP_PORT, DISCOVERY_PORT, get_local_ip
from discovery import DiscoveryService

# Set up rotating file logger for 24/7 background operation
LOG_FILE = os.path.join(os.path.dirname(__file__), "service.log")
PID_FILE = os.path.join(os.path.dirname(__file__), "service.pid")

logger = logging.getLogger("VisionService")
logger.setLevel(logging.INFO)
file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Also log to stdout if attached
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


def write_pid():
    """Writes the current process ID to service.pid."""
    try:
        with open(PID_FILE, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
    except Exception as e:
        logger.warning(f"Could not write PID file: {e}")


def clear_pid():
    """Removes the PID file upon graceful shutdown."""
    try:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
    except Exception:
        pass


def run_service():
    write_pid()
    local_ip = get_local_ip()
    logger.info("=" * 60)
    logger.info("    VISION STREAM BRIDGE BACKGROUND SERVICE STARTED")
    logger.info("=" * 60)
    logger.info(f"Process ID         : {os.getpid()}")
    logger.info(f"Local Host IP      : {local_ip}")
    logger.info(f"HTTP/WebSocket Port: {HTTP_PORT}")
    logger.info(f"UDP Discovery Port : {DISCOVERY_PORT}")
    logger.info(f"MJPEG Stream URL   : http://{local_ip}:{HTTP_PORT}/stream/video")
    logger.info(f"WebSocket Proxy URL: ws://{local_ip}:{HTTP_PORT}/ws/proxy")
    logger.info(f"Snapshot URL       : http://{local_ip}:{HTTP_PORT}/snapshot")
    logger.info("=" * 60)

    # 1. Start UDP Discovery Service
    discovery = DiscoveryService(http_port=HTTP_PORT, discovery_port=DISCOVERY_PORT)
    discovery.start()
    logger.info(f"Discovery responder active on UDP {DISCOVERY_PORT}")

    # 2. Configure Uvicorn ASGI Server
    config = uvicorn.Config(
        app=app,
        host=DEFAULT_HOST,
        port=HTTP_PORT,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)

    # Signal handlers for graceful shutdown
    def handle_exit(signum, frame):
        logger.info(f"Received shutdown signal ({signum}). Stopping service...")
        discovery.stop()
        server.should_exit = True
        clear_pid()

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    try:
        server.run()
    except Exception as e:
        logger.error(f"Uvicorn error: {e}", exc_info=True)
    finally:
        discovery.stop()
        clear_pid()
        logger.info("Vision Stream Bridge service stopped cleanly.")


if __name__ == "__main__":
    run_service()
