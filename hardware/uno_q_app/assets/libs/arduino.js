// Minimal REST client for the app's WebUI brick API.
class BoardAPI {
  async get(path, params) {
    const query = params ? '?' + new URLSearchParams(params).toString() : '';
    const response = await fetch(`/api${path}${query}`);
    if (!response.ok) {
      throw new Error(`${path} failed: ${response.status}`);
    }
    return response.json();
  }
}
