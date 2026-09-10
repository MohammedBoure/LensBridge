"""FastAPI application for Vision Desktop Server & Stream Proxy.

Provides HTTP MJPEG video stream, raw WebSocket proxy, snapshot API,
live audio stream (/stream/audio), audio WebSocket proxy (/ws/audio),
and an internal REST API for programmatic hardware control:
- Flashlight / Torch: Turn ON / OFF (/api/flash)
- JPEG Quality: Set 10-100 (/api/quality)
- Number of Frames: Set Target FPS (/api/fps)
- Microphone Audio: Enable / Disable (/api/audio)
- Unified Control: Batch update (/api/control, /api/settings)
"""

import json
import os
from typing import Optional
from pydantic import BaseModel, Field
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response, Query, Body
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from config import HTTP_PORT, get_local_ip
from stream_hub import hub

app = FastAPI(
    title="Vision Back-Camera Stream & Audio Proxy",
    description="High-performance video & microphone audio proxy with internal REST API for remote hardware control.",
    version="2.1.0",
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# Pydantic Schemas for Internal API
class FlashRequest(BaseModel):
    enabled: bool = Field(..., description="True to turn flash ON, False to turn OFF")


class QualityRequest(BaseModel):
    quality: int = Field(..., ge=10, le=100, description="Hardware JPEG quality (10 - 100)")


class FpsRequest(BaseModel):
    fps: int = Field(..., ge=1, le=60, description="Target framerate (1 - 60 FPS)")


class AudioRequest(BaseModel):
    enabled: bool = Field(..., description="True to enable microphone transmission, False to mute/disable")


class ControlRequest(BaseModel):
    flash: Optional[bool] = Field(None, description="Flash ON/OFF")
    quality: Optional[int] = Field(None, ge=10, le=100, description="JPEG quality (10-100)")
    fps: Optional[int] = Field(None, ge=1, le=60, description="Target FPS (1-60)")
    audio: Optional[bool] = Field(None, description="Microphone audio enabled")


# ---------------- Web & Status Endpoints ---------------- #

@app.get("/", response_class=HTMLResponse)
async def get_index():
    """Serves the main desktop live viewer and proxy control dashboard."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h1>Vision Server Running. Proxy & Internal API active.</h1>")


@app.get("/api/status")
async def get_status():
    """Returns current server status, proxy stream URLs, internal API endpoints, and telemetry."""
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
            "audio_stream_wav": f"http://{local_ip}:{HTTP_PORT}/stream/audio?format=wav",
            "audio_stream_pcm": f"http://{local_ip}:{HTTP_PORT}/stream/audio?format=pcm",
            "audio_websocket": f"ws://{local_ip}:{HTTP_PORT}/ws/audio",
        },
        "api_endpoints": {
            "flash": f"http://{local_ip}:{HTTP_PORT}/api/flash",
            "quality": f"http://{local_ip}:{HTTP_PORT}/api/quality",
            "fps": f"http://{local_ip}:{HTTP_PORT}/api/fps",
            "audio": f"http://{local_ip}:{HTTP_PORT}/api/audio",
            "control": f"http://{local_ip}:{HTTP_PORT}/api/control",
        },
        "controls": hub.get_controls_dict(),
        "metrics": hub.get_stats(),
    }


# ---------------- Video Stream & Snapshot ---------------- #

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


# ---------------- Microphone Audio Stream ---------------- #

@app.get("/stream/audio")
async def get_audio_stream(format: str = Query("wav", description="Audio format: 'wav' (streamable RIFF) or 'pcm' (raw 16kHz 16-bit)")):
    """
    Live continuous audio stream from phone microphone.
    Supports ?format=wav (default, for VLC, browser, FFmpeg) or ?format=pcm (raw bytes).
    """
    media_type = "audio/wav" if format.lower() == "wav" else "audio/x-raw-pcm"
    return StreamingResponse(
        hub.generate_audio_stream(format_type=format),
        media_type=media_type
    )


@app.websocket("/ws/audio")
async def websocket_audio_endpoint(websocket: WebSocket):
    """
    Real-time binary audio WebSocket proxy for internal applications or web player.
    Delivers raw 16kHz 16-bit Mono PCM chunks as binary messages.
    """
    await websocket.accept()
    await hub.register_audio_proxy(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        hub.unregister_audio_proxy(websocket)
    except Exception:
        hub.unregister_audio_proxy(websocket)


# ---------------- Internal Hardware Control APIs ---------------- #

@app.get("/api/flash")
async def get_flash():
    """Returns current rear camera flash/torch state."""
    return {
        "status": "ok",
        "flash_enabled": hub.flash_enabled,
        "phone_connected": hub.phone_socket is not None,
    }


@app.post("/api/flash")
async def set_flash(
    request_data: Optional[FlashRequest] = Body(None),
    enabled: Optional[bool] = Query(None, description="Flash ON (true) or OFF (false)"),
    state: Optional[str] = Query(None, description="'on', 'off', 'true', or 'false'"),
):
    """
    Programmatic Internal API: Turn rear camera flash ON or OFF.
    Accepts JSON body: {"enabled": true}, Query param: ?enabled=true, or ?state=on.
    """
    target_state = False
    if request_data is not None:
        target_state = request_data.enabled
    elif enabled is not None:
        target_state = enabled
    elif state is not None:
        target_state = state.strip().lower() in ("on", "true", "1", "yes")
    else:
        # Toggle if no param given
        target_state = not hub.flash_enabled

    delivered = await hub.set_flash(target_state)
    return {
        "status": "ok",
        "flash_enabled": hub.flash_enabled,
        "phone_connected": hub.phone_socket is not None,
        "command_delivered": delivered,
        "message": f"Flash set to {'ON' if target_state else 'OFF'}",
    }


@app.get("/api/quality")
async def get_quality():
    """Returns current JPEG compression quality setting (10 - 100)."""
    return {
        "status": "ok",
        "quality": hub.jpeg_quality,
        "phone_connected": hub.phone_socket is not None,
    }


@app.post("/api/quality")
async def set_quality(
    request_data: Optional[QualityRequest] = Body(None),
    quality: Optional[int] = Query(None, ge=10, le=100, description="JPEG quality 10-100"),
):
    """
    Programmatic Internal API: Set hardware JPEG compression quality (10 - 100).
    Lower quality drastically reduces Wi-Fi transmission power and battery consumption.
    """
    target_quality = hub.jpeg_quality
    if request_data is not None:
        target_quality = request_data.quality
    elif quality is not None:
        target_quality = quality

    delivered = await hub.set_quality(target_quality)
    return {
        "status": "ok",
        "quality": hub.jpeg_quality,
        "phone_connected": hub.phone_socket is not None,
        "command_delivered": delivered,
        "message": f"Compression quality set to {hub.jpeg_quality}%",
    }


@app.get("/api/fps")
async def get_fps():
    """Returns current target framerate (FPS)."""
    return {
        "status": "ok",
        "fps": hub.target_fps,
        "phone_connected": hub.phone_socket is not None,
    }


@app.post("/api/fps")
async def set_fps(
    request_data: Optional[FpsRequest] = Body(None),
    fps: Optional[int] = Query(None, ge=1, le=60, description="Target framerate (1 - 60 FPS)"),
):
    """
    Programmatic Internal API: Set target framerate (1 - 60 FPS).
    Hardware-level throttling skips unnecessary frame encodings, saving maximum energy.
    """
    target_fps = hub.target_fps
    if request_data is not None:
        target_fps = request_data.fps
    elif fps is not None:
        target_fps = fps

    delivered = await hub.set_fps(target_fps)
    return {
        "status": "ok",
        "fps": hub.target_fps,
        "phone_connected": hub.phone_socket is not None,
        "command_delivered": delivered,
        "message": f"Target framerate set to {hub.target_fps} FPS",
    }


@app.get("/api/audio")
async def get_audio_status():
    """Returns current microphone transmission status and streaming metrics."""
    return {
        "status": "ok",
        "audio_enabled": hub.audio_enabled,
        "audio_metrics": hub.audio_stats.to_dict(),
        "phone_connected": hub.phone_socket is not None,
    }


@app.post("/api/audio")
async def set_audio(
    request_data: Optional[AudioRequest] = Body(None),
    enabled: Optional[bool] = Query(None, description="Audio enabled (true) or muted (false)"),
    state: Optional[str] = Query(None, description="'on', 'off', 'true', or 'false'"),
):
    """
    Programmatic Internal API: Enable or disable microphone audio streaming.
    Disabling completely suspends mobile microphone sampling to save battery.
    """
    target_state = True
    if request_data is not None:
        target_state = request_data.enabled
    elif enabled is not None:
        target_state = enabled
    elif state is not None:
        target_state = state.strip().lower() in ("on", "true", "1", "yes")
    else:
        target_state = not hub.audio_enabled

    delivered = await hub.set_audio(target_state)
    return {
        "status": "ok",
        "audio_enabled": hub.audio_enabled,
        "phone_connected": hub.phone_socket is not None,
        "command_delivered": delivered,
        "message": f"Microphone audio {'enabled' if target_state else 'muted/disabled'}",
    }


@app.get("/api/control")
@app.get("/api/settings")
async def get_all_controls():
    """Returns all current remote control settings."""
    return {
        "status": "ok",
        "controls": hub.get_controls_dict(),
    }


@app.post("/api/control")
@app.post("/api/settings")
async def update_all_controls(request_data: ControlRequest):
    """
    Unified Programmatic Internal API: Update multiple parameters in a single call.
    Accepts: {"flash": bool, "quality": int, "fps": int, "audio": bool}
    """
    results = {}
    if request_data.flash is not None:
        results["flash"] = await hub.set_flash(request_data.flash)
    if request_data.quality is not None:
        results["quality"] = await hub.set_quality(request_data.quality)
    if request_data.fps is not None:
        results["fps"] = await hub.set_fps(request_data.fps)
    if request_data.audio is not None:
        results["audio"] = await hub.set_audio(request_data.audio)

    return {
        "status": "ok",
        "updated_controls": hub.get_controls_dict(),
        "delivery_results": results,
    }


# ---------------- Ingestion WebSocket Endpoint ---------------- #

@app.websocket("/ws/phone")
async def websocket_phone_endpoint(websocket: WebSocket):
    """
    Incoming WebSocket channel from the mobile application.
    Accepts multiplexed video frames, audio PCM packets, and exchanges real-time control events.
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
                    p_type = payload.get("type")

                    if p_type in ("DEVICE_INFO", "STATE_UPDATE"):
                        if "flash_enabled" in payload:
                            hub.flash_enabled = bool(payload["flash_enabled"])
                        if "quality" in payload:
                            hub.jpeg_quality = int(payload["quality"])
                        if "fps" in payload:
                            hub.target_fps = int(payload["fps"])
                        if "audio_enabled" in payload:
                            hub.audio_enabled = bool(payload["audio_enabled"])
                        if "device_model" in payload:
                            hub.phone_info["device_model"] = payload["device_model"]
                        if "battery" in payload:
                            hub.phone_info["battery"] = payload["battery"]
                        if "flash_supported" in payload:
                            hub.phone_info["flash_supported"] = str(payload["flash_supported"])

                        await hub.broadcast_event({
                            "type": "PHONE_STATE_SYNC",
                            "phone_info": hub.phone_info,
                            "controls": hub.get_controls_dict(),
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
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        hub.unregister_proxy(websocket)
    except Exception:
        hub.unregister_proxy(websocket)
