/**
 * Vision Core Live Dashboard & Proxy Client
 * Receives the back-camera feed and displays copyable stream endpoints.
 */

const videoCanvas = document.getElementById('videoCanvas');
const ctx = videoCanvas.getContext('2d');
const overlay = document.getElementById('overlay');

const serverIpDisplay = document.getElementById('serverIpDisplay');
const phoneStatusDisplay = document.getElementById('phoneStatusDisplay');
const phoneDot = document.getElementById('phoneDot');

const fpsText = document.getElementById('fpsText');
const bitrateText = document.getElementById('bitrateText');
const resText = document.getElementById('resolutionText');
const deviceModelText = document.getElementById('deviceModelText');
const totalFramesText = document.getElementById('totalFramesText');

const mjpegInput = document.getElementById('mjpegUrl');
const wsInput = document.getElementById('wsUrl');
const snapInput = document.getElementById('snapUrl');
const codeMjpegUrl = document.getElementById('codeMjpegUrl');

let totalFrames = 0;
let ws = null;
let reconnectTimer = null;

// Telemetry
let frameCount = 0;
let byteCount = 0;
let lastCheck = performance.now();

function populateUrls() {
  const host = window.location.host;
  const protocol = window.location.protocol;
  const wsProtocol = protocol === 'https:' ? 'wss:' : 'ws:';

  const mjpeg = `${protocol}//${host}/stream/video`;
  const wsProxy = `${wsProtocol}//${host}/ws/proxy`;
  const snap = `${protocol}//${host}/snapshot`;

  mjpegInput.value = mjpeg;
  wsInput.value = wsProxy;
  snapInput.value = snap;
  if (codeMjpegUrl) codeMjpegUrl.textContent = mjpeg;
  serverIpDisplay.textContent = host;
}

function initWebSocket() {
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const url = `${wsProtocol}//${window.location.host}/ws/proxy`;

  ws = new WebSocket(url);
  ws.binaryType = 'arraybuffer';

  ws.onopen = () => {
    if (reconnectTimer) {
      clearInterval(reconnectTimer);
      reconnectTimer = null;
    }
  };

  ws.onmessage = async (event) => {
    if (typeof event.data === 'string') {
      try {
        const data = JSON.parse(event.data);
        handleControlMessage(data);
      } catch (_) {}
    } else if (event.data instanceof ArrayBuffer) {
      handleBinaryFrame(event.data);
    }
  };

  ws.onclose = () => {
    phoneDot.className = 'status-dot red';
    phoneStatusDisplay.textContent = 'Disconnected (Waiting...)';
    if (!reconnectTimer) {
      reconnectTimer = setInterval(initWebSocket, 2000);
    }
  };

  ws.onerror = () => {
    ws.close();
  };
}

function handleControlMessage(data) {
  if (data.type === 'PHONE_CONNECTED' || data.type === 'DEVICE_INFO_UPDATED') {
    const info = data.phone_info || {};
    phoneDot.className = 'status-dot green';
    phoneStatusDisplay.textContent = `Connected (${info.ip || 'Wi-Fi'})`;
    deviceModelText.textContent = `${info.device_model || 'Mobile Device'}`;
  } else if (data.type === 'PHONE_DISCONNECTED') {
    phoneDot.className = 'status-dot red';
    phoneStatusDisplay.textContent = 'Phone Disconnected';
    deviceModelText.textContent = 'Waiting...';
    overlay.classList.remove('hidden');
    fpsText.textContent = '0.0';
  }
}

async function handleBinaryFrame(arrayBuffer) {
  if (arrayBuffer.byteLength < 4) return;

  totalFrames++;
  totalFramesText.textContent = `${totalFrames} frames`;

  frameCount++;
  byteCount += arrayBuffer.byteLength;

  const blob = new Blob([arrayBuffer], { type: 'image/jpeg' });
  try {
    const bitmap = await createImageBitmap(blob);
    if (videoCanvas.width !== bitmap.width || videoCanvas.height !== bitmap.height) {
      videoCanvas.width = bitmap.width;
      videoCanvas.height = bitmap.height;
      resText.textContent = `${bitmap.width} x ${bitmap.height}`;
    }

    ctx.drawImage(bitmap, 0, 0);
    overlay.classList.add('hidden');
    bitmap.close();

    // Mark phone connected on receiving active frames
    phoneDot.className = 'status-dot green';
    phoneStatusDisplay.textContent = 'Live Streaming';
  } catch (e) {
    console.error('Frame decode error:', e);
  }
}

// FPS calculation
setInterval(() => {
  const now = performance.now();
  const elapsed = (now - lastCheck) / 1000;
  if (elapsed >= 1.0) {
    const fps = (frameCount / elapsed).toFixed(1);
    const kbps = Math.round((byteCount * 8) / (elapsed * 1000));
    fpsText.textContent = fps;
    bitrateText.textContent = kbps;
    frameCount = 0;
    byteCount = 0;
    lastCheck = now;
  }
}, 1000);

function copyToClipboard(elementId) {
  const input = document.getElementById(elementId);
  if (!input) return;
  input.select();
  navigator.clipboard.writeText(input.value).then(() => {
    const originalText = input.nextElementSibling.textContent;
    input.nextElementSibling.textContent = 'Copied!';
    setTimeout(() => {
      input.nextElementSibling.textContent = originalText;
    }, 1500);
  });
}

function takeSnapshot() {
  if (!videoCanvas.width || !videoCanvas.height) return;
  const link = document.createElement('a');
  link.download = `back_camera_${Date.now()}.jpg`;
  link.href = videoCanvas.toDataURL('image/jpeg', 0.95);
  link.click();
}

function toggleFullscreen() {
  if (!document.fullscreenElement) {
    videoCanvas.requestFullscreen().catch(() => {});
  } else {
    document.exitFullscreen();
  }
}

// Initialize
populateUrls();
initWebSocket();
