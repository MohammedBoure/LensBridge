/**
 * Vision Core Live Dashboard Client
 * Low-latency dual camera WebSocket stream renderer.
 */

// DOM Elements
const rearCanvas = document.getElementById('rearCanvas');
const frontCanvas = document.getElementById('frontCanvas');
const rearCtx = rearCanvas.getContext('2d');
const frontCtx = frontCanvas.getContext('2d');

const rearOverlay = document.getElementById('rearOverlay');
const frontOverlay = document.getElementById('frontOverlay');

const serverIpDisplay = document.getElementById('serverIpDisplay');
const phoneStatusDisplay = document.getElementById('phoneStatusDisplay');
const phoneDot = document.getElementById('phoneDot');

const rearFps = document.getElementById('rearFps');
const frontFps = document.getElementById('frontFps');
const rearBitrate = document.getElementById('rearBitrate');
const frontBitrate = document.getElementById('frontBitrate');
const rearRes = document.getElementById('rearResolution');
const frontRes = document.getElementById('frontResolution');

const deviceModelText = document.getElementById('deviceModelText');
const totalFramesText = document.getElementById('totalFramesText');
const wsStateText = document.getElementById('wsStateText');
const viewport = document.getElementById('viewport');

let totalFrames = 0;
let ws = null;
let reconnectTimer = null;

// Telemetry calculation
const stats = {
  rear: { frames: 0, bytes: 0, lastCheck: performance.now(), fps: 0 },
  front: { frames: 0, bytes: 0, lastCheck: performance.now(), fps: 0 },
};

function initWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/client`;

  wsStateText.textContent = 'Connecting to Core...';
  ws = new WebSocket(wsUrl);
  ws.binaryType = 'arraybuffer';

  ws.onopen = () => {
    wsStateText.textContent = 'Active (Live Sync)';
    serverIpDisplay.textContent = window.location.hostname;
    if (reconnectTimer) {
      clearInterval(reconnectTimer);
      reconnectTimer = null;
    }
  };

  ws.onmessage = async (event) => {
    if (typeof event.data === 'string') {
      handleJsonMessage(JSON.parse(event.data));
    } else if (event.data instanceof ArrayBuffer) {
      handleBinaryFrame(event.data);
    }
  };

  ws.onclose = () => {
    wsStateText.textContent = 'Disconnected (Reconnecting...)';
    phoneDot.className = 'status-dot red';
    phoneStatusDisplay.textContent = 'Disconnected';
    if (!reconnectTimer) {
      reconnectTimer = setInterval(initWebSocket, 2000);
    }
  };

  ws.onerror = () => {
    ws.close();
  };
}

function handleJsonMessage(data) {
  if (data.type === 'INITIAL_STATE' || data.type === 'PHONE_CONNECTED' || data.type === 'DEVICE_INFO_UPDATED') {
    const info = data.phone_info || {};
    if (info.ip) {
      phoneDot.className = 'status-dot green';
      phoneStatusDisplay.textContent = `Connected (${info.ip})`;
      deviceModelText.textContent = `${info.device_model || 'Mobile Device'}`;
    } else {
      phoneDot.className = 'status-dot red';
      phoneStatusDisplay.textContent = 'Waiting for Mobile Wi-Fi Link...';
      deviceModelText.textContent = 'Not Connected';
    }
  } else if (data.type === 'PHONE_DISCONNECTED') {
    phoneDot.className = 'status-dot red';
    phoneStatusDisplay.textContent = 'Phone Disconnected';
    deviceModelText.textContent = 'Not Connected';
    rearOverlay.classList.remove('hidden');
    frontOverlay.classList.remove('hidden');
  }
}

async function handleBinaryFrame(arrayBuffer) {
  if (arrayBuffer.byteLength < 2) return;

  const view = new Uint8Array(arrayBuffer);
  const camCode = view[0]; // 0 = Rear, 1 = Front
  const isRear = camCode === 0;

  const jpegBytes = arrayBuffer.slice(1);
  const blob = new Blob([jpegBytes], { type: 'image/jpeg' });

  totalFrames++;
  totalFramesText.textContent = `${totalFrames} frames`;

  // Update telemetry
  const camStats = isRear ? stats.rear : stats.front;
  camStats.frames++;
  camStats.bytes += arrayBuffer.byteLength;

  try {
    const bitmap = await createImageBitmap(blob);
    const canvas = isRear ? rearCanvas : frontCanvas;
    const ctx = isRear ? rearCtx : frontCtx;
    const overlay = isRear ? rearOverlay : frontOverlay;
    const resElem = isRear ? rearRes : frontRes;

    if (canvas.width !== bitmap.width || canvas.height !== bitmap.height) {
      canvas.width = bitmap.width;
      canvas.height = bitmap.height;
      resElem.textContent = `${bitmap.width} x ${bitmap.height}`;
    }

    ctx.drawImage(bitmap, 0, 0);
    overlay.classList.add('hidden');
    bitmap.close();
  } catch (e) {
    console.error('Frame decode error:', e);
  }
}

// Periodic FPS & Bitrate calculation
setInterval(() => {
  const now = performance.now();
  ['rear', 'front'].forEach((cam) => {
    const s = stats[cam];
    const elapsed = (now - s.lastCheck) / 1000;
    if (elapsed > 0.5) {
      s.fps = (s.frames / elapsed).toFixed(1);
      const kbps = Math.round((s.bytes * 8) / (elapsed * 1000));
      s.frames = 0;
      s.bytes = 0;
      s.lastCheck = now;

      if (cam === 'rear') {
        rearFps.textContent = s.fps;
        rearBitrate.textContent = kbps;
      } else {
        frontFps.textContent = s.fps;
        frontBitrate.textContent = kbps;
      }
    }
  });
}, 1000);

// Viewport mode buttons
document.querySelectorAll('.btn-mode').forEach((btn) => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.btn-mode').forEach((b) => b.classList.remove('active'));
    btn.classList.add('active');
    const mode = btn.dataset.mode;
    viewport.className = `streams-viewport mode-${mode}`;
  });
});

// Snapshot action
function takeSnapshot(cam) {
  const canvas = cam === 'rear' ? rearCanvas : frontCanvas;
  if (!canvas.width || !canvas.height) return;

  const link = document.createElement('a');
  link.download = `vision_${cam}_${Date.now()}.jpg`;
  link.href = canvas.toDataURL('image/jpeg', 0.95);
  link.click();
}

// Fullscreen toggle
function toggleFullscreen(cardId) {
  const card = document.getElementById(cardId);
  if (!document.fullscreenElement) {
    card.requestFullscreen().catch((err) => console.log(err));
  } else {
    document.exitFullscreen();
  }
}

// Fetch initial status via REST API as fallback
fetch('/api/status')
  .then((r) => r.json())
  .then((data) => {
    if (data.local_ip) {
      serverIpDisplay.textContent = `${data.local_ip}:${data.http_port}`;
    }
  })
  .catch(() => {});

// Start WebSocket connection
initWebSocket();
