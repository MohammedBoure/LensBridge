"""FastAPI application for Vision Desktop Server.

Serves REST endpoints, WebSocket streaming channels, and modern HTML5 dashboard.
"""

import io
import json
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response, Query
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from config import HTTP_PORT, get_local_ip
from stream_hub import hub

app = FastAPI(title="Vision Dual-Camera Server", version="1.0.0")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
async def get_index():
    """Serves the main desktop live viewer dashboard."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h1>Vision Server Running. Static dashboard missing.</h1>")


@app.get("/api/status")
async def get_status():
    """Returns the current server and dual camera streaming status."""
    return {
        "status": "online",
        "local_ip": get_local_ip(),
        "http_port": HTTP_PORT,
        "metrics": hub.get_stats(),
    }


@app.get("/api/snapshot/{camera}")
async def get_snapshot(camera: str):
    """Returns the latest captured JPEG snapshot from the specified camera ('rear' or 'front')."""
    cam_key = camera.lower()
    if cam_key not in hub.latest_frames or not hub.latest_frames[cam_key]:
        return Response(content=b"No frame available yet", status_code=404, media_type="text/plain")

    return Response(content=hub.latest_frames[cam_key], media_type="image/jpeg")


@app.websocket("/ws/phone")
async def websocket_phone_stream(websocket: WebSocket, device: str = Query("Mobile Device")):
    """
    WebSocket channel for the mobile phone.

    Receives binary video frames containing concurrent front and rear camera feeds.
    Format: [1-byte camera index (0=rear, 1=front)] + [JPEG payload bytes]
    """
    await websocket.accept()
    client_ip = websocket.client.host if websocket.client else "Unknown"
    await hub.register_phone(websocket, client_ip, device)

    try:
        while True:
            # Handle incoming binary frame or json metadata
            message = await websocket.receive()
            if "bytes" in message and message["bytes"]:
                await hub.handle_incoming_frame(message["bytes"])
            elif "text" in message and message["text"]:
                try:
                    payload = json.loads(message["text"])
                    if payload.get("type") == "DEVICE_INFO":
                        hub.phone_info["device_model"] = payload.get("device_model", device)
                        hub.phone_info["battery"] = payload.get("battery", "N/A")
                        await hub.broadcast_server_event({
                            "type": "DEVICE_INFO_UPDATED",
                            "phone_info": hub.phone_info,
                        })
                except Exception:
                    pass
    except WebSocketDisconnect:
        await hub.unregister_phone()
    except Exception as e:
        print(f"[Phone Stream Error] {e}")
        await hub.unregister_phone()


@app.websocket("/ws/client")
async def websocket_desktop_client(websocket: WebSocket):
    """
    WebSocket channel for desktop viewer clients.

    Broadcasts real-time frames for both rear and front cameras as well as stats.
    """
    await websocket.accept()
    await hub.register_viewer(websocket)
    try:
        while True:
            # Keep-alive / command receiver from viewer (e.g. ping, request snapshot)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        hub.unregister_viewer(websocket)
    except Exception:
        hub.unregister_viewer(websocket)
