// =============================================================================
//  sketch.ino - MCU side of the Object & Human Detection app.
//
//  Deliberately empty. All actuation (wheels + lid servo) lives on a separate
//  ESP32 that joins the same WiFi and takes commands over HTTP - see
//  hardware/esp32_actuators/. The UNO Q's job is the camera and the model,
//  which both run on the Linux side in python/main.py; nothing in this app
//  needs the microcontroller.
//
//  If you later add hardware directly to the UNO Q headers (a status LED, a
//  bump switch, an encoder), this is where it goes - reach it from Python
//  with Bridge.provide_safe() here and @call()/@notify() there.
// =============================================================================

void setup() {
}

void loop() {
}
