"""FastAPI application for Vision Desktop Server & Stream Proxy.

Provides HTTP MJPEG video stream, raw WebSocket proxy, snapshot API,
live audio stream (/stream/audio), audio WebSocket proxy (/ws/audio),
and an internal REST API for programmatic hardware control:
- Flashlight / Torch: Turn ON / OFF (/api/flash)
- JPEG Quality: Set 10-100 (/api/quality)
- Number of Frames: Set Target FPS (/api/fps)
- Microphone Audio: Enable / Disable (/api/audio)
- Unified Control: Batch update (/api/control, /api/settings)
- Multi-Device Broadcaster Management (/api/devices)
- Granular Internal API Permissions & Token Management (/api/auth)
"""

import json
import os
from typing import Optional, List
from pydantic import BaseModel, Field
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response, Query, Body, Depends, status, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from config import HTTP_PORT, get_local_ip
from stream_hub import hub
from auth import (
    PermissionScope,
    ROLE_DEFINITIONS,
    TokenCreateRequest,
    TokenData,
    auth_manager,
    check_websocket_permission,
    require_permission,
)

app = FastAPI(
    title="Vision Back-Camera Stream & Audio Proxy",
    description="High-performance video & microphone audio proxy with internal REST API for remote hardware control and permissions.",
    version="2.2.0",
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


class SelectDeviceRequest(BaseModel):
    session_id: str = Field(..., description="Target broadcaster session ID to activate")


class AuthConfigUpdate(BaseModel):
    auth_enabled: Optional[bool] = Field(None, description="Enable or disable API permissions enforcement")
    allow_local_loopback_bypass: Optional[bool] = Field(None, description="Allow unauthenticated access for localhost calls")


# ---------------- Web & Status Endpoints ---------------- #

@app.get("/", response_class=HTMLResponse)
async def get_index():
    """Serves the main desktop live viewer and proxy control dashboard."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h1>Vision Server Running. Proxy & Internal API active.</h1>")


@app.get("/api/status")
async def get_status(caller: TokenData = Depends(require_permission(PermissionScope.STATUS_READ))):
    """Returns current server status, proxy stream URLs, internal API endpoints, and telemetry."""
    local_ip = get_local_ip()
    return {
        "status": "online",
        "local_ip": local_ip,
        "http_port": HTTP_PORT,
        "auth_enabled": auth_manager.auth_enabled,
        "caller": {
            "token_id": caller.id,
            "name": caller.name,
            "role": caller.role,
        },
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
            "devices": f"http://{local_ip}:{HTTP_PORT}/api/devices",
            "auth_permissions": f"http://{local_ip}:{HTTP_PORT}/api/auth/permissions",
            "auth_tokens": f"http://{local_ip}:{HTTP_PORT}/api/auth/tokens",
        },
        "controls": hub.get_controls_dict(),
        "metrics": hub.get_stats(),
    }


# ---------------- Video Stream & Snapshot ---------------- #

@app.get("/stream/video")
@app.get("/video_feed")
async def get_video_stream(caller: TokenData = Depends(require_permission(PermissionScope.STREAM_VIDEO))):
    """
    Universal HTTP multipart/x-mixed-replace MJPEG video stream.
    Directly consumable by OpenCV (cv2.VideoCapture), VLC, FFmpeg, and web browsers.
    Requires 'stream:video' permission.
    """
    return StreamingResponse(
        hub.generate_mjpeg_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.get("/snapshot")
@app.get("/snapshot.jpg")
async def get_latest_snapshot(caller: TokenData = Depends(require_permission(PermissionScope.STREAM_VIDEO))):
    """Returns the latest captured JPEG frame from the active camera or standby image if not yet connected."""
    frame = hub.latest_frame if hub.latest_frame else hub.get_standby_frame()
    return Response(
        content=frame,
        media_type="image/jpeg",
        headers={"X-Stream-Active": "true" if hub.latest_frame else "false"}
    )


# ---------------- Microphone Audio Stream ---------------- #

@app.get("/stream/audio")
async def get_audio_stream(
    format: str = Query("wav", description="Audio format: 'wav' (streamable RIFF) or 'pcm' (raw 16kHz 16-bit)"),
    caller: TokenData = Depends(require_permission(PermissionScope.STREAM_AUDIO)),
):
    """
    Live continuous audio stream from phone microphone.
    Supports ?format=wav (default, for VLC, browser, FFmpeg) or ?format=pcm (raw bytes).
    Requires 'stream:audio' permission.
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
    Requires 'stream:audio' permission.
    """
    token_data = check_websocket_permission(websocket, PermissionScope.STREAM_AUDIO)
    if not token_data:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized: requires 'stream:audio' permission")
        return

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
async def get_flash(caller: TokenData = Depends(require_permission(PermissionScope.STATUS_READ))):
    """Returns current rear camera flash/torch state."""
    return {
        "status": "ok",
        "flash_enabled": hub.flash_enabled,
        "phone_connected": bool(hub.sources),
        "active_source_id": hub.active_source_id,
    }


@app.post("/api/flash")
async def set_flash(
    request_data: Optional[FlashRequest] = Body(None),
    enabled: Optional[bool] = Query(None, description="Flash ON (true) or OFF (false)"),
    state: Optional[str] = Query(None, description="'on', 'off', 'true', or 'false'"),
    session_id: Optional[str] = Query(None, description="Target specific phone session ID"),
    caller: TokenData = Depends(require_permission(PermissionScope.CONTROL_FLASH)),
):
    """
    Programmatic Internal API: Turn rear camera flash ON or OFF.
    Accepts JSON body: {"enabled": true}, Query param: ?enabled=true, or ?state=on.
    Requires 'control:flash' permission.
    """
    target_state = False
    if request_data is not None:
        target_state = request_data.enabled
    elif enabled is not None:
        target_state = enabled
    elif state is not None:
        target_state = state.strip().lower() in ("on", "true", "1", "yes")
    else:
        target_state = not hub.flash_enabled

    delivered = await hub.set_flash(target_state, target_session_id=session_id)
    return {
        "status": "ok",
        "flash_enabled": hub.flash_enabled,
        "phone_connected": bool(hub.sources),
        "active_source_id": hub.active_source_id,
        "command_delivered": delivered,
        "message": f"Flash set to {'ON' if target_state else 'OFF'}",
    }


@app.get("/api/quality")
async def get_quality(caller: TokenData = Depends(require_permission(PermissionScope.STATUS_READ))):
    """Returns current JPEG compression quality setting (10 - 100)."""
    return {
        "status": "ok",
        "quality": hub.jpeg_quality,
        "phone_connected": bool(hub.sources),
        "active_source_id": hub.active_source_id,
    }


@app.post("/api/quality")
async def set_quality(
    request_data: Optional[QualityRequest] = Body(None),
    quality: Optional[int] = Query(None, ge=10, le=100, description="JPEG quality 10-100"),
    session_id: Optional[str] = Query(None, description="Target specific phone session ID"),
    caller: TokenData = Depends(require_permission(PermissionScope.CONTROL_QUALITY)),
):
    """
    Programmatic Internal API: Set hardware JPEG compression quality (10 - 100).
    Lower quality drastically reduces Wi-Fi transmission power and battery consumption.
    Requires 'control:quality' permission.
    """
    target_quality = hub.jpeg_quality
    if request_data is not None:
        target_quality = request_data.quality
    elif quality is not None:
        target_quality = quality

    delivered = await hub.set_quality(target_quality, target_session_id=session_id)
    return {
        "status": "ok",
        "quality": hub.jpeg_quality,
        "phone_connected": bool(hub.sources),
        "active_source_id": hub.active_source_id,
        "command_delivered": delivered,
        "message": f"Compression quality set to {hub.jpeg_quality}%",
    }


@app.get("/api/fps")
async def get_fps(caller: TokenData = Depends(require_permission(PermissionScope.STATUS_READ))):
    """Returns current target framerate (FPS)."""
    return {
        "status": "ok",
        "fps": hub.target_fps,
        "phone_connected": bool(hub.sources),
        "active_source_id": hub.active_source_id,
    }


@app.post("/api/fps")
async def set_fps(
    request_data: Optional[FpsRequest] = Body(None),
    fps: Optional[int] = Query(None, ge=1, le=60, description="Target framerate (1 - 60 FPS)"),
    session_id: Optional[str] = Query(None, description="Target specific phone session ID"),
    caller: TokenData = Depends(require_permission(PermissionScope.CONTROL_FPS)),
):
    """
    Programmatic Internal API: Set target framerate (1 - 60 FPS).
    Hardware-level throttling skips unnecessary frame encodings, saving maximum energy.
    Requires 'control:fps' permission.
    """
    target_fps = hub.target_fps
    if request_data is not None:
        target_fps = request_data.fps
    elif fps is not None:
        target_fps = fps

    delivered = await hub.set_fps(target_fps, target_session_id=session_id)
    return {
        "status": "ok",
        "fps": hub.target_fps,
        "phone_connected": bool(hub.sources),
        "active_source_id": hub.active_source_id,
        "command_delivered": delivered,
        "message": f"Target framerate set to {hub.target_fps} FPS",
    }


@app.get("/api/audio")
async def get_audio_status(caller: TokenData = Depends(require_permission(PermissionScope.STATUS_READ))):
    """Returns current microphone transmission status and streaming metrics."""
    return {
        "status": "ok",
        "audio_enabled": hub.audio_enabled,
        "audio_metrics": hub.audio_stats.to_dict(),
        "phone_connected": bool(hub.sources),
        "active_source_id": hub.active_source_id,
    }


@app.post("/api/audio")
async def set_audio(
    request_data: Optional[AudioRequest] = Body(None),
    enabled: Optional[bool] = Query(None, description="Audio enabled (true) or muted (false)"),
    state: Optional[str] = Query(None, description="'on', 'off', 'true', or 'false'"),
    session_id: Optional[str] = Query(None, description="Target specific phone session ID"),
    caller: TokenData = Depends(require_permission(PermissionScope.CONTROL_AUDIO)),
):
    """
    Programmatic Internal API: Enable or disable microphone audio streaming.
    Disabling completely suspends mobile microphone sampling to save battery.
    Requires 'control:audio' permission.
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

    delivered = await hub.set_audio(target_state, target_session_id=session_id)
    return {
        "status": "ok",
        "audio_enabled": hub.audio_enabled,
        "phone_connected": bool(hub.sources),
        "active_source_id": hub.active_source_id,
        "command_delivered": delivered,
        "message": f"Microphone audio {'enabled' if target_state else 'muted/disabled'}",
    }


@app.get("/api/control")
@app.get("/api/settings")
async def get_all_controls(caller: TokenData = Depends(require_permission(PermissionScope.STATUS_READ))):
    """Returns all current remote control settings."""
    return {
        "status": "ok",
        "controls": hub.get_controls_dict(),
    }


@app.post("/api/control")
@app.post("/api/settings")
async def update_all_controls(
    request_data: ControlRequest,
    caller: TokenData = Depends(require_permission(PermissionScope.CONTROL_ALL)),
):
    """
    Unified Programmatic Internal API: Update multiple parameters in a single call.
    Accepts: {"flash": bool, "quality": int, "fps": int, "audio": bool}
    Requires 'control:*' or 'admin' permission.
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


# ---------------- Multi-Device Broadcaster Management ---------------- #

@app.get("/api/devices")
async def get_connected_devices(caller: TokenData = Depends(require_permission(PermissionScope.STATUS_READ))):
    """
    Lists all connected broadcasting mobile devices, their status, uptimes, and frame metrics.
    Requires 'status:read' permission.
    """
    device_list = [s.to_dict() for s in hub.sources.values()]
    return {
        "status": "ok",
        "active_source_id": hub.active_source_id,
        "devices_count": len(hub.sources),
        "total_sources": len(hub.sources),
        "devices": device_list,
        "sources": device_list,
        "total_connections": hub.total_connections_count,
        "total_disconnections": hub.total_disconnections_count,
    }


@app.post("/api/devices/select")
async def select_active_device(
    request_data: SelectDeviceRequest,
    caller: TokenData = Depends(require_permission(PermissionScope.CONTROL_ALL)),
):
    """
    Switches the active primary broadcasting device to the specified session ID.
    Requires 'control:*' or 'admin' permission.
    """
    success = await hub.set_active_source(request_data.session_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": "error", "message": f"Device session '{request_data.session_id}' not found."},
        )
    return {
        "status": "ok",
        "message": f"Active broadcaster switched to session '{request_data.session_id}'.",
        "active_source_id": hub.active_source_id,
    }


# ---------------- Granular Permissions & Token Management APIs ---------------- #

@app.get("/api/auth/permissions")
async def get_permissions_info():
    """Returns available permission scopes and pre-defined role bundles (public metadata)."""
    return {
        "status": "ok",
        "auth_enabled": auth_manager.auth_enabled,
        "allow_local_loopback_bypass": auth_manager.allow_local_loopback_bypass,
        "available_scopes": PermissionScope.all_scopes(),
        "predefined_roles": ROLE_DEFINITIONS,
    }


@app.get("/api/auth/me")
async def get_caller_auth(caller: TokenData = Depends(require_permission(PermissionScope.STATUS_READ))):
    """Validates the caller's token and returns granted permissions."""
    return {
        "status": "ok",
        "token_id": caller.id,
        "name": caller.name,
        "role": caller.role,
        "permissions": caller.permissions,
        "created_at": caller.created_at,
    }


@app.get("/api/auth/tokens")
async def list_tokens(caller: TokenData = Depends(require_permission(PermissionScope.ADMIN))):
    """Lists all configured API tokens with masked secrets. Requires 'admin' permission."""
    return {
        "status": "ok",
        "tokens": auth_manager.list_tokens(),
    }


@app.post("/api/auth/tokens")
async def create_token(
    request_data: TokenCreateRequest,
    caller: TokenData = Depends(require_permission(PermissionScope.ADMIN)),
):
    """Issues a new permission token. Requires 'admin' permission."""
    new_token = auth_manager.create_token(
        name=request_data.name,
        role=request_data.role or "custom",
        permissions=request_data.permissions,
        description=request_data.description or "",
    )
    return {
        "status": "ok",
        "message": "Token created successfully. Store this token securely; it cannot be retrieved again in plaintext.",
        "token": new_token.token,
        "id": new_token.id,
        "name": new_token.name,
        "role": new_token.role,
        "permissions": new_token.permissions,
    }


@app.delete("/api/auth/tokens/{identifier}")
async def revoke_token(
    identifier: str,
    caller: TokenData = Depends(require_permission(PermissionScope.ADMIN)),
):
    """Revokes an API token by secret or ID. Requires 'admin' permission."""
    revoked = auth_manager.revoke_token(identifier)
    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": "error", "message": f"Token identifier '{identifier}' not found."},
        )
    return {
        "status": "ok",
        "message": f"Token '{identifier}' revoked successfully.",
    }


@app.post("/api/auth/config")
async def update_auth_config(
    request_data: AuthConfigUpdate,
    caller: TokenData = Depends(require_permission(PermissionScope.ADMIN)),
):
    """Updates API authentication enforcement settings. Requires 'admin' permission."""
    if request_data.auth_enabled is not None:
        auth_manager.auth_enabled = request_data.auth_enabled
    if request_data.allow_local_loopback_bypass is not None:
        auth_manager.allow_local_loopback_bypass = request_data.allow_local_loopback_bypass
    auth_manager.save()
    return {
        "status": "ok",
        "auth_enabled": auth_manager.auth_enabled,
        "allow_local_loopback_bypass": auth_manager.allow_local_loopback_bypass,
    }


# ---------------- Ingestion WebSocket Endpoint ---------------- #

@app.websocket("/ws/phone")
async def websocket_phone_endpoint(websocket: WebSocket):
    """
    Incoming WebSocket channel from mobile broadcast clients.
    Session-aware and disconnect-resilient:
    - Multiple connections are registered independently with unique session IDs.
    - Stale connections terminating do NOT disconnect new active connections.
    - Reconnection cycles fail over and recover seamlessly without dropping subscribers.
    """
    await websocket.accept()
    device = websocket.query_params.get("device", "Mobile Phone")
    client_ip = websocket.client.host if websocket.client else "Unknown"
    session_id = await hub.register_phone(websocket, client_ip, device)

    try:
        while True:
            message = await websocket.receive()
            if "bytes" in message and message["bytes"]:
                await hub.handle_incoming_frame(message["bytes"], session_id=session_id)
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

                        source = hub.sources.get(session_id)
                        if source:
                            if "device_model" in payload:
                                source.device_info["device_model"] = payload["device_model"]
                            if "battery" in payload:
                                source.device_info["battery"] = payload["battery"]
                            if "flash_supported" in payload:
                                source.device_info["flash_supported"] = str(payload["flash_supported"])

                        if session_id == hub.active_source_id:
                            if "device_model" in payload:
                                hub.phone_info["device_model"] = payload["device_model"]
                            if "battery" in payload:
                                hub.phone_info["battery"] = payload["battery"]
                            if "flash_supported" in payload:
                                hub.phone_info["flash_supported"] = str(payload["flash_supported"])

                        await hub.broadcast_event({
                            "type": "PHONE_STATE_SYNC",
                            "session_id": session_id,
                            "phone_info": hub.phone_info,
                            "controls": hub.get_controls_dict(),
                        })
                except Exception:
                    pass
    except WebSocketDisconnect:
        await hub.unregister_phone(session_id)
    except Exception as e:
        print(f"[Phone Stream Disconnect] {session_id}: {e}")
        await hub.unregister_phone(session_id)


@app.websocket("/ws/proxy")
async def websocket_proxy_endpoint(websocket: WebSocket):
    """
    Proxy WebSocket channel for internal applications.
    Broadcasts raw JPEG binary frames directly with sub-10ms latency.
    Requires 'stream:video' permission.
    """
    token_data = check_websocket_permission(websocket, PermissionScope.STREAM_VIDEO)
    if not token_data:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized: requires 'stream:video' permission")
        return

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

