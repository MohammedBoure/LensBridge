# Vision Desktop Server & Stream Proxy

This directory contains the desktop backend program, UDP auto-discovery responder, and reverse stream proxy engine designed to convert the mobile phone's **back (rear) camera stream** into standard formats for other internal applications.

## Key Capabilities

- **Back-Camera Stream Hub**: Ingests high-framerate JPEG frames exclusively from the phone's rear camera.
- **Reverse / Proxy Streaming**: Instantly converts the incoming mobile stream for external/internal programs:
  - **HTTP MJPEG Stream**: `http://<IP>:8765/stream/video` (also aliased at `/video_feed`). Universally compatible with OpenCV (`cv2.VideoCapture`), VLC, FFmpeg, and web browsers.
  - **Raw Binary WebSocket Proxy**: `ws://<IP>:8765/ws/proxy`. Zero-latency (<10ms) direct JPEG binary frame pipeline.
  - **REST Frame Snapshot**: `http://<IP>:8765/snapshot` (and `/snapshot.jpg`). Returns the latest frame as a JPEG response.
- **24/7 Always-On Reliability**: Runs continuously without stopping or crashing. Phone disconnections do not terminate the server or proxy listeners.
- **On-Demand Auto-Discovery**: Binds to UDP port `45454` with `SO_REUSEADDR` to respond instantaneously to discovery searches from the mobile phone whenever broadcast is initiated.

## Files and Directory Structure

- **`config.py`**: Central configuration defining HTTP port (`8765`), discovery port (`45454`), network IP resolver, and frame settings.
- **`discovery.py`**: UDP discovery responder and beacon broadcaster on port `45454`. Listens for `VISION_DISCOVER_PROBE` and announces server coordinates.
- **`stream_hub.py`**: Central proxy engine managing WebSocket ingestion, queue-based pub/sub MJPEG frame dispatch with dropped-frame protection, and client telemetry.
- **`app.py`**: FastAPI server exposing proxy endpoints (`/stream/video`, `/video_feed`, `/ws/proxy`, `/snapshot`, `/api/status`) and ingestion endpoint (`/ws/phone`).
- **`desktop_gui.py`**: Native Windows PySide6 desktop GUI displaying live back camera video feed, copyable proxy stream URLs, snapshot tools, and sample OpenCV integration code.
- **`main.py`**: Orchestrator launching UDP discovery, Uvicorn backend, and desktop GUI in unison.
- **`requirements.txt`**: Python dependencies (`fastapi`, `uvicorn`, `PySide6`, `websocket-client`, `Pillow`).
- **`run_server.bat`**: Double-clickable Windows batch launcher.
- **`static/`**: Web-based live dashboard assets (`index.html`, `style.css`, `app.js`).

## Internal Program Integration Example (Python OpenCV)

```python
import cv2

# Connect to Vision proxy MJPEG stream
cap = cv2.VideoCapture("http://127.0.0.1:8765/stream/video")

while True:
    ret, frame = cap.read()
    if not ret:
        continue
    
    # Process frame with OpenCV / AI models
    cv2.imshow("Phone Back Camera Stream", frame)
    if cv2.waitKey(1) == 27: # ESC
        break

cap.release()
cv2.destroyAllWindows()
```
