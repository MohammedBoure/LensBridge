# Vision Desktop Web Dashboard

This directory contains the front-end assets for the web-based live monitoring dashboard, remote hardware controls, and browser audio player.

## Files

- **`index.html`**: Responsive single-page interface with back camera video canvas, hardware control buttons (Flash ON/OFF, Microphone Audio ON/Muted, Target FPS selector, JPEG Quality slider), in-browser audio playback, telemetry badges, copyable proxy endpoints, and snapshot triggers.
- **`style.css`**: Modern dark glassmorphism styling, control panel button themes, responsive grid layout, and real-time status indicators.
- **`app.js`**: Client-side JavaScript establishing a WebSocket link with the server, parsing binary video frames, rendering them using HTML5 Canvas, calculating live FPS, dispatching remote control API calls, and streaming microphone audio to browser speakers.
