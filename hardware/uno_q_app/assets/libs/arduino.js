// Minimal REST client for the app's WebUI brick API.
//
// Routes registered via ui.expose_api() live at their plain path - no "/api"
// prefix - confirmed by hitting the board directly (http://<ip>:7000/detections
// returns 200, http://<ip>:7000/api/detections 404s). The prefix this file
// used to hardcode never matched that, so every call here silently failed
// whenever the page was opened this way (which is how a phone on the same
// WiFi reaches it) - the person-status panel and confidence slider looked
// like they should work but the fetches were 404ing the whole time.
class BoardAPI {
  async get(path, params) {
    const query = params ? '?' + new URLSearchParams(params).toString() : '';
    const response = await fetch(`${path}${query}`);
    if (!response.ok) {
      throw new Error(`${path} failed: ${response.status}`);
    }
    return response.json();
  }
}
