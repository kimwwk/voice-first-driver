'use strict';

/* ===== SPEECH RECOGNITION COMPAT ===== */
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

/* ===== QUICK MODE STATE (Web Speech API) ===== */
let recognition       = null;
let isListening       = false;
let quickFinalTranscript = '';
let silenceTimer      = null;
const SILENCE_DELAY   = 3500;

/* ===== WAKE WORD / HANDS-FREE STATE ===== */
let wakeEngine        = null;
let wakeEngineReady   = false;
let wakeEngineLoading = false;
let wakeWordListening = false;
let handsFreeEnabled  = false;

/* ===== PROCESSING STATE ===== */
let isProcessing = false;

/* ===== DOM REFS ===== */
const chatEl          = document.getElementById('chat');
const chatEmpty       = document.getElementById('chat-empty');
const liveTranscript  = document.getElementById('live-transcript');
const liveText        = document.getElementById('live-text');
const textInput       = document.getElementById('text-input');
const sendBtn         = document.getElementById('send-btn');
const micBtn          = document.getElementById('mic-btn');
const settingsBtn     = document.getElementById('settings-btn');
const modalOverlay    = document.getElementById('modal-overlay');
const modalClose      = document.getElementById('modal-close');
const langSelect      = document.getElementById('lang-select');
const handsFreeToggle = document.getElementById('hands-free-toggle');
const agentUrlInput   = document.getElementById('agent-url');
const saveSettingsBtn = document.getElementById('save-settings');
const wakeDot         = document.getElementById('wake-dot');
const notSupported    = document.getElementById('not-supported');

/* ===== UTILITY ===== */
function escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function getRecognitionLang() {
  return localStorage.getItem('recognitionLang') || '';
}

/* ===== CHAT UI ===== */

function addChatMessage(text, role) {
  // Hide empty state
  if (chatEmpty) chatEmpty.hidden = true;

  const msg = document.createElement('div');
  msg.className = `chat-msg ${role}`;
  msg.textContent = text;
  chatEl.appendChild(msg);
  chatEl.scrollTop = chatEl.scrollHeight;
}

function addThinkingIndicator() {
  const el = document.createElement('div');
  el.className = 'thinking';
  el.id = 'thinking-indicator';
  el.innerHTML = '<span class="thinking-dot"></span><span class="thinking-dot"></span><span class="thinking-dot"></span>';
  chatEl.appendChild(el);
  chatEl.scrollTop = chatEl.scrollHeight;
}

function removeThinkingIndicator() {
  const el = document.getElementById('thinking-indicator');
  if (el) el.remove();
}

/* ===== TTS ===== */

function speak(text) {
  if (!window.speechSynthesis) return;
  // Cancel any ongoing speech
  window.speechSynthesis.cancel();

  const utterance = new SpeechSynthesisUtterance(text);
  const lang = getRecognitionLang();
  if (lang) utterance.lang = lang;
  utterance.rate = 1.0;

  // Resume wake word after speaking finishes
  utterance.onend = () => {
    if (handsFreeEnabled && !isListening && !isProcessing) {
      setTimeout(startWakeWordListening, 400);
    }
  };

  window.speechSynthesis.speak(utterance);
}

/* ===== AGENT COMMUNICATION ===== */

async function sendToAgent(text) {
  if (!text.trim() || isProcessing) return;

  isProcessing = true;
  addChatMessage(text, 'user');
  addThinkingIndicator();

  try {
    const resp = await fetch('/api/v1/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: text.trim() }),
    });

    removeThinkingIndicator();

    if (!resp.ok) {
      addChatMessage('Failed to reach the agent. Please try again.', 'error');
      return;
    }

    const data = await resp.json();
    const reply = data.response || '(no response)';
    addChatMessage(reply, 'assistant');
    speak(reply);
  } catch (err) {
    removeThinkingIndicator();
    console.error('Agent request failed:', err);
    addChatMessage('Could not connect to the server.', 'error');
  } finally {
    isProcessing = false;
    // Resume wake word if hands-free
    if (handsFreeEnabled && !isListening) {
      setTimeout(startWakeWordListening, 400);
    }
  }
}

/* ===== TEXT INPUT ===== */

textInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    const text = textInput.value.trim();
    if (text) {
      textInput.value = '';
      sendToAgent(text);
    }
  }
});

sendBtn.addEventListener('click', () => {
  const text = textInput.value.trim();
  if (text) {
    textInput.value = '';
    sendToAgent(text);
  }
});

/* ===== LIVE TRANSCRIPT ===== */

function showLiveTranscript(text) {
  liveTranscript.hidden = false;
  if (text) {
    liveText.textContent = text;
    liveText.classList.add('has-text');
  } else {
    liveText.textContent = 'Listening...';
    liveText.classList.remove('has-text');
  }
}

function updateLiveText(text) {
  if (text) {
    liveText.textContent = text;
    liveText.classList.add('has-text');
  } else {
    liveText.textContent = 'Listening...';
    liveText.classList.remove('has-text');
  }
}

function hideLiveTranscript() {
  liveTranscript.hidden = true;
  liveText.textContent = 'Listening...';
  liveText.classList.remove('has-text');
}

/* ===== QUICK MODE (Web Speech API) ===== */

function initRecognition() {
  if (!SpeechRecognition) return;

  recognition = new SpeechRecognition();
  recognition.continuous     = true;
  recognition.interimResults = true;
  recognition.lang           = getRecognitionLang();
  recognition.maxAlternatives = 1;

  recognition.onstart = () => {
    isListening = true;
    quickFinalTranscript = '';
    showLiveTranscript('');
    micBtn.classList.add('recording');
    micBtn.setAttribute('aria-pressed', 'true');
  };

  recognition.onresult = (event) => {
    let interim = '';
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const result = event.results[i];
      if (result.isFinal) {
        quickFinalTranscript += result[0].transcript + ' ';
      } else {
        interim += result[0].transcript;
      }
    }
    const displayText = (quickFinalTranscript + interim).trim();
    updateLiveText(displayText);
    resetSilenceTimer();
  };

  recognition.onerror = (event) => {
    if (event.error !== 'no-speech') {
      console.warn('Speech recognition error:', event.error);
    }
    stopQuickMode();
  };

  recognition.onend = () => {
    if (isListening) {
      finishQuickRecording();
    }
  };
}

function resetSilenceTimer() {
  clearTimeout(silenceTimer);
  silenceTimer = setTimeout(() => {
    if (isListening) stopQuickMode();
  }, SILENCE_DELAY);
}

function startQuickMode() {
  if (isListening || isProcessing) return;
  if (!recognition) {
    alert('Speech recognition is not available in this browser.');
    return;
  }
  // Stop wake word listener (can't run both concurrently)
  if (wakeWordListening) stopWakeWordListening();
  try {
    recognition.lang = getRecognitionLang();
    recognition.start();
  } catch (e) {
    console.warn('Could not start recognition:', e);
    initRecognition();
    try { recognition.start(); } catch (_) {}
  }
  resetSilenceTimer();
}

function stopQuickMode() {
  clearTimeout(silenceTimer);
  isListening = false;
  if (recognition) {
    try { recognition.stop(); } catch (_) {}
  }
  finishQuickRecording();
}

function finishQuickRecording() {
  isListening = false;
  clearTimeout(silenceTimer);
  micBtn.classList.remove('recording');
  micBtn.setAttribute('aria-pressed', 'false');
  hideLiveTranscript();

  const text = quickFinalTranscript.trim();
  quickFinalTranscript = '';

  if (text) {
    sendToAgent(text);
  } else {
    // No text captured -- resume wake word
    if (handsFreeEnabled) {
      setTimeout(startWakeWordListening, 400);
    }
  }
}

/* Mic button toggles Quick Mode */
micBtn.addEventListener('click', () => {
  if (navigator.vibrate) navigator.vibrate(50);
  if (isListening) {
    stopQuickMode();
  } else if (!isProcessing) {
    startQuickMode();
  }
});

/* ===== WAKE WORD DETECTION ===== */

async function _loadWakeEngine() {
  if (wakeEngineReady || wakeEngineLoading) return;
  if (typeof WakeWordEngine === 'undefined') {
    console.warn('WakeWordEngine not available -- wake word disabled');
    return;
  }
  wakeEngineLoading = true;
  try {
    wakeEngine = new WakeWordEngine({
      keywords: ['hey_chill'],
      modelFiles: { hey_chill: 'hey_chill.onnx' },
      baseAssetUrl: '/static/models',
      ortWasmPath: '/static/wasm/',
      detectionThreshold: 0.5,
      cooldownMs: 2000,
    });
    wakeEngine.on('detect', ({ keyword }) => {
      if (keyword === 'hey_chill') handleWakeWordDetected();
    });
    wakeEngine.on('error', (err) => {
      console.warn('WakeWordEngine error:', err);
    });
    await wakeEngine.load();
    wakeEngineReady = true;
    if (handsFreeEnabled && !isListening && !isProcessing && !wakeWordListening) {
      await _startEngineListening();
    }
  } catch (err) {
    console.warn('WakeWordEngine load failed:', err);
    wakeEngine = null;
    wakeEngineReady = false;
  } finally {
    wakeEngineLoading = false;
  }
}

async function _startEngineListening() {
  try {
    await wakeEngine.start();
    wakeWordListening = true;
    updateWakeDot();
  } catch (err) {
    console.warn('Wake word start failed:', err);
    wakeWordListening = false;
    updateWakeDot();
  }
}

function startWakeWordListening() {
  if (!handsFreeEnabled) return;
  if (isListening || isProcessing) return;
  if (wakeWordListening || wakeEngineLoading) return;

  if (!wakeEngineReady) {
    _loadWakeEngine();
    return;
  }
  _startEngineListening();
}

function stopWakeWordListening() {
  if (!wakeWordListening) return;
  wakeWordListening = false;
  updateWakeDot();
  if (wakeEngine && wakeEngineReady) {
    wakeEngine.stop().catch(() => {});
  }
}

function handleWakeWordDetected() {
  stopWakeWordListening();
  if (!isListening && !isProcessing) {
    if (navigator.vibrate) navigator.vibrate(50);
    startQuickMode();
  }
}

function updateWakeDot() {
  if (!wakeDot) return;
  wakeDot.hidden = !(handsFreeEnabled && wakeWordListening);
}

function setHandsFree(enabled) {
  handsFreeEnabled = enabled;
  localStorage.setItem('handsFreeEnabled', enabled ? '1' : '0');
  if (enabled) {
    startWakeWordListening();
  } else {
    stopWakeWordListening();
  }
  updateWakeDot();
}

/* ===== SETTINGS ===== */

function openSettings() {
  // Populate current values
  langSelect.value = localStorage.getItem('recognitionLang') || '';
  handsFreeToggle.checked = handsFreeEnabled;
  agentUrlInput.value = localStorage.getItem('agentUrl') || '';
  modalOverlay.hidden = false;
}

function closeSettings() {
  modalOverlay.hidden = true;
}

function saveSettings() {
  const lang = langSelect.value;
  localStorage.setItem('recognitionLang', lang);
  if (recognition) recognition.lang = lang;

  const newHandsFree = handsFreeToggle.checked;
  if (newHandsFree !== handsFreeEnabled) {
    setHandsFree(newHandsFree);
  }

  const url = agentUrlInput.value.trim();
  localStorage.setItem('agentUrl', url);

  closeSettings();
}

settingsBtn.addEventListener('click', openSettings);
modalClose.addEventListener('click', closeSettings);
modalOverlay.addEventListener('click', (e) => {
  if (e.target === modalOverlay) closeSettings();
});
saveSettingsBtn.addEventListener('click', saveSettings);

/* ===== KEYBOARD SHORTCUT ===== */

document.addEventListener('keydown', (e) => {
  // Spacebar toggles Quick Mode when not focused on an input
  if (e.code === 'Space' && document.activeElement !== textInput &&
      document.activeElement.tagName !== 'INPUT' &&
      document.activeElement.tagName !== 'SELECT' &&
      document.activeElement.tagName !== 'TEXTAREA') {
    e.preventDefault();
    if (isListening) {
      stopQuickMode();
    } else if (!isProcessing) {
      startQuickMode();
    }
  }
});

/* ===== INIT ===== */

document.addEventListener('DOMContentLoaded', () => {
  if (!SpeechRecognition) {
    notSupported.hidden = false;
    micBtn.disabled = true;
    micBtn.title = 'Speech recognition not supported in this browser';
  } else {
    initRecognition();
  }

  // Restore hands-free setting
  handsFreeEnabled = localStorage.getItem('handsFreeEnabled') === '1';
  if (handsFreeEnabled) {
    startWakeWordListening();
  }
});
