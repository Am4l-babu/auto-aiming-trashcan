const api = new BoardAPI();

const errorContainer = document.getElementById('error-container');
const recentDetectionsElement = document.getElementById('recentDetections');
const personStatus = document.getElementById('personStatus');
const personStatusText = document.getElementById('personStatusText');
const personSubtext = document.getElementById('personSubtext');
const confidenceSlider = document.getElementById('confidenceSlider');
const confidenceValue = document.getElementById('confidenceValue');
const clipPlayer = document.getElementById('clipPlayer');
const enableSoundBtn = document.getElementById('enableSoundBtn');

// Phone browsers refuse to autoplay audio until the page has had a real tap.
// This button plays a silent, near-instant clip once to "unlock" audio for
// the rest of the session - after that, unattended play() calls triggered by
// polling below are allowed.
let soundEnabled = false;
enableSoundBtn.addEventListener('click', () => {
  clipPlayer.src = 'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=';
  clipPlayer.play()
    .then(() => {
      soundEnabled = true;
      enableSoundBtn.textContent = '🔊 Sound enabled';
      enableSoundBtn.disabled = true;
    })
    .catch((err) => showError('Could not enable sound: ' + err.message));
});

// undefined until the first poll: that first value is a baseline (whatever
// clip last played before this page was even open), never something to play.
let lastClipSeq;

function maybePlayClip(state) {
  if (lastClipSeq === undefined) {
    lastClipSeq = state.clip_seq;
    return;
  }
  if (!soundEnabled || state.clip_seq === lastClipSeq) {
    return;
  }
  lastClipSeq = state.clip_seq;
  if (!state.clip_name) {
    return;
  }
  clipPlayer.src = `/api/sound?name=${encodeURIComponent(state.clip_name)}`;
  clipPlayer.play().catch((err) => showError('Clip playback failed: ' + err.message));
}

// The detection brick publishes the annotated stream on its own port.
const iframe = document.getElementById('dynamicIframe');
const placeholder = document.getElementById('videoPlaceholder');
const streamUrl = `http://${window.location.hostname}:4912/embed`;

let streamIntervalId = setInterval(() => {
  iframe.src = streamUrl;
}, 1000);

iframe.onload = () => {
  clearInterval(streamIntervalId);
  placeholder.style.display = 'none';
  iframe.style.display = 'block';
};

confidenceSlider.addEventListener('input', () => {
  confidenceValue.textContent = parseFloat(confidenceSlider.value).toFixed(2);
});
confidenceSlider.addEventListener('change', async () => {
  try {
    await api.get('/confidence', { value: confidenceSlider.value });
  } catch (err) {
    showError(err.message);
  }
});

function showError(message) {
  errorContainer.textContent = message;
  errorContainer.style.display = 'block';
}

function clearError() {
  errorContainer.style.display = 'none';
  errorContainer.textContent = '';
}

function renderPerson(state) {
  personStatus.classList.toggle('present', state.person_present);
  personStatusText.textContent = state.person_present ? 'Person detected' : 'No person detected';

  if (state.last_person_seen) {
    const seen = new Date(state.last_person_seen);
    personSubtext.textContent = `Last seen at ${seen.toLocaleTimeString()}`;
  } else {
    personSubtext.textContent = 'No person seen since the app started.';
  }
}

function renderDetections(detections) {
  recentDetectionsElement.innerHTML = '';

  if (!detections.length) {
    recentDetectionsElement.innerHTML = '<li class="empty">Nothing detected yet</li>';
    return;
  }

  for (const detection of detections) {
    const item = document.createElement('li');
    if (detection.is_person) {
      item.classList.add('person');
    }

    const label = document.createElement('span');
    label.className = 'detection-label';
    const percent = Math.round((detection.confidence ?? 0) * 100);
    label.textContent = `${percent}% — ${detection.label}`;

    const time = document.createElement('span');
    time.className = 'detection-time';
    time.textContent = new Date(detection.timestamp).toLocaleTimeString();

    item.appendChild(label);
    item.appendChild(time);
    recentDetectionsElement.appendChild(item);
  }
}

async function refresh() {
  try {
    const state = await api.get('/detections');
    clearError();
    renderPerson(state);
    renderDetections(state.detections);
    maybePlayClip(state);
  } catch (err) {
    showError('Cannot reach the board: ' + err.message);
  }
}

renderDetections([]);
refresh();
setInterval(refresh, 500);
