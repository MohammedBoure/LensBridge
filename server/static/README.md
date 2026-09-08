# Vision Desktop Web Dashboard

This directory contains the front-end assets for the web-based live dual-camera monitoring dashboard.

## Files

- **`index.html`**: Responsive single-page interface with dual camera video canvases, mode switchers (Split, PiP, Fullscreen), telemetry badges, and snapshot triggers.
- **`style.css`**: Modern dark glassmorphism styling, cyberpunk accents, flexible responsive grid layout, and control button themes.
- **`app.js`**: Client-side JavaScript establishing a WebSocket link with the server, parsing binary frames from both front and rear cameras, rendering them using HTML5 Canvas, and calculating live FPS.
