# Vision Desktop Server

This directory contains the desktop backend server, UDP auto-discovery responder, WebSocket video streaming hub, and hardware-accelerated desktop viewer.

## Files and Directory Structure

- **`config.py`**: Central configuration module defining default HTTP and UDP discovery ports, target framerates, JPEG quality, and local network IP resolution.
- **`discovery.py`**: Background UDP discovery service that periodically broadcasts beacon packets across the Wi-Fi subnet and answers probe requests from the mobile app so it connects automatically.
- **`stream_hub.py`**: Central WebSocket manager and telemetry engine that receives concurrent rear and front camera binary video frames from the phone and dispatches them to desktop viewers.
- **`app.py`**: FastAPI application exposing REST health/snapshot endpoints and WebSocket channels (`/ws/phone` and `/ws/client`).
- **`desktop_gui.py`**: Native Windows desktop GUI application built with PySide6, featuring side-by-side low-latency hardware-accelerated camera feeds, snapshot tools, and telemetry badges.
- **`main.py`**: Main orchestrator launching the discovery service, FastAPI backend, and desktop GUI in unison.
- **`requirements.txt`**: Python package dependencies.
- **`run_server.bat`**: Double-clickable Windows batch script to launch the server instantly.
- **`static/`**: Web-based live dashboard assets (HTML, CSS, JS) for browser-based viewing.
