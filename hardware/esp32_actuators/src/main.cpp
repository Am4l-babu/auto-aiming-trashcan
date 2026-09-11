// =============================================================================
//  main.cpp - ESP32 actuator controller for the auto-aiming trashcan.
//
//  The UNO Q does the seeing (USB camera + YOLOX-nano). This board does the
//  moving. They talk over WiFi - both boards sit on the same network, so the
//  trashcan is not tethered to anything and can actually drive around.
//
//  The joke: the lid sits OPEN, inviting. The moment something is actually
//  thrown at it, the lid SLAMS SHUT and the trashcan refuses the rubbish.
//  It reopens a few seconds later to bait the next person.
//
//  COMMANDS (identical over WiFi and serial - one parser, two transports)
//    AIM <offset>   offset -1.0 (target hard left) .. +1.0 (hard right).
//                   0 drives straight. Steers the wheels toward the target.
//    THROWN         something was thrown in -> slam the lid shut, refuse it.
//    OPEN           reopen the lid (bait reset).
//    STOP           stop the wheels.
//    LID <angle>    drive the lid servo to a raw angle. Calibration aid:
//                   use it to find your real OPEN/CLOSED angles.
//    BEEP           play a short test tone through the speaker. Link check
//                   for the MAX98357A, same role PING plays for the network.
//    PLAY <name>    play /<name>.wav from this board's own flash (LittleFS) -
//                   for small clips baked in at build time via uploadfs.
//    PING           replies "PONG". Link check.
//
//  Large/many clips do not fit on this board's flash. For those, the UNO Q
//  keeps the files on its own storage and streams raw PCM to TCP port 8081:
//  connect, send a 5-byte header (4-byte LE sample rate + 1-byte channel
//  count), then just write samples until the socket closes. Runs on core 0,
//  independent of the motor/servo loop, so a long clip never blocks steering.
//
//  OVER WIFI    GET http://<ip>/cmd?c=THROWN
//               GET http://<ip>/         control page, works from a phone
//  OVER SERIAL  type the command at 115200 baud
//
//  WIRING
//    L298N     ENA 18  ENB 19  IN1 27  IN2 26  IN3 25  IN4 33
//    Lid servo signal -> GPIO 17, servo V+ -> its own 5V supply (NOT the
//    ESP32 3V3 pin), servo GND -> common ground with the ESP32.
//    MAX98357A DIN 23  BCLK 22  LRC/WS 21  GND -> GND  VIN -> 5V
// =============================================================================
#include <Arduino.h>
#include <ESP32Servo.h>
#include <WiFi.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include <driver/i2s.h>
#include <math.h>
#include <FS.h>
#include <LittleFS.h>
#include "secrets.h"

// ---- Motor driver (L298N) ---------------------------------------------------
const int ENA = 18;
const int ENB = 19;
const int IN1 = 27;
const int IN2 = 26;
const int IN3 = 25;
const int IN4 = 33;

// Motor PWM lives on LEDC channels 4/5 (timer 2). ESP32Servo gets timer 0,
// allocated in setup(). Keeping them on separate timers stops the servo from
// jittering every time the motor duty changes.
const int PWM_CH_A = 4;
const int PWM_CH_B = 5;
const int PWM_FREQ = 5000;
const int PWM_RES  = 8;

const int DRIVE_SPEED = 200;   // 0-255. Steering is bang-bang at this duty.

// Motor B measured slower than Motor A on this build at equal duty. Scale B up
// to match. 1.00 = no correction; raise until both wheels turn at the same rate.
const float MOTOR_B_TRIM = 1.00f;

// ---- Lid servo --------------------------------------------------------------
const int LID_SERVO_PIN = 17;

// Calibrate these from the web page slider, then set them here.
const int LID_OPEN_ANGLE   = 180;
const int LID_CLOSED_ANGLE = 90;

const uint16_t SERVO_MIN_US = 500;
const uint16_t SERVO_MAX_US = 2400;

// The lid slams shut fast (that is the gag) but reopens lazily.
const uint16_t LID_CLOSE_MS = 180;
const uint16_t LID_OPEN_MS  = 900;

// How long the lid stays shut before reopening to bait the next person.
const uint32_t LID_SHUT_HOLD_MS = 4000;

// Stop the wheels if the UNO Q goes quiet - never keep driving blind.
const uint32_t AIM_TIMEOUT_MS = 1000;

// ---- Speaker (MAX98357A, I2S) ------------------------------------------------
const int I2S_BCLK_PIN = 22;
const int I2S_WS_PIN   = 21;   // LRC
const int I2S_DOUT_PIN = 23;   // DIN on the amp

const int I2S_SAMPLE_RATE = 16000;
const i2s_port_t I2S_PORT = I2S_NUM_0;

// Raw PCM audio streaming, for clips too large to fit on this board's flash.
// The UNO Q keeps the actual audio files on its own storage and streams the
// samples over this socket live; nothing is ever copied onto the ESP32.
// Runs on core 0 in its own task so a multi-minute clip can never block the
// motor/servo loop, which stays on core 1 and must keep running to enforce
// AIM_TIMEOUT_MS.
const uint16_t AUDIO_STREAM_PORT = 8081;
WiFiServer audioServer(AUDIO_STREAM_PORT);
SemaphoreHandle_t i2sMutex;

Servo     lidServo;
WebServer server(80);

enum LidState : uint8_t { LID_IDLE, LID_MOVING, LID_SHUT_WAITING };

LidState lidState   = LID_IDLE;
float    lidAngle   = LID_OPEN_ANGLE;
float    lidFrom    = LID_OPEN_ANGLE;
float    lidTo      = LID_OPEN_ANGLE;
uint32_t lidStarted = 0;
uint16_t lidSegment = 1;
uint32_t lidShutAt  = 0;

float    aimOffset = 0.0f;
bool     aimActive = false;
uint32_t lastAimAt = 0;

String   inputLine;

// ---- Motors -----------------------------------------------------------------
void motorA(int speed, bool forward) {
    digitalWrite(IN1, forward ? HIGH : LOW);
    digitalWrite(IN2, forward ? LOW : HIGH);
    ledcWrite(PWM_CH_A, constrain(speed, 0, 255));
}

void motorB(int speed, bool forward) {
    digitalWrite(IN3, forward ? HIGH : LOW);
    digitalWrite(IN4, forward ? LOW : HIGH);
    ledcWrite(PWM_CH_B, constrain((int)(speed * MOTOR_B_TRIM), 0, 255));
}

void stopMotors() {
    ledcWrite(PWM_CH_A, 0);
    ledcWrite(PWM_CH_B, 0);
    digitalWrite(IN1, LOW);
    digitalWrite(IN2, LOW);
    digitalWrite(IN3, LOW);
    digitalWrite(IN4, LOW);
}

void steer(float offset) {
    const float deadzone = 0.12f;
    if (offset < -deadzone) {        // target left: pivot left
        motorA(DRIVE_SPEED, false);
        motorB(DRIVE_SPEED, true);
    } else if (offset > deadzone) {  // target right: pivot right
        motorA(DRIVE_SPEED, true);
        motorB(DRIVE_SPEED, false);
    } else {                         // centered: close in
        motorA(DRIVE_SPEED, true);
        motorB(DRIVE_SPEED, true);
    }
}

// ---- Lid --------------------------------------------------------------------
static inline float ease(float t) {
    if (t <= 0.0f) return 0.0f;
    if (t >= 1.0f) return 1.0f;
    return 0.5f * (1.0f - cosf((float)M_PI * t));
}

void moveLid(int target, uint16_t durationMs) {
    lidFrom    = lidAngle;
    lidTo      = constrain(target, 0, 180);
    lidSegment = durationMs ? durationMs : 1;
    lidStarted = millis();
    lidState   = LID_MOVING;
}

void updateLid() {
    if (lidState == LID_MOVING) {
        const uint32_t elapsed = millis() - lidStarted;
        const float t = ease((float)elapsed / (float)lidSegment);
        lidAngle = lidFrom + t * (lidTo - lidFrom);
        lidServo.write((int)lroundf(lidAngle));

        if (elapsed >= lidSegment) {
            lidAngle = lidTo;
            lidServo.write((int)lroundf(lidAngle));
            // Shutting the lid starts the hold timer that later reopens it.
            if ((int)lroundf(lidTo) == LID_CLOSED_ANGLE) {
                lidState  = LID_SHUT_WAITING;
                lidShutAt = millis();
            } else {
                lidState = LID_IDLE;
            }
        }
    } else if (lidState == LID_SHUT_WAITING) {
        if (millis() - lidShutAt >= LID_SHUT_HOLD_MS) {
            Serial.println("EVT reopening");
            moveLid(LID_OPEN_ANGLE, LID_OPEN_MS);
        }
    }
}

// ---- Speaker ------------------------------------------------------------
void i2sInit() {
    const i2s_config_t config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
        .sample_rate = I2S_SAMPLE_RATE,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
        .channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT,
        .communication_format = I2S_COMM_FORMAT_STAND_I2S,
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 4,
        .dma_buf_len = 256,
        .use_apll = false,
        .tx_desc_auto_clear = true,
    };
    const i2s_pin_config_t pins = {
        .bck_io_num = I2S_BCLK_PIN,
        .ws_io_num = I2S_WS_PIN,
        .data_out_num = I2S_DOUT_PIN,
        .data_in_num = I2S_PIN_NO_CHANGE,
    };
    i2s_driver_install(I2S_PORT, &config, 0, nullptr);
    i2s_set_pin(I2S_PORT, &pins);
}

// Blocking - only ever called from a manual command, never from the aim/lid
// loop, so a few hundred ms of block here does not affect steering or safety
// timing. Long clips go through the streaming path below instead, on the
// other core, precisely so they never end up blocking here.
void playTone(float freqHz, uint16_t durationMs, float volume = 0.5f) {
    xSemaphoreTake(i2sMutex, portMAX_DELAY);
    const int samples = (I2S_SAMPLE_RATE * durationMs) / 1000;
    int16_t frame[2];
    size_t written;
    for (int i = 0; i < samples; i++) {
        const float t = (float)i / (float)I2S_SAMPLE_RATE;
        const int16_t sample = (int16_t)(sinf(2.0f * (float)M_PI * freqHz * t) * volume * 32000.0f);
        frame[0] = sample;
        frame[1] = sample;
        i2s_write(I2S_PORT, frame, sizeof(frame), &written, portMAX_DELAY);
    }
    xSemaphoreGive(i2sMutex);
}

void playTestChirp() {
    // Two quick rising notes - unmistakable over a silent, unbeeping board.
    playTone(880.0f, 120, 0.5f);
    playTone(1318.5f, 160, 0.5f);
}

// Minimal WAV reader: assumes the canonical 44-byte header (16-bit PCM,
// mono or stereo) written by any standard export - Audacity, ffmpeg,
// Python's wave module. Anything more exotic (extra chunks, float samples,
// compressed formats) is not handled and will just play as noise or fail
// the sanity checks below.
struct WavInfo {
    uint16_t channels;
    uint32_t sampleRate;
    uint16_t bitsPerSample;
    uint32_t dataSize;
};

bool readWavHeader(File &f, WavInfo &info) {
    uint8_t header[44];
    if (f.read(header, 44) != 44) return false;
    if (memcmp(header, "RIFF", 4) != 0 || memcmp(header + 8, "WAVE", 4) != 0) return false;

    info.channels      = header[22] | (header[23] << 8);
    info.sampleRate     = header[24] | (header[25] << 8) | (header[26] << 16) | ((uint32_t)header[27] << 24);
    info.bitsPerSample = header[34] | (header[35] << 8);
    info.dataSize       = header[40] | (header[41] << 8) | (header[42] << 16) | ((uint32_t)header[43] << 24);
    return info.bitsPerSample == 16 && (info.channels == 1 || info.channels == 2);
}

// Streams a file straight off flash rather than loading it into RAM - clips
// can be longer than free heap allows. Re-initializes the I2S clock to match
// the file's own sample rate, so clips don't need to share one fixed rate.
String playWavFile(const String &name) {
    const String path = "/" + name + ".wav";
    if (!LittleFS.exists(path)) return "ERR no such clip: " + path;

    File f = LittleFS.open(path, "r");
    if (!f) return "ERR could not open " + path;

    WavInfo info;
    if (!readWavHeader(f, info)) {
        f.close();
        return "ERR " + path + " is not a 16-bit PCM WAV";
    }

    xSemaphoreTake(i2sMutex, portMAX_DELAY);
    i2s_set_sample_rates(I2S_PORT, info.sampleRate);

    const size_t bufSamples = 512;
    int16_t inBuf[bufSamples];
    int16_t outFrame[2];
    size_t written;

    while (f.available()) {
        const size_t got = f.read((uint8_t *)inBuf, sizeof(inBuf)) / sizeof(int16_t);
        for (size_t i = 0; i < got; ) {
            if (info.channels == 1) {
                outFrame[0] = outFrame[1] = inBuf[i];
                i += 1;
            } else {
                outFrame[0] = inBuf[i];
                outFrame[1] = inBuf[i + 1];
                i += 2;
            }
            i2s_write(I2S_PORT, outFrame, sizeof(outFrame), &written, portMAX_DELAY);
        }
    }

    f.close();
    i2s_set_sample_rates(I2S_PORT, I2S_SAMPLE_RATE);  // restore default for playTone()/BEEP
    xSemaphoreGive(i2sMutex);
    return "OK played " + path;
}

// ---- Audio streaming (large clips, held on the UNO Q's own storage) --------
// Wire protocol, deliberately tiny: the client (UNO Q) connects, sends a
// 5-byte header - 4-byte little-endian sample rate + 1-byte channel count
// (1 or 2) - then just writes raw signed 16-bit PCM until it closes the
// socket. No length prefix needed: EOF is the end of the clip.
void streamClientAudio(WiFiClient &client) {
    uint8_t hdr[5];
    if (client.readBytes(hdr, sizeof(hdr)) != sizeof(hdr)) {
        Serial.println("EVT audio stream: short header, dropping connection");
        return;
    }
    const uint32_t rate = hdr[0] | (hdr[1] << 8) | (hdr[2] << 16) | ((uint32_t)hdr[3] << 24);
    const uint8_t channels = hdr[4];
    if (channels != 1 && channels != 2) {
        Serial.println("EVT audio stream: bad channel count, dropping connection");
        return;
    }

    Serial.print("EVT audio stream started, rate=");
    Serial.print(rate);
    Serial.print(" ch=");
    Serial.println(channels);

    xSemaphoreTake(i2sMutex, portMAX_DELAY);
    i2s_set_sample_rates(I2S_PORT, rate);

    // TCP delivers bytes in whatever chunks the network happens to hand over -
    // it has no idea a "sample" is 2 bytes (or a stereo frame is 4). A chunk
    // boundary landing mid-sample used to shift every following sample by a
    // byte and turn the rest of the clip to noise. carry[] holds that partial
    // sample across reads so alignment never drifts.
    const size_t frameBytes = channels * 2;
    uint8_t carry[4];
    size_t carryLen = 0;

    const size_t bufBytes = 1024;
    uint8_t raw[bufBytes];
    int16_t outFrame[2];
    size_t written;

    while (client.connected() || client.available()) {
        const int n = client.available();
        if (n <= 0) {
            delay(2);   // yields to other tasks on this core while waiting for more data
            continue;
        }
        memcpy(raw, carry, carryLen);
        const int toRead = min(n, (int)(bufBytes - carryLen));
        const int got = client.read(raw + carryLen, toRead);
        const size_t total = carryLen + (got > 0 ? (size_t)got : 0);
        const size_t usable = total - (total % frameBytes);
        carryLen = total - usable;
        memcpy(carry, raw + usable, carryLen);

        const int16_t *samples = (const int16_t *)raw;
        const size_t sampleUnits = usable / 2;

        for (size_t i = 0; i < sampleUnits; ) {
            if (channels == 1) {
                outFrame[0] = outFrame[1] = samples[i];
                i += 1;
            } else {
                outFrame[0] = samples[i];
                outFrame[1] = samples[i + 1];
                i += 2;
            }
            i2s_write(I2S_PORT, outFrame, sizeof(outFrame), &written, portMAX_DELAY);
        }
    }

    i2s_set_sample_rates(I2S_PORT, I2S_SAMPLE_RATE);
    xSemaphoreGive(i2sMutex);
    Serial.println("EVT audio stream ended");
}

// Runs on core 0, forever, independent of the main motor/servo loop on core 1.
void audioTask(void *param) {
    (void)param;
    for (;;) {
        if (audioServer.hasClient()) {
            WiFiClient client = audioServer.accept();
            streamClientAudio(client);
            client.stop();
        }
        vTaskDelay(10 / portTICK_PERIOD_MS);
    }
}

// ---- Command handling (shared by WiFi and serial) ---------------------------
String handleCommand(String line) {
    line.trim();
    if (line.length() == 0) return "ERR empty";

    if (line.startsWith("AIM")) {
        aimOffset = line.substring(3).toFloat();
        aimActive = true;
        lastAimAt = millis();
        return "OK AIM " + String(aimOffset, 3);

    } else if (line == "THROWN") {
        // The whole point of the machine.
        moveLid(LID_CLOSED_ANGLE, LID_CLOSE_MS);
        aimActive = false;
        stopMotors();
        return "OK THROWN lid=closed";

    } else if (line == "OPEN") {
        moveLid(LID_OPEN_ANGLE, LID_OPEN_MS);
        return "OK OPEN";

    } else if (line == "STOP") {
        aimActive = false;
        stopMotors();
        return "OK STOP";

    } else if (line.startsWith("LID")) {
        const int angle = line.substring(3).toInt();
        moveLid(angle, LID_OPEN_MS);
        return "OK LID " + String(angle);

    } else if (line == "BEEP") {
        playTestChirp();
        return "OK BEEP";

    } else if (line.startsWith("PLAY")) {
        String name = line.substring(4);
        name.trim();
        if (name.length() == 0) return "ERR PLAY needs a clip name, e.g. PLAY denied";
        return playWavFile(name);

    } else if (line == "PING") {
        return "PONG";
    }

    return "ERR unknown: " + line;
}

void readSerial() {
    while (Serial.available()) {
        const char c = (char)Serial.read();
        if (c == '\n' || c == '\r') {
            if (inputLine.length()) {
                Serial.println(handleCommand(inputLine));
                inputLine = "";
            }
        } else if (inputLine.length() < 64) {
            inputLine += c;
        }
    }
}

// ---- HTTP -------------------------------------------------------------------
const char CONTROL_PAGE[] PROGMEM = R"HTML(<!doctype html>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Trashcan</title>
<style>
body{font-family:system-ui;margin:0;padding:24px;background:#111;color:#eee}
h1{font-size:1.2rem;margin:0 0 4px}p{color:#888;margin:0 0 20px;font-size:.85rem}
button{display:block;width:100%;padding:16px;margin:8px 0;font-size:1rem;
border:0;border-radius:10px;background:#2a2a2a;color:#eee}
button.slam{background:#7a1f1f}
input{width:100%}label{font-size:.85rem;color:#888}
#out{margin-top:16px;padding:10px;background:#000;border-radius:8px;
font-family:monospace;font-size:.8rem;color:#6f6;min-height:1.2em}
</style>
<h1>Auto-aiming trashcan</h1>
<p>Manual override / servo calibration</p>
<button class=slam onclick="c('THROWN')">SLAM LID (refuse)</button>
<button onclick="c('OPEN')">Open lid</button>
<button onclick="c('STOP')">Stop wheels</button>
<button onclick="c('BEEP')">Test speaker</button>
<label>Lid angle: <span id=a>90</span>&deg;</label>
<input type=range min=0 max=180 value=90 oninput="a.textContent=this.value"
onchange="c('LID '+this.value)">
<div id=out>ready</div>
<script>
function c(x){fetch('/cmd?c='+encodeURIComponent(x))
.then(r=>r.text()).then(t=>out.textContent=t)
.catch(e=>out.textContent='ERR '+e)}
</script>)HTML";

void handleRoot() {
    server.send_P(200, "text/html", CONTROL_PAGE);
}

void handleCmd() {
    if (!server.hasArg("c")) {
        server.send(400, "text/plain", "ERR missing c parameter");
        return;
    }
    const String reply = handleCommand(server.arg("c"));
    server.send(200, "text/plain", reply);
}

void handleStatus() {
    String s = "{\"lid\":" + String((int)lroundf(lidAngle));
    s += ",\"aim\":" + String(aimOffset, 3);
    s += ",\"driving\":" + String(aimActive ? "true" : "false");
    s += ",\"rssi\":" + String(WiFi.RSSI()) + "}";
    server.send(200, "application/json", s);
}

void setup() {
    Serial.begin(115200);

    i2sMutex = xSemaphoreCreateMutex();

    pinMode(IN1, OUTPUT);
    pinMode(IN2, OUTPUT);
    pinMode(IN3, OUTPUT);
    pinMode(IN4, OUTPUT);
    ledcSetup(PWM_CH_A, PWM_FREQ, PWM_RES);
    ledcSetup(PWM_CH_B, PWM_FREQ, PWM_RES);
    ledcAttachPin(ENA, PWM_CH_A);
    ledcAttachPin(ENB, PWM_CH_B);
    stopMotors();

    ESP32PWM::allocateTimer(0);
    lidServo.setPeriodHertz(50);
    lidServo.attach(LID_SERVO_PIN, SERVO_MIN_US, SERVO_MAX_US);
    lidAngle = LID_OPEN_ANGLE;
    lidServo.write(LID_OPEN_ANGLE);

    i2sInit();

    if (!LittleFS.begin(true)) {
        Serial.println("LITTLEFS mount failed - PLAY will not work until reflashed with uploadfs");
    } else {
        Serial.println("LITTLEFS mounted");
    }

    Serial.println();
    Serial.println("BOOT auto-aiming-trashcan esp32 actuators");

    // WiFi is how the UNO Q talks to us, but a failure here must not take the
    // machine down: serial still accepts every command.
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    Serial.print("WIFI connecting to ");
    Serial.print(WIFI_SSID);
    const uint32_t startedAt = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - startedAt < 20000) {
        delay(250);
        Serial.print(".");
    }
    Serial.println();

    if (WiFi.status() == WL_CONNECTED) {
        Serial.print("WIFI ok  ip=");
        Serial.print(WiFi.localIP());
        Serial.print("  rssi=");
        Serial.println(WiFi.RSSI());
        if (MDNS.begin("trashcan")) {
            MDNS.addService("http", "tcp", 80);
            Serial.println("MDNS trashcan.local");
        }
    } else {
        Serial.println("WIFI failed - serial commands still work");
    }

    server.on("/", handleRoot);
    server.on("/cmd", handleCmd);
    server.on("/status", handleStatus);
    server.begin();

    audioServer.begin();
    // Pinned to core 0 - the main loop (motors, servo, HTTP commands) runs on
    // core 1 by default and must never be blocked by a long audio stream.
    xTaskCreatePinnedToCore(audioTask, "audioStream", 4096, nullptr, 1, nullptr, 0);
    Serial.print("AUDIO stream server on port ");
    Serial.println(AUDIO_STREAM_PORT);

    Serial.println("READY cmds: AIM <-1..1> | THROWN | OPEN | STOP | LID <angle> | BEEP | PLAY <name> | PING");
}

void loop() {
    server.handleClient();
    readSerial();
    updateLid();

    // Wheels only run while the UNO Q keeps saying where to go.
    if (aimActive && millis() - lastAimAt <= AIM_TIMEOUT_MS) {
        steer(aimOffset);
    } else {
        if (aimActive) {
            aimActive = false;
            Serial.println("EVT aim timeout, motors stopped");
        }
        stopMotors();
    }
}
