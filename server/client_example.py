"""Vision Stream Bridge • Internal Program Integration & Permissions Example.

Demonstrates how internal software (AI inference pipelines, OpenCV,
automated testing, VLC/audio recorders, robot control systems) can:
1. Authenticate with Granular API Tokens (via X-API-Key, Bearer Header, or Query Params).
2. Exercise role-based permissions (Viewer vs Controller vs Admin).
3. Query and programmatically switch between multiple connected camera sources (/api/devices).
4. Control remote hardware (Flashlight torch, Framerate throttling, JPEG quality, Microphone audio).
"""

import sys
import time
import urllib.request
import urllib.error
import urllib.parse
import json

SERVER_URL = "http://127.0.0.1:8765"


def http_request(method: str, endpoint: str, payload: dict = None, token: str = None) -> tuple[int, dict]:
    """Helper function to execute HTTP requests with optional token authentication."""
    url = f"{SERVER_URL}{endpoint}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-API-Key"] = token

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"error": body}
        return err.code, parsed
    except urllib.error.URLError as err:
        return 0, {"error": str(err.reason)}


def main():
    print("=" * 70)
    print("   Vision Stream Proxy • Granular Permissions & Multi-Source Demo")
    print("=" * 70)

    # 1. Fetch current status & available permission scopes
    status_code, status = http_request("GET", "/api/status")
    if status_code == 0:
        print(f"[!] Unable to connect to server at {SERVER_URL}. Is server running?")
        print("    Start server with: cd server && python app.py")
        sys.exit(1)

    print(f"[*] Server Status          : {status.get('status')} (HTTP {status_code})")
    print(f"[*] Active Broadcasters    : {status.get('metrics', {}).get('total_sources', 0)}")
    print(f"[*] Current Controls       : {status.get('controls')}")
    print("-" * 70)

    # 2. Inspect Permission Scopes and Predefined Roles
    print("[1] Inspecting Server Permission Scopes & Predefined Roles (/api/auth/permissions)...")
    _, perms_info = http_request("GET", "/api/auth/permissions")
    print(f"    Available Scopes: {', '.join(perms_info.get('scopes', []))}")
    print(f"    Predefined Roles: {list(perms_info.get('roles', {}).keys())}")
    print("-" * 70)

    # 3. Multi-Device Management: Query connected broadcast phones
    print("[2] Querying Connected Camera Broadcasters (/api/devices)...")
    _, devices = http_request("GET", "/api/devices")
    active_id = devices.get("active_source_id")
    total_sources = devices.get("total_sources", 0)
    print(f"    Connected Sources: {total_sources}")
    for idx, src in enumerate(devices.get("sources", [])):
        is_active = " [PRIMARY]" if src.get("session_id") == active_id else ""
        print(f"    - Source #{idx + 1}: {src.get('device_model')} ({src.get('client_ip')}) | "
              f"Frames: {src.get('total_frames')} | FPS: {src.get('fps')}{is_active}")
    print("-" * 70)

    # 4. Permission Enforcement Demonstration: Viewer Token (Read-Only)
    # A viewer token has scopes ["stream:video", "stream:audio", "status:read"]
    # It must SUCCEED for GET /api/status and FAIL (403 Forbidden) for POST /api/flash.
    viewer_token = "lb_viewer_demo_read_only"
    print(f"[3] Testing Read-Only Viewer Token: '{viewer_token}'...")

    # Read status with viewer token -> Expected 200 OK
    code, res = http_request("GET", "/api/status", token=viewer_token)
    print(f"    GET /api/status -> HTTP {code} (Allowed: {code == 200})")

    # Attempt to toggle Flash with viewer token -> Expected 403 Forbidden
    code, res = http_request("POST", "/api/flash", payload={"enabled": True}, token=viewer_token)
    print(f"    POST /api/flash -> HTTP {code} (Blocked as Expected: {code == 403})")
    if code == 403:
        print(f"    Access Denied Detail: {res.get('detail')}")
    print("-" * 70)

    # 5. Permission Enforcement: Controller / Service Token (Hardware Control)
    service_token = "lb_service_camera_node_01"
    print(f"[4] Testing Controller/Service Token: '{service_token}'...")

    # Toggle Flashlight
    print("    - Turning Flashlight ON via /api/flash...")
    code, res = http_request("POST", "/api/flash", payload={"enabled": True}, token=service_token)
    print(f"      HTTP {code} Response: {res}")
    time.sleep(1)

    print("    - Turning Flashlight OFF via /api/flash...")
    code, res = http_request("POST", "/api/flash", payload={"enabled": False}, token=service_token)
    print(f"      HTTP {code} Response: {res}")

    # Throttle Framerate (FPS)
    print("    - Setting Framerate to 15 FPS (low power) via /api/fps...")
    code, res = http_request("POST", "/api/fps", payload={"fps": 15}, token=service_token)
    print(f"      HTTP {code} Response: {res}")

    # Set JPEG Compression Quality
    print("    - Setting Compression Quality to 65% via /api/quality...")
    code, res = http_request("POST", "/api/quality", payload={"quality": 65}, token=service_token)
    print(f"      HTTP {code} Response: {res}")

    # Restore default settings
    print("    - Restoring defaults (30 FPS, 75% Quality) via /api/control...")
    code, res = http_request(
        "POST",
        "/api/control",
        payload={"fps": 30, "quality": 75, "audio": True, "flash": False},
        token=service_token
    )
    print(f"      HTTP {code} Response: {res}")
    print("-" * 70)

    # 6. Stream URL Token Authentication for OpenCV / VLC
    print("[5] Media Stream URLs for External Consuming Programs (OpenCV / VLC / FFmpeg):")
    print(f"    OpenCV Video:  cv2.VideoCapture('{SERVER_URL}/stream/video?token={viewer_token}')")
    print(f"    VLC / Audio:   {SERVER_URL}/stream/audio?token={viewer_token}")
    print(f"    Snapshot URI:  {SERVER_URL}/snapshot?token={viewer_token}")
    print("=" * 70)
    print("[✓] Demonstration completed successfully.")


if __name__ == "__main__":
    main()
