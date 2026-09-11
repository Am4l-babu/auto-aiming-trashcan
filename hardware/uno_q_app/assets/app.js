const api = new BoardAPI();

const errorContainer = document.getElementById('error-container');
const recentDetectionsElement = document.getElementById('recentDetections');
const personStatus = document.getElementById('personStatus');
const personStatusText = document.getElementById('personStatusText');
const personSubtext = document.getElementById('personSubtext');
const confidenceSlider = document.getElementById('confidenceSlider');
const confidenceValue = document.getElementById('confidenceValue');

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
  } catch (err) {
    showError('Cannot reach the board: ' + err.message);
  }
}

renderDetections([]);
refresh();
setInterval(refresh, 500);
