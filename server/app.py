"""FastAPI application for Vision Desktop Server & Stream Proxy.

Provides HTTP MJPEG video stream, raw WebSocket proxy, snapshot API,
and browser dashboard for converting the mobile camera stream to internal programs.
"""

import json
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from config import HTTP_PORT, get_local_ip
from stream_hub import hub

app = FastAPI(title="Vision Back-Camera Stream Proxy", version="2.0.0")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
async def get_index():
    """Serves the main desktop live viewer and proxy control dashboard."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h1>Vision Server Running. Proxy active.</h1>")


@app.get("/api/status")
async def get_status():
    """Returns current server status, proxy stream URLs, and telemetry."""
    local_ip = get_local_ip()
    return {
        "status": "online",
        "local_ip": local_ip,
        "http_port": HTTP_PORT,
        "proxy_urls": {
            "mjpeg_stream": f"http://{local_ip}:{HTTP_PORT}/stream/video",
            "mjpeg_alias": f"http://{local_ip}:{HTTP_PORT}/video_feed",
            "websocket_proxy": f"ws://{local_ip}:{HTTP_PORT}/ws/proxy",
            "snapshot": f"http://{local_ip}:{HTTP_PORT}/snapshot",
        },
        "metrics": hub.get_stats(),
    }


@app.get("/stream/video")
@app.get("/video_feed")
async def get_video_stream():
    """
    Universal HTTP multipart/x-mixed-replace MJPEG video stream.
    Directly consumable by OpenCV (cv2.VideoCapture), VLC, FFmpeg, and web browsers.
    """
    return StreamingResponse(
        hub.generate_mjpeg_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.get("/snapshot")
@app.get("/snapshot.jpg")
async def get_latest_snapshot():
    """Returns the latest captured JPEG frame from the back camera."""
    if not hub.latest_frame:
        return Response(content=b"No frame received yet", status_code=404, media_type="text/plain")
    return Response(content=hub.latest_frame, media_type="image/jpeg")


@app.websocket("/ws/phone")
async def websocket_phone_endpoint(websocket: WebSocket):
    """
    Incoming WebSocket channel from the mobile application.
    Accepts continuous back camera video frames.
    """
    await websocket.accept()
    device = websocket.query_params.get("device", "Mobile Phone")
    client_ip = websocket.client.host if websocket.client else "Unknown"
    await hub.register_phone(websocket, client_ip, device)

    try:
        while True:
            message = await websocket.receive()
            if "bytes" in message and message["bytes"]:
                await hub.handle_incoming_frame(message["bytes"])
            elif "text" in message and message["text"]:
                try:
                    payload = json.loads(message["text"])
                    if payload.get("type") == "DEVICE_INFO":
                        hub.phone_info["device_model"] = payload.get("device_model", device)
                        hub.phone_info["battery"] = payload.get("battery", "N/A")
                        await hub.broadcast_event({
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


@app.websocket("/ws/proxy")
async def websocket_proxy_endpoint(websocket: WebSocket):
    """
    Proxy WebSocket channel for internal applications.
    Broadcasts raw JPEG binary frames directly with sub-10ms latency.
    """
    await websocket.accept()
    await hub.register_proxy(websocket)

    try:
        while True:
            # Keep-alive ping receiver from internal client
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        hub.unregister_proxy(websocket)
    except Exception:
        hub.unregister_proxy(websocket)
