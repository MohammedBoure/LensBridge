"""Vision Stream Bridge • Internal Program Integration & Control Example.

Demonstrates how external/internal Python software (AI inference pipelines, OpenCV,
automated testing, VLC/audio recorders) can programmatically control the mobile hardware
via the Vision Desktop Server Internal REST API and consume video & audio streams.
"""

import time
import urllib.request
import json

SERVER_URL = "http://127.0.0.1:8765"


def call_api(endpoint: str, payload: dict) -> dict:
    """Helper function to perform an HTTP POST request to the Internal API."""
    url = f"{SERVER_URL}{endpoint}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_status() -> dict:
    """Retrieves full system telemetry, URLs, and hardware control states."""
    with urllib.request.urlopen(f"{SERVER_URL}/api/status") as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    print("=" * 65)
    print("   Vision Stream Proxy • Internal API Programmatic Control Demo")
    print("=" * 65)

    # 1. Fetch current status
    status = get_status()
    print(f"[*] Server Status     : {status.get('status')}")
    print(f"[*] Phone Connected   : {status.get('metrics', {}).get('phone_connected')}")
    print(f"[*] MJPEG Video URL   : {status.get('proxy_urls', {}).get('mjpeg_stream')}")
    print(f"[*] Live Audio URL    : {status.get('proxy_urls', {}).get('audio_stream_wav')}")
    print(f"[*] Current Controls  : {status.get('controls')}")
    print("-" * 65)

    # 2. Flashlight (Torch) Control
    print("[1] Turning Flash ON via Internal API (/api/flash)...")
    res = call_api("/api/flash", {"enabled": True})
    print(f"    Response: {res}")
    time.sleep(2)

    print("[2] Turning Flash OFF via Internal API (/api/flash)...")
    res = call_api("/api/flash", {"enabled": False})
    print(f"    Response: {res}")
    print("-" * 65)

    # 3. Framerate (FPS) Control (Throttling for energy savings)
    print("[3] Setting Target Framerate to 15 FPS for low battery consumption (/api/fps)...")
    res = call_api("/api/fps", {"fps": 15})
    print(f"    Response: {res}")
    time.sleep(1)

    print("[4] Restoring Target Framerate to 30 FPS (/api/fps)...")
    res = call_api("/api/fps", {"fps": 30})
    print(f"    Response: {res}")
    print("-" * 65)

    # 4. Compression Quality Control (Wi-Fi bandwidth and battery management)
    print("[5] Setting Compression Quality to 50% (/api/quality)...")
    res = call_api("/api/quality", {"quality": 50})
    print(f"    Response: {res}")
    time.sleep(1)

    print("[6] Restoring Compression Quality to 75% (/api/quality)...")
    res = call_api("/api/quality", {"quality": 75})
    print(f"    Response: {res}")
    print("-" * 65)

    # 5. Microphone Audio Transmission Control
    print("[7] Testing Microphone Audio Control (/api/audio)...")
    res = call_api("/api/audio", {"enabled": True})
    print(f"    Response: {res}")
    print("-" * 65)

    # 6. Unified Batch Control Example
    print("[8] Unified Batch Update (/api/control)...")
    batch_payload = {
        "flash": False,
        "quality": 80,
        "fps": 25,
        "audio": True
    }
    res = call_api("/api/control", batch_payload)
    print(f"    Response: {res}")
    print("=" * 65)
    print("Demonstration completed successfully.")


if __name__ == "__main__":
    main()
