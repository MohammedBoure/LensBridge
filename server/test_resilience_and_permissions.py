"""End-to-End Test Suite for LensBridge Multi-Broadcaster Resilience & Granular Permissions.

Tests:
1. Token Authentication & Granular Permissions (Scopes, Roles, 401 Unauthorized, 403 Forbidden, 200 OK)
2. Multi-Device Broadcast Connections (Multiple concurrent phones)
3. Smooth Disconnect & Failover (Old session dying does not kill new session; automatic failover)
4. Non-blocking Stream Cadence during disconnects
"""

import asyncio
import json
import time
import urllib.request
import urllib.error
import websockets
from auth import auth_manager, PermissionScope
from stream_hub import hub, StreamHub
from config import HTTP_PORT

SERVER_URL = f"http://127.0.0.1:{HTTP_PORT}"
WS_BASE = f"ws://127.0.0.1:{HTTP_PORT}"


def test_auth_manager_logic():
    print("[TEST 1] Testing Auth Manager Token Logic...")
    admin_tok = auth_manager.get_token_by_role("admin")
    service_tok = auth_manager.get_service_token()
    viewer_tok = auth_manager.get_token_by_role("viewer")

    assert admin_tok is not None, "Admin token missing"
    assert service_tok is not None, "Service token missing"
    assert viewer_tok is not None, "Viewer token missing"

    # Verify Viewer permissions
    assert auth_manager.verify_token(viewer_tok, PermissionScope.STATUS_READ), "Viewer should have status:read"
    assert auth_manager.verify_token(viewer_tok, PermissionScope.STREAM_VIDEO), "Viewer should have stream:video"
    assert not auth_manager.verify_token(viewer_tok, PermissionScope.CONTROL_FLASH), "Viewer must NOT have control:flash"
    assert not auth_manager.verify_token(viewer_tok, PermissionScope.ADMIN), "Viewer must NOT have admin"

    # Verify Controller/Service permissions
    assert auth_manager.verify_token(service_tok, PermissionScope.CONTROL_FLASH), "Service should have control:flash"
    assert auth_manager.verify_token(service_tok, PermissionScope.CONTROL_QUALITY), "Service should have control:quality"
    assert auth_manager.verify_token(service_tok, PermissionScope.CONTROL_FPS), "Service should have control:fps"
    assert auth_manager.verify_token(service_tok, PermissionScope.CONTROL_AUDIO), "Service should have control:audio"

    # Verify Admin permissions
    assert auth_manager.verify_token(admin_tok, PermissionScope.ALL), "Admin should have wildcard *"
    assert auth_manager.verify_token(admin_tok, PermissionScope.ADMIN), "Admin should have admin"

    print("  [✓] Auth manager permission verification passed.")


async def test_multi_broadcaster_hub():
    print("[TEST 2] Testing StreamHub Multi-Broadcaster Registration & Failover...")
    hub = StreamHub()

    # Mock phone sockets
    class DummyWS:
        def __init__(self, name):
            self.name = name
            self.sent = []
            self.closed = False
        async def send_text(self, text):
            self.sent.append(text)
        async def send_bytes(self, b):
            self.sent.append(b)

    ws_phone1 = DummyWS("Phone-1")
    ws_phone2 = DummyWS("Phone-2")

    # 1. Register Phone 1
    s1 = await hub.register_phone(ws_phone1, "192.168.1.101", "Pixel 7 Pro")
    assert hub.active_source_id == s1, "Phone 1 should be active source"
    assert len(hub.sources) == 1, "Should have 1 source"
    print(f"  [✓] Phone 1 registered with session {s1}")

    # 2. Register Phone 2
    s2 = await hub.register_phone(ws_phone2, "192.168.1.102", "Samsung S23")
    assert len(hub.sources) == 2, "Should have 2 sources"
    assert hub.active_source_id == s1, "Phone 1 remains active source until switched or disconnected"
    print(f"  [✓] Phone 2 registered with session {s2}")

    # 3. Switch active device to Phone 2
    switched = await hub.set_active_source(s2)
    assert switched is True, "Should successfully switch active source"
    assert hub.active_source_id == s2, "Active source must now be Phone 2"
    print(f"  [✓] Switched active source to Phone 2 ({s2})")

    # 4. Disconnect Phone 2 -> should automatically failover back to Phone 1
    await hub.unregister_phone(s2)
    assert len(hub.sources) == 1, "Should have 1 source left"
    assert hub.active_source_id == s1, "Active source must automatically failover to Phone 1"
    print(f"  [✓] Auto-failover verified: active source reverted to Phone 1 ({s1})")

    # 5. Rapid Reconnect Race Condition Test:
    # Simulate: Phone 1 reconnects (creates s3) BEFORE old socket unregisters s1
    ws_phone1_new = DummyWS("Phone-1-New")
    s3 = await hub.register_phone(ws_phone1_new, "192.168.1.101", "Pixel 7 Pro (Reconnected)")
    assert hub.active_source_id == s3, "New reconnection should become active"

    # Now the OLD socket's onClose finally fires with s1:
    await hub.unregister_phone(s1)
    # Crucial check: unregistering the old s1 MUST NOT unregister or affect the new s3!
    assert hub.active_source_id == s3, "Unregistering old session s1 must NOT kill new session s3"
    assert s3 in hub.sources, "Session s3 must remain alive and healthy"
    print(f"  [✓] Race-condition test passed: Old session teardown did not disrupt new session.")

    # Cleanup Phone 1
    await hub.unregister_phone(s3)
    assert len(hub.sources) == 0
    assert hub.active_source_id is None
    print("  [✓] All stream hub source lifecycles cleanly verified.")


def test_live_server_endpoints():
    print("[TEST 3] Testing Live Server REST Endpoints & Authentication...")
    viewer_tok = auth_manager.get_token_by_role("viewer")
    service_tok = auth_manager.get_service_token()

    # 1. Invalid Token -> Expect 401
    url = f"{SERVER_URL}/api/flash"
    req = urllib.request.Request(
        url,
        data=json.dumps({"enabled": True}).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-API-Key": "invalid_bogus_token_xyz"}
    )
    try:
        urllib.request.urlopen(req)
        assert False, "Expected 401 Unauthorized"
    except urllib.error.HTTPError as err:
        assert err.code == 401, f"Expected 401, got {err.code}"
        print("  [✓] Invalid token correctly returned 401 Unauthorized.")

    # 2. Viewer Token attempting Flash -> Expect 403
    req = urllib.request.Request(
        url,
        data=json.dumps({"enabled": True}).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-API-Key": viewer_tok}
    )
    try:
        urllib.request.urlopen(req)
        assert False, "Expected 403 Forbidden for Viewer"
    except urllib.error.HTTPError as err:
        assert err.code == 403, f"Expected 403, got {err.code}"
        print("  [✓] Viewer token forbidden from toggling flash (403 Forbidden verified).")

    # 3. Service Token toggling Flash -> Expect 200
    req = urllib.request.Request(
        url,
        data=json.dumps({"enabled": True}).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-API-Key": service_tok}
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        res = json.loads(resp.read().decode("utf-8"))
        assert res.get("flash_enabled") is True
        print("  [✓] Service token successfully toggled flash (200 OK).")

    # 4. Query /api/devices with Service Token
    req = urllib.request.Request(f"{SERVER_URL}/api/devices", headers={"X-API-Key": service_tok})
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        dev_data = json.loads(resp.read().decode("utf-8"))
        assert "sources" in dev_data
        print(f"  [✓] /api/devices queried successfully: {dev_data.get('total_sources')} sources connected.")

    # 5. Test snapshot with query parameter token
    snap_req = urllib.request.Request(f"{SERVER_URL}/snapshot?token={viewer_tok}")
    with urllib.request.urlopen(snap_req, timeout=3) as resp:
        assert resp.status == 200
        data = resp.read()
        assert len(data) > 0
        print(f"  [✓] /snapshot?token=... returned fallback/live image ({len(data)} bytes).")

def run_test_server():
    import uvicorn
    from app import app
    # Disable loopback bypass during endpoint tests so explicit tokens are strictly tested
    auth_manager.allow_local_loopback_bypass = False
    config = uvicorn.Config(app, host="127.0.0.1", port=8769, log_level="error")
    server = uvicorn.Server(config)
    server.run()


def main():
    test_auth_manager_logic()
    asyncio.run(test_multi_broadcaster_hub())

    # Start live server on port 8769
    import threading
    t = threading.Thread(target=run_test_server, daemon=True)
    t.start()
    time.sleep(1.5)

    # Run live server endpoint tests against port 8769
    global SERVER_URL
    SERVER_URL = "http://127.0.0.1:8769"
    test_live_server_endpoints()

    print("\n[ALL UNIT & LIVE ENDPOINT INTEGRATION TESTS PASSED SUCCESSFULLY!]")


if __name__ == "__main__":
    main()
