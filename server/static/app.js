/**
 * Vision Core Live Dashboard & Proxy Client
 * Receives the back-camera video and microphone audio stream,
 * provides copyable proxy endpoints, and programmatic hardware controls.
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
const audioStatBadge = document.getElementById('audioStatBadge');

// Control elements
const flashBtn = document.getElementById('flashBtn');
const flashBtnText = document.getElementById('flashBtnText');
const audioBtn = document.getElementById('audioBtn');
const audioBtnText = document.getElementById('audioBtnText');
const fpsSelect = document.getElementById('fpsSelect');
const qualitySlider = document.getElementById('qualitySlider');
const qualityVal = document.getElementById('qualityVal');

const mjpegInput = document.getElementById('mjpegUrl');
const audioInput = document.getElementById('audioUrl');
const wsInput = document.getElementById('wsUrl');
const snapInput = document.getElementById('snapUrl');
const browserAudioPlayer = document.getElementById('browserAudioPlayer');
const listenAudioBtn = document.getElementById('listenAudioBtn');
const listenAudioText = document.getElementById('listenAudioText');

let totalFrames = 0;
let ws = null;
let reconnectTimer = null;

// Telemetry
let frameCount = 0;
let byteCount = 0;
let lastCheck = performance.now();

// State
let isFlashOn = false;
let isAudioOn = true;
let isPlayingAudio = false;

// Auth Token resolution (URL query param or localStorage)
const urlParams = new URLSearchParams(window.location.search);
let authToken = urlParams.get('token') || urlParams.get('api_key') || localStorage.getItem('lb_auth_token') || '';
if (urlParams.get('token')) {
  localStorage.setItem('lb_auth_token', urlParams.get('token'));
}

function getAuthQueryString() {
  return authToken ? `token=${encodeURIComponent(authToken)}` : '';
}

function apiFetch(endpoint, options = {}) {
  const headers = options.headers || {};
  if (authToken) {
    headers['X-API-Key'] = authToken;
  }
  return fetch(endpoint, { ...options, headers });
}

function populateUrls() {
  const host = window.location.host;
  const protocol = window.location.protocol;
  const wsProtocol = protocol === 'https:' ? 'wss:' : 'ws:';
  const query = getAuthQueryString() ? `?${getAuthQueryString()}` : '';

  const mjpeg = `${protocol}//${host}/stream/video${query}`;
  const audio = `${protocol}//${host}/stream/audio${query}`;
  const wsProxy = `${wsProtocol}//${host}/ws/proxy${query}`;
  const snap = `${protocol}//${host}/snapshot${query}`;

  mjpegInput.value = mjpeg;
  if (audioInput) audioInput.value = audio;
  wsInput.value = wsProxy;
  snapInput.value = snap;
  serverIpDisplay.textContent = host;
}

function initWebSocket() {
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const query = getAuthQueryString() ? `?${getAuthQueryString()}` : '';
  const url = `${wsProtocol}//${window.location.host}/ws/proxy${query}`;

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
  if (data.type === 'PHONE_CONNECTED' || data.type === 'DEVICE_INFO_UPDATED' || data.type === 'PHONE_STATE_SYNC') {
    const info = data.phone_info || {};
    phoneDot.className = 'status-dot green';
    phoneStatusDisplay.textContent = `Connected (${info.ip || 'Wi-Fi'})`;
    deviceModelText.textContent = `${info.device_model || 'Mobile Device'}`;

    if (data.controls) {
      syncControlsUI(data.controls);
    }
  } else if (data.type === 'PHONE_DISCONNECTED') {
    phoneDot.className = 'status-dot red';
    phoneStatusDisplay.textContent = 'Phone Disconnected';
    deviceModelText.textContent = 'Waiting...';
    overlay.classList.remove('hidden');
    fpsText.textContent = '0.0';
  } else if (data.type === 'CONTROL_UPDATED') {
    if (data.control === 'flash') updateFlashUI(data.enabled);
    if (data.control === 'audio') updateAudioUI(data.enabled);
    if (data.control === 'quality') updateQualityUI(data.quality);
    if (data.control === 'fps') updateFpsUI(data.fps);
  }
}

function syncControlsUI(controls) {
  if (controls.flash_enabled !== undefined) updateFlashUI(controls.flash_enabled);
  if (controls.audio_enabled !== undefined) updateAudioUI(controls.audio_enabled);
  if (controls.quality !== undefined) updateQualityUI(controls.quality);
  if (controls.fps !== undefined) updateFpsUI(controls.fps);
}

function updateFlashUI(enabled) {
  isFlashOn = Boolean(enabled);
  if (isFlashOn) {
    flashBtn.classList.add('flash-on');
    flashBtnText.textContent = 'Flash: ON';
  } else {
    flashBtn.classList.remove('flash-on');
    flashBtnText.textContent = 'Flash: OFF';
  }
}

function updateAudioUI(enabled) {
  isAudioOn = Boolean(enabled);
  if (isAudioOn) {
    audioBtn.className = 'btn-control btn-audio-active';
    audioBtnText.textContent = 'Microphone: ON';
    audioStatBadge.textContent = '🎤 Audio: Active';
    audioStatBadge.style.color = 'var(--accent-cyan)';
  } else {
    audioBtn.className = 'btn-control btn-audio-muted';
    audioBtnText.textContent = 'Microphone: MUTED';
    audioStatBadge.textContent = '🎤 Audio: Muted';
    audioStatBadge.style.color = '#ef4444';
  }
}

function updateQualityUI(quality) {
  qualitySlider.value = quality;
  qualityVal.textContent = `${quality}%`;
}

function updateFpsUI(fps) {
  fpsSelect.value = String(fps);
}

// ---------------- Remote Control Actions ---------------- //

async function toggleFlash() {
  const next = !isFlashOn;
  updateFlashUI(next);
  try {
    await apiFetch('/api/flash', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: next }),
    });
  } catch (e) {
    console.error('Failed toggling flash:', e);
  }
}

async function toggleAudio() {
  const next = !isAudioOn;
  updateAudioUI(next);
  try {
    await apiFetch('/api/audio', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: next }),
    });
  } catch (e) {
    console.error('Failed toggling audio:', e);
  }
}

async function changeFps(val) {
  try {
    await apiFetch('/api/fps', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fps: parseInt(val, 10) }),
    });
  } catch (e) {
    console.error('Failed setting FPS:', e);
  }
}

async function changeQuality(val) {
  try {
    await apiFetch('/api/quality', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ quality: parseInt(val, 10) }),
    });
  } catch (e) {
    console.error('Failed setting quality:', e);
  }
}

function toggleBrowserAudioPlayback() {
  if (!isPlayingAudio) {
    const tokenParam = authToken ? `&token=${encodeURIComponent(authToken)}` : '';
    browserAudioPlayer.src = `/stream/audio?format=wav&t=${Date.now()}${tokenParam}`;
    browserAudioPlayer.play().then(() => {
      isPlayingAudio = true;
      listenAudioText.textContent = 'Mute Browser Audio';
      listenAudioBtn.style.background = '#065f46';
    }).catch((err) => {
      console.warn('Audio play request failed:', err);
    });
  } else {
    browserAudioPlayer.pause();
    browserAudioPlayer.src = '';
    isPlayingAudio = false;
    listenAudioText.textContent = 'Listen in Browser';
    listenAudioBtn.style.background = '';
  }
}

// ---------------- Video Processing ---------------- //

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
